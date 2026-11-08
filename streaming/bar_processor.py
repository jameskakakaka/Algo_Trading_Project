"""Opt-in in-memory consumer correctness; no Kafka, indicators, or trading."""
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from decimal import Decimal
import json

from schemas.data_types import (
    BarValidationError, IDENTITY_FIELDS, MIN_TIME_MS, MAX_TIME_MS, PRICE_FIELDS,
    classify_bar_events, generate_event_id, normalize_supported_value,
    storage_identity, validate_finalized_bar,
)


def stream_identity(exchange, market, symbol, timeframe):
    """Canonical four-component stream identity (not a bar/storage identity)."""
    return tuple(normalize_supported_value(k, v) for k, v in zip(
        IDENTITY_FIELDS[:4], (exchange, market, symbol, timeframe)))


def decimal_ohlcv(event):
    """Validate first; explicitly convert strings to exact Decimal feature inputs.

    These values are not JSON serializable; retain the canonical event for JSON.
    No implicit float conversion or ML-library dependency is introduced.
    """
    bar = validate_finalized_bar(event)
    return {key: Decimal(bar[key]) for key in PRICE_FIELDS}


@dataclass(frozen=True)
class ModelSpec:
    exchange: str
    market: str
    symbol: str
    timeframe: str
    warmup_bars: int

    def __post_init__(self):
        stream_identity(self.exchange, self.market, self.symbol, self.timeframe)
        if type(self.warmup_bars) is not int or self.warmup_bars < 1:
            raise ValueError('warmup_bars must be a positive integer')

    @property
    def stream(self):
        return stream_identity(self.exchange, self.market, self.symbol, self.timeframe)


@dataclass(frozen=True)
class ProcessResult:
    outcome: str
    reason: str
    stream: tuple | None = None
    storage_key: str | None = None
    next_cursor_ms: int | None = None
    missing_range: tuple | None = None
    inference_ready: bool = False
    inference_blocks: tuple = ()
    stale: bool = False
    # Always disabled: this module has no execution integration.
    paper_trading_enabled: bool = False


@dataclass
class _State:
    next_cursor_ms: int
    window: deque
    history: OrderedDict = field(default_factory=OrderedDict)
    recovery_end_ms: int | None = None
    conflict: tuple | None = None


class BarProcessor:
    """Single-threaded, bounded state; explicitly register each starting cursor.

    Results and snapshots never expose internal event dictionaries. Recovery
    resubmits missing bars in order; future events are not buffered internally.
    """
    def __init__(self, *, window_size=60, history_size=256, max_streams=32,
                 max_age_ms=120_000):
        for name, value in (('window_size', window_size), ('history_size', history_size),
                            ('max_streams', max_streams), ('max_age_ms', max_age_ms)):
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if history_size < window_size:
            raise ValueError('history_size must cover window_size')
        self.window_size, self.history_size = window_size, history_size
        self.max_streams, self.max_age_ms = max_streams, max_age_ms
        self._streams = {}

    def register_stream(self, *, exchange, market='spot', symbol, timeframe, start_time_ms):
        """Set an explicit trusted starting open; never reset an existing stream."""
        stream = stream_identity(exchange, market, symbol, timeframe)
        generate_event_id(*stream, start_time_ms)
        if stream in self._streams:
            raise ValueError('stream already registered; reset requires a new processor')
        if len(self._streams) >= self.max_streams:
            raise ValueError('stream capacity reached')
        self._streams[stream] = _State(start_time_ms, deque(maxlen=self.window_size))
        return stream

    def snapshot(self, stream):
        """Return independent JSON-compatible state evidence for tests/review."""
        state = self._streams[stream]
        return dict(next_cursor_ms=state.next_cursor_ms,
                    recovery_end_ms=state.recovery_end_ms,
                    window=[dict(b) for b in state.window],
                    history=[dict(b) for b in state.history.values()],
                    conflict=None if state.conflict is None else [dict(b) for b in state.conflict])

    @staticmethod
    def _check_context(now_ms, replay, model):
        if type(now_ms) is not int or not MIN_TIME_MS <= now_ms < MAX_TIME_MS:
            raise ValueError('now_ms must be strict Unix milliseconds in v1 domain')
        if type(replay) is not bool:
            raise ValueError('replay must be boolean')
        if model is not None and not isinstance(model, ModelSpec):
            raise ValueError('model must be ModelSpec or None')

    def process_json(self, payload, *, now_ms, replay=True, model=None):
        """Decode JSON without accepting duplicate object keys or coercing nulls."""
        self._check_context(now_ms, replay, model)

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON key')
                result[key] = value
            return result

        try:
            if type(payload) is not str:
                raise ValueError('payload must be JSON text')
            event = json.loads(payload, object_pairs_hook=unique_object)
        except ValueError as error:
            return ProcessResult('rejected', str(error))
        return self.process(event, now_ms=now_ms, replay=replay, model=model)

    def process(self, event, *, now_ms, replay=True, model=None):
        """Validate before mutation; replay defaults safe. See BAR_PROCESSOR.md."""
        self._check_context(now_ms, replay, model)
        try:
            bar = validate_finalized_bar(event)
        except BarValidationError as error:
            return ProcessResult('rejected', str(error))
        stream = tuple(bar[k] for k in IDENTITY_FIELDS[:4])
        key = storage_identity(bar)
        state = self._streams.get(stream)
        if state is None:
            return ProcessResult('deferred', 'unregistered_stream', stream, key)
        stale = now_ms - bar['end_time_ms'] > self.max_age_ms

        def result(outcome, reason, *, ready=False, blocks=(), missing=None):
            return ProcessResult(outcome, reason, stream, key, state.next_cursor_ms,
                                 missing, ready, blocks, stale)

        if bar['published_at_ms'] > now_ms:
            return result('deferred', 'future_metadata')
        if state.conflict is not None:
            return result('deferred', 'stream_quarantined')
        opening = bar['open_time_ms']
        known = state.history.get(opening)
        if known is not None:
            if classify_bar_events(known, bar) == 'duplicate':
                return result('duplicate', 'retained_content_matches')
            state.conflict = (dict(known), dict(bar))
            state.window.clear()
            return result('conflict', 'stream_quarantined')
        if opening < state.next_cursor_ms:
            return result('out_of_order', 'older_identity_without_content_evidence')
        if opening > state.next_cursor_ms:
            state.recovery_end_ms = max(state.recovery_end_ms or 0, bar['end_time_ms'])
            return result('gap', 'backfill_and_resubmit_required',
                          missing=(state.next_cursor_ms, opening))
        state.window.append(bar)
        state.history[opening] = bar
        if len(state.history) > self.history_size:
            state.history.popitem(last=False)
        state.next_cursor_ms = bar['end_time_ms']
        if state.recovery_end_ms is not None and state.next_cursor_ms >= state.recovery_end_ms:
            state.recovery_end_ms = None
        blocks = []
        if replay:
            blocks.append('historical_replay')
        if stale:
            blocks.append('stale_record')
        if state.recovery_end_ms is not None:
            blocks.append('unresolved_gap')
        if model is None:
            blocks.append('model_metadata_missing')
        else:
            if model.stream != stream:
                blocks.append('model_stream_mismatch')
            if len(state.window) < model.warmup_bars:
                blocks.append('insufficient_warmup')
        return result('accepted', 'contiguous_bar', ready=not blocks, blocks=tuple(blocks))
