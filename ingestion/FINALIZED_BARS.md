# Phase 3A.2 — isolated finalized REST bar selection

`ingestion.finalized_bars` is opt-in. Neither legacy fetcher is changed or wired
to it. It has no default HTTP client, clock, sleep implementation, network call,
Kafka dependency, or executable entry point. Importing it has no side effects.
The v1 contract remains unchanged.

## REST structure and UTC boundaries

A REST kline must be an exact 12-element JSON list:

| Index | Meaning | Required type |
| --- | --- | --- |
| 0 | Open timestamp, Unix milliseconds | strict int |
| 1–4 | Open, high, low, close | exact decimal strings |
| 5 | Base volume | exact decimal string |
| 6 | Inclusive close timestamp | strict int |
| 7 | Quote volume | nonnegative decimal string |
| 8 | Trade count | nonnegative strict int |
| 9–10 | Taker buy base/quote volume | nonnegative decimal strings |
| 11 | Ignored exchange field | nonnegative decimal string |

Booleans are not integers. Decimal validation uses v1 bounds and canonicalization.
OHLC, identity, and timestamp checks delegate to the existing v1 validator.
Open times are aligned UTC multiples of 60,000 or 900,000 for 1m or 15m.
Close must equal `open + duration - 1`; the normalized exclusive end is close + 1.
Unsupported interval, exchange, market, malformed row, or invalid OHLC cannot be
coerced into a valid bar. `parse_kline` returns market fields without a finality
marker or operational timestamps. Its internal structural validation uses
synthetic post-end metadata, discarded before returning the candidate.

## Finality assumptions and injected evidence

`TimeEvidence(now_ms, uncertainty_ms)` represents a fresh exchange UTC estimate
at HTTP request initiation, with an absolute error bound. The caller must provide
an honest clock, including synchronization, drift, and evidence-age uncertainty.
No exchange-time service is called or implemented here.

For every HTTP attempt, evidence is captured BEFORE calling the transport. A
returned candidate is selectable only if:

`request_start_estimate - uncertainty >= exclusive_end + safety_delay`

Defaults: 2,000 ms safety delay; at most 500 ms uncertainty. Excessive uncertainty
stops before HTTP and returns an explicit error. A pre-close fetch remains
ineligible even if the request finishes after close. Retries obtain fresh
pre-request evidence. Equality at the safety boundary is accepted. The policy
assumes a fresh REST response (no stale transport cache), accurate stated clock
bounds, and exchange data availability after the chosen delay. It cannot prove
that the exchange will never correct history. No actual exchange behavior was
verified using network access.

`observed_at_ms` records the request-start estimate. `published_at_ms` initially
has the same value as a schema-compatible preparation placeholder: NO publication
occurs here. A future publisher must replace it with consistent publication
metadata. Event IDs do not depend on either field.

## Interface and transport contract

```python
fetcher = FinalizedBarFetcher(injected_client, injected_clock, injected_sleep)
result = fetcher.fetch(
    exchange='binance', market='spot', symbol='BTCUSDT', timeframe='1m',
    start_time_ms=1800000000000, end_time_ms=1800000180000,
)
```

The client implements `get(url, params=..., timeout=(connect_seconds,
read_seconds))`, returning `status_code`, a `headers` mapping, and `json()`.
Timeouts raise standard `TimeoutError`, connection failures `OSError`, and invalid
JSON `ValueError`. A future requests/other client adapter must translate its
exceptions and honor the timeout. Unexpected programming/interface errors
propagate rather than being disguised as exchange failures. Caller configuration
errors raise before fetching; operational failures appear in the result.

Timeout defaults are 3s connect / 10s read per attempt. Retries default to two
(three attempts total), with capped exponential delays. Only timeout/connection
failures, 429, and 500/502/503/504 retry. Other statuses, malformed JSON/shape,
and invalid rows fail explicitly. Numeric Retry-After seconds are honored within
the configured wait budget (default 30s). Longer or unsupported/date-form headers
stop and report deferral rather than retrying too soon. Transport adapters must
honor timeout and disable hidden retries; this interface cannot forcibly interrupt
an arbitrary blocking injected client. There is no separate total elapsed-time
deadline. Attempts, pages, range size, and sleeps are bounded.

## Pagination, overlap, results, and cursor

The aligned positive range `[start_time_ms, end_time_ms)` specifies expected bar
opens, not response observation times. Both endpoints must satisfy the v1 domain.
Default limits: 1,000 rows/page, 1,000 pages, 100,000 expected bars. Each forward
request sends UTC timezone, startTime=scan, endTime=exclusive_range_end-1. Page
responses may be out of order; sort them before selection. Advance the scan to
maximum returned open + interval. Do not infer completeness from a short page.
Empty pages stop; a page that cannot advance scan reports non-progress. An
exhausted page budget reports failure. Rows outside the overall requested range
fail the page; earlier rows within that range are accepted as server overlap.

All rows in a page are validated before any row from that page is accepted.
Previously accepted pages survive later failures. Identity/content comparison
uses the v1 classifier. Duplicate occurrences are counted in `duplicates` as
repeated event IDs. Conflicting finalized values remove that identity from
selected output and retain both variants in `conflicts`; subsequent occurrences
cannot restore the quarantined bar. Unfinished snapshots are deferred rather
than compared as finalized conflicts. Deduplication is local to one fetch call;
repeated calls intentionally yield the same deterministic identities.

`FetchResult` fields:

- `bars`: validated, unique, nonconflicting selected bars sorted by open time.
  May include bars beyond a gap, for inspection/backfill, not sequential inference.
- `duplicates`: one event ID per duplicate occurrence.
- `conflicts`: first conflicting pair per identity, with event ID and both bars.
- `deferred`: opens observed but not safely post-close; sorted and unique.
- `gaps`: expected opens absent from selected/deferred/conflict categories. After
  a failed scan these include unexamined intervals, not proven exchange omissions.
- `errors`: explicit failure reasons; partial output is never labeled success.
- `requests`: transport attempts, including retries.
- `next_cursor_ms`: first unresolved open in the contiguous selected prefix,
  or range end. It stops at missing, deferred, or conflicting intervals.
- `complete`: all requested intervals selected, no errors, and no conflicts.

No missing candles are synthesized. A caller can resume/backfill by supplying
next_cursor_ms as the next range start. If a later request finds a conflict,
selection and cursor are recomputed before returning. This is an in-memory
selection cursor only. Callers must inspect errors/completeness, and must not
persist it as a publication acknowledgement. No cross-call reconciliation or
previous-history lookup is implemented.

## Compatibility and Phase 3B boundary

Legacy float payloads and CSVs are neither converted nor activated. The v1
contract's identity, decimal strings, and explicit timestamps require reviewed
adapters for existing Kafka, ML and storage consumers. Model timeframe alignment
remains separate. Existing timestamp-only storage is untouched.

Phase 3B must supply a reviewed transport/clock integration, durable cursor
persistence, producer acknowledgements, replay after uncertain publication,
consumer idempotency/checkpoints, and crash/rebalance recovery. Broker retries
and restart duplicates remain possible. No exactly-once delivery is claimed.

Offline regressions: `python3 -B -m unittest discover -s tests -v`.
