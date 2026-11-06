"""Opt-in synchronous offline orchestration; no transport or trading defaults."""
from dataclasses import dataclass

from schemas.data_types import classify_bar_events, storage_identity, validate_finalized_bar
from streaming.bar_processor import BarProcessor, ProcessResult


class StoredBarConflict(ValueError):
    """Stored canonical market content differs; no overwrite was attempted."""
    def __init__(self, existing, candidate):
        super().__init__('stored finalized bar conflicts with accepted candidate')
        self.existing, self.candidate = dict(existing), dict(candidate)


class StoredBarIntegrityError(ValueError):
    """The existing value violates the dedicated v1 namespace contract."""


class AcceptedBarStore:
    """Single-writer adapter over get(key)/put(key=..., value=...).

    Only accepted processing results can enter this adapter. It does not own
    storage lifecycle. get(None) means absence under the dedicated namespace
    assumption; stored nulls are unsupported by that contract.
    """
    def __init__(self, store):
        self._store = store

    def persist(self, event, decision):
        bar = validate_finalized_bar(event)
        key = storage_identity(bar)
        if decision.outcome != 'accepted' or decision.storage_key != key:
            raise ValueError('persistence requires a matching accepted result')
        existing = self._store.get(key)
        if existing is not None:
            try:
                existing = validate_finalized_bar(existing)
            except ValueError as error:
                raise StoredBarIntegrityError('stored value is not a valid v1 bar') from error
            if storage_identity(existing) != key:
                raise StoredBarIntegrityError('stored value has mismatched identity')
            if classify_bar_events(existing, bar) != 'duplicate':
                raise StoredBarConflict(existing, bar)
            return 'already_stored'
        self._store.put(key=key, value=dict(bar))
        return 'stored'


@dataclass(frozen=True)
class DeliveryResult:
    processing: ProcessResult | None
    persistence: str
    # Confirms a successful put or matching value in a caller-reconciled store.
    # An existing-value read is not a new fsync acknowledgement.
    storage_confirmed: bool = False
    confirmed_next_cursor_ms: int | None = None
    fenced: bool = False
    error: str | None = None
    write_acknowledged: bool = False


@dataclass(frozen=True)
class BatchResult:
    fetched: object | None
    deliveries: tuple
    complete: bool
    fenced: bool


class OfflineBarPipeline:
    """Owns fresh processor state; borrows a clean, exclusively owned store.

    Never reuse its processor after a fence. Instantiate a new pipeline against
    a reopened/reconciled engine and replay from trusted registration cursors.
    """
    def __init__(self, store, *, fetcher=None, processor_options=None):
        self._adapter = AcceptedBarStore(store)
        self._processor = BarProcessor(**(processor_options or {}))
        self._fetcher = fetcher
        self._confirmed = {}
        self._fenced = False
        self._quarantine = None

    @property
    def fenced(self):
        return self._fenced

    @property
    def quarantine(self):
        if self._quarantine is None:
            return None
        return tuple(dict(bar) for bar in self._quarantine)

    def register_stream(self, **kwargs):
        if self.fenced:
            raise RuntimeError('pipeline fenced; rebuild/replay required')
        stream = self._processor.register_stream(**kwargs)
        self._confirmed[stream] = kwargs['start_time_ms']
        return stream

    def snapshot(self, stream):
        return dict(processor=self._processor.snapshot(stream),
                    confirmed_next_cursor_ms=self._confirmed[stream], fenced=self.fenced)

    def deliver(self, event, *, now_ms):
        if self.fenced:
            return DeliveryResult(None, 'fenced', fenced=True,
                                  error='reopen storage and rebuild/replay before retry')
        decision = self._processor.process(event, now_ms=now_ms, replay=True, model=None)
        confirmed = self._confirmed.get(decision.stream)
        if decision.outcome != 'accepted':
            return DeliveryResult(decision, 'not_attempted',
                                  confirmed_next_cursor_ms=confirmed)
        try:
            persistence = self._adapter.persist(event, decision)
        except StoredBarConflict as error:
            self._fenced = True
            self._quarantine = (error.existing, error.candidate)
            return DeliveryResult(decision, 'conflict', confirmed_next_cursor_ms=confirmed,
                                  fenced=True, error=str(error))
        except BaseException as error:
            # Also fence if interrupted after acceptance. Ordinary storage errors
            # are returned; process-control exceptions are re-raised after fencing.
            self._fenced = True
            if not isinstance(error, Exception):
                raise
            return DeliveryResult(decision, 'storage_error', confirmed_next_cursor_ms=confirmed,
                                  fenced=True, error=f'{type(error).__name__}: {error}')
        self._confirmed[decision.stream] = decision.next_cursor_ms
        return DeliveryResult(decision, persistence, True, decision.next_cursor_ms,
                              write_acknowledged=persistence == 'stored')

    def fetch_and_store(self, *, now_ms, **range_args):
        """Process sorted selected bars, retaining fetch errors/gaps in the result.

        now_ms is caller-supplied processing-time evidence, separate from the
        fetcher's request-start evidence. No automatic retry/backfill occurs here.
        """
        if self.fenced:
            return BatchResult(None, (), False, True)
        if self._fetcher is None:
            raise ValueError('an explicitly injected fetcher is required')
        fetched = self._fetcher.fetch(**range_args)
        if fetched.conflicts:
            pair = fetched.conflicts[0]
            self._quarantine = (dict(pair['existing']), dict(pair['candidate']))
            self._fenced = True
            return BatchResult(fetched, (), False, True)
        deliveries = []
        for bar in fetched.bars:
            delivery = self.deliver(bar, now_ms=now_ms)
            deliveries.append(delivery)
            if self.fenced:
                break
        complete = fetched.complete and not self.fenced and all(
            d.storage_confirmed or (d.processing is not None and d.processing.outcome == 'duplicate')
            for d in deliveries)
        return BatchResult(fetched, tuple(deliveries), complete, self.fenced)
