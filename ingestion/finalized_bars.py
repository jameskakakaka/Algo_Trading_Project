"""Offline-facing Binance REST adapter; no default transport or live entry point.

See FINALIZED_BARS.md for injected interfaces and finality assumptions.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import math

from schemas.data_types import (
    BarValidationError, INTERVAL_MS, MIN_TIME_MS, MAX_TIME_MS,
    classify_bar_events, generate_event_id, normalize_decimal,
    normalize_supported_value, validate_finalized_bar,
)


@dataclass(frozen=True)
class TimeEvidence:
    """Exchange UTC estimate at request start and its absolute error bound."""
    now_ms: int
    uncertainty_ms: int = 0

    def __post_init__(self):
        if type(self.now_ms) is not int or not MIN_TIME_MS <= self.now_ms < MAX_TIME_MS:
            raise ValueError('invalid clock timestamp')
        if type(self.uncertainty_ms) is not int or self.uncertainty_ms < 0:
            raise ValueError('invalid clock uncertainty')


@dataclass
class FetchResult:
    bars: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    deferred: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    complete: bool = False
    next_cursor_ms: int = 0
    requests: int = 0


def parse_kline(row, *, exchange, market, symbol, timeframe):
    """Validate all 12 REST fields, returning canonical market fields only.

    Synthetic post-end metadata is used only to reuse structural schema checks;
    this function does not select or return evidence of finality.
    """
    if type(row) is not list or len(row) != 12:
        raise BarValidationError('kline must be a 12-field JSON array')
    for index in (0, 6, 8):
        if type(row[index]) is not int:
            raise BarValidationError(f'kline[{index}] must be integer')
    if row[8] < 0:
        raise BarValidationError('negative trade count')
    for index in (1, 2, 3, 4, 5, 7, 9, 10, 11):
        value = normalize_decimal(row[index])
        if Decimal(value) < 0:
            raise BarValidationError(f'negative kline[{index}]')
    end = row[0] + INTERVAL_MS[timeframe]
    if row[6] != end - 1:
        raise BarValidationError('incompatible inclusive close time')
    candidate = validate_finalized_bar(dict(
        schema_version=1, event_type='market.bar.finalized',
        event_id=generate_event_id(exchange, market, symbol, timeframe, row[0]),
        exchange=exchange, market=market, symbol=symbol, timeframe=timeframe,
        open_time_ms=row[0], end_time_ms=end, is_final=True,
        **dict(zip(('open', 'high', 'low', 'close', 'volume'), row[1:6])),
        observed_at_ms=end, published_at_ms=end, source='binance_rest',
    ))
    for field_name in ('schema_version', 'event_type', 'is_final',
                       'observed_at_ms', 'published_at_ms'):
        del candidate[field_name]
    return candidate


class FinalizedBarFetcher:
    """Injected client.get(url, params=..., timeout=(connect, read)) returns
    a response with integer status_code, headers mapping and json() method.
    Transport timeouts must raise TimeoutError; connection failures OSError.
    clock() returns fresh TimeEvidence before each attempt. sleep(seconds) is
    injected too. No third-party imports or network-capable defaults exist.
    """
    URL = 'https://api.binance.com/api/v3/klines'

    def __init__(self, client, clock, sleep, *, page_size=1000, max_pages=1000,
                 max_bars=100_000, safety_delay_ms=2000, max_uncertainty_ms=500,
                 timeout=(3.0, 10.0), retries=2, retry_delay_s=1.0,
                 max_retry_delay_s=30.0):
        for name, value, minimum, maximum in (
            ('page_size', page_size, 1, 1000), ('max_pages', max_pages, 1, 100_000),
            ('max_bars', max_bars, 1, 1_000_000), ('retries', retries, 0, 10),
            ('safety_delay_ms', safety_delay_ms, 0, 86_400_000),
            ('max_uncertainty_ms', max_uncertainty_ms, 0, 86_400_000),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f'invalid {name}')
        if (type(timeout) is not tuple or len(timeout) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in timeout)):
            raise ValueError('timeout requires positive finite connect/read seconds')
        for value in (retry_delay_s, max_retry_delay_s):
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('retry delay must be finite and nonnegative')
        self.client, self.clock, self.sleep = client, clock, sleep
        self.page_size, self.max_pages, self.max_bars = page_size, max_pages, max_bars
        self.safety_delay_ms, self.max_uncertainty_ms = safety_delay_ms, max_uncertainty_ms
        self.timeout, self.retries = timeout, retries
        self.retry_delay_s, self.max_retry_delay_s = retry_delay_s, max_retry_delay_s

    def _request(self, params, result):
        for attempt in range(self.retries + 1):
            evidence = self.clock()
            if not isinstance(evidence, TimeEvidence):
                raise ValueError('clock must return TimeEvidence')
            if evidence.uncertainty_ms > self.max_uncertainty_ms:
                result.errors.append('clock_uncertainty: request deferred')
                return None
            result.requests += 1
            retry_after = None
            try:
                response = self.client.get(self.URL, params=params, timeout=self.timeout)
                status = response.status_code
                if type(status) is not int:
                    raise ValueError('invalid HTTP status')
                if status == 200:
                    body = response.json()
                    if type(body) is not list or len(body) > self.page_size:
                        raise ValueError('invalid or oversized REST page')
                    return body, evidence
                reason = f'HTTP {status}'
                if status not in (429, 500, 502, 503, 504):
                    result.errors.append(reason)
                    return None
                retry_after = response.headers.get('Retry-After')
            except (TimeoutError, OSError) as error:
                reason = f'{type(error).__name__}: {error}'
            except ValueError as error:
                result.errors.append(f'invalid_response: {error}')
                return None
            if attempt == self.retries:
                result.errors.append(f'retries_exhausted: {reason}')
                return None
            delay = min(self.retry_delay_s * 2 ** attempt, self.max_retry_delay_s)
            if retry_after is not None:
                try:
                    wait = float(retry_after)
                    if not math.isfinite(wait) or wait < 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    result.errors.append('unsupported Retry-After; retry deferred')
                    return None
                if wait > self.max_retry_delay_s:
                    result.errors.append('Retry-After exceeds wait budget; retry deferred')
                    return None
                delay = max(delay, wait)
            self.sleep(delay)
        return None

    def fetch(self, *, exchange, symbol, timeframe, start_time_ms, end_time_ms,
              market='spot'):
        """Fetch aligned [start,end) bar opens; cursor is next missing open.

        Caller may resume using a prior result's cursor as start_time_ms.
        Cursor is a selection result, NOT a durable publication checkpoint.
        """
        exchange = normalize_supported_value('exchange', exchange)
        market = normalize_supported_value('market', market)
        symbol = normalize_supported_value('symbol', symbol)
        timeframe = normalize_supported_value('timeframe', timeframe)
        step = INTERVAL_MS[timeframe]
        for value in (start_time_ms, end_time_ms):
            generate_event_id(exchange, market, symbol, timeframe, value)
        if end_time_ms <= start_time_ms or (end_time_ms - start_time_ms) // step > self.max_bars:
            raise ValueError('range must be positive and within max_bars')
        result = FetchResult(next_cursor_ms=start_time_ms)
        selected, quarantined = {}, set()
        scan = start_time_ms
        for _ in range(self.max_pages):
            page = self._request(dict(symbol=symbol, interval=timeframe, timeZone='0',
                                      startTime=scan, endTime=end_time_ms - 1,
                                      limit=self.page_size), result)
            if page is None:
                break
            rows, evidence = page
            if not rows:
                break
            try:
                candidates = [parse_kline(row, exchange=exchange, market=market,
                                         symbol=symbol, timeframe=timeframe) for row in rows]
                if any(not start_time_ms <= b['open_time_ms'] < end_time_ms for b in candidates):
                    raise BarValidationError('response outside requested overall range')
            except (BarValidationError, ValueError) as error:
                result.errors.append(f'invalid_page: {error}')
                break  # page atomic: do not accept part of a malformed page
            for bar in sorted(candidates, key=lambda b: b['open_time_ms']):
                opening = bar['open_time_ms']
                if evidence.now_ms - evidence.uncertainty_ms < bar['end_time_ms'] + self.safety_delay_ms:
                    result.deferred.append(opening)
                    continue
                bar.update(schema_version=1, event_type='market.bar.finalized', is_final=True,
                           observed_at_ms=evidence.now_ms, published_at_ms=evidence.now_ms)
                bar = validate_finalized_bar(bar)
                if opening in quarantined:
                    continue
                if opening in selected:
                    classification = classify_bar_events(selected[opening], bar)
                    if classification == 'duplicate':
                        result.duplicates.append(bar['event_id'])
                    else:
                        result.conflicts.append(dict(event_id=bar['event_id'],
                                                     existing=selected.pop(opening), candidate=bar))
                        quarantined.add(opening)
                else:
                    selected[opening] = bar
            next_scan = max(b['open_time_ms'] for b in candidates) + step
            if next_scan <= scan:
                result.errors.append('non_progressing_page')
                break
            scan = next_scan
            if scan >= end_time_ms:
                break
        else:
            result.errors.append('page_budget_exhausted')
        result.bars = [selected[k] for k in sorted(selected)]
        deferred = set(result.deferred)
        result.gaps = [k for k in range(start_time_ms, end_time_ms, step)
                       if k not in selected and k not in quarantined and k not in deferred]
        while result.next_cursor_ms in selected:
            result.next_cursor_ms += step
        result.deferred = sorted(set(result.deferred) - set(selected) - quarantined)
        result.complete = (result.next_cursor_ms == end_time_ms and not result.errors
                           and not result.conflicts)
        return result
