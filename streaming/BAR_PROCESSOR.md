# Phase 3A.3 — offline consumer event correctness

`streaming.bar_processor` is opt-in, standard-library-only and single-threaded.
It imports the v1 contract only, and has no Kafka, exchange, storage, model,
indicator or trading side effects. Existing `raw_market_data` consumers are
unchanged. No live or paper order can be executed by this module.

## Existing behavior and compatibility boundary

`ai_op/feature_engineer.py` and `execution_engine/paper_trading_bot.py` append all
raw deliveries to one deque without identity/content checks or stream isolation.
They independently calculate indicators, rather than sharing a feature stream.
`storage_engine/data_lake_worker.py` uses timestamp-only integer keys. All three
use legacy payloads, not v1. The new processor neither wraps nor activates them.
The default historical-training 15m versus live 1m discrepancy remains unresolved.

## Public interface

```python
from streaming.bar_processor import BarProcessor, ModelSpec, decimal_ohlcv

processor = BarProcessor(window_size=60, history_size=256, max_streams=32,
                         max_age_ms=120_000)
stream = processor.register_stream(
    exchange='binance', market='spot', symbol='BTCUSDT', timeframe='1m',
    start_time_ms=1800000000000,
)
result = processor.process(event, now_ms=trusted_now_ms, replay=True)
# Or process_json(JSON_text, now_ms=..., replay=..., model=...).
view = processor.snapshot(stream)
```

`stream_identity` canonicalizes `(exchange, market, symbol, timeframe)` with v1
identifier normalization. Registration validates an aligned start open and
refuses existing streams or capacity overflow; there is no implicit registration,
eviction, cursor reset or skipping history. The chosen starting point is an
explicit caller trust boundary: continuity before that point is not proven.

`process` validates the complete event before any state mutation, including v1
finality assertions, decimal strings, timestamps and identity. Invalid events
return `rejected`; invalid caller context/configuration raises `ValueError`.
The schema's relaxed end-boundary *classifier* exception does not make invalid
bars eligible for consumer state: such events are rejected before comparison.

`process_json` rejects malformed JSON, duplicate object keys, null payloads,
missing fields and null/float OHLCV rather than filling or coercing them.
`decimal_ohlcv` validates an event and returns exact Decimal values. Decimal
values are not JSON-compatible: preserve the canonical string event for JSON.
No float conversion is provided; a future ML adapter must explicitly manage
float precision, overflow/underflow, feature order and finite numeric checks.

All process results contain outcome, reason, canonical stream, composite storage
key (via v1 `storage_identity`), next cursor when registered, optional missing
range, stale flag, inference eligibility and blocking reasons. Invalid events
lack trustworthy identity and do not get a key. A returned key is not a write
request or authorization to overwrite. Snapshots copy all event dictionaries;
caller mutation cannot change internal state.

## State invariants and transitions

Per stream, cursor is the next expected open. The window is a contiguous,
ascending suffix of accepted bars. History is a bounded cache of accepted
identity/content evidence, keyed by open within the stream. Duplicate checks use
v1 canonical market content, ignoring source/observation/publication changes.
Operational metadata of a duplicate never refreshes the original bar or makes
its old close time fresh.

| Outcome | Condition | State mutation |
| --- | --- | --- |
| accepted | Registered, valid, not future-dated; open equals cursor | Append once to window/history, advance cursor, evict oldest history if needed, update recovery watermark |
| duplicate | Matching identity and market content retained in history | None; never append, infer or re-execute |
| conflict | Retained identity has changed valid market content | Retain first conflicting pair, clear indicator window and permanently fence stream |
| gap | Open exceeds cursor | Raise recovery watermark to maximum observed future end; do not buffer/append event or advance cursor |
| out_of_order | Open below cursor, without retained content evidence | None; never assume duplicate or silently update history |
| rejected | Invalid v1 event or JSON | None |
| deferred | Unregistered stream, future publication metadata, or quarantined stream | None |

All fields are checked before registration lookup or mutation. Actual publication
later than trusted now defers the event; it cannot be accepted as a future bar.
Staleness is orthogonal to outcome: a valid stale contiguous bar can be accepted
for archival/replay/warm-up, but cannot enable inference. An old unknown delivery
is still `out_of_order` even if stale. Known duplicates may be stale, but never
trigger new inference. A conflict affects only its own stream. Once fenced,
further valid events are deferred and cannot overwrite the quarantined pair.

## Recovery and backfill policy

Future events are deliberately not buffered. A gap returns missing open range
`[cursor, delivered_open)` and remembers the furthest delivered exclusive end.
Callers backfill from cursor in ascending order and must resubmit future events.
Backfill bars can extend the continuous prefix, but inference stays blocked
until cursor reaches the recovery watermark, including the previously delivered
future bar. A later, smaller gap cannot lower that watermark. No candles are
synthesized; receiving data beyond a gap cannot advance the contiguous cursor.

Conflict repair is explicit and external: preserve the quarantined pair for
review, reconcile authoritative history, then construct a new processor,
register a trusted replay start and rebuild state in replay mode. There is no
in-place unquarantine or last-write-wins repair. Previously returned acceptance
or external side effects cannot be retracted by this in-memory processor.

After history eviction, older identity/content is unknown. The processor returns
`out_of_order`; it cannot reliably detect duplicates or conflicts for that bar.
A caller needing full-history reconciliation must consult durable evidence in a
later integration. Restarts lose all state and require explicit bootstrap/replay.

## Inference and trading boundary

`replay=True` is the default. `ModelSpec` supplies expected exchange, market,
symbol, timeframe and required warm-up count. A matching timeframe alone is not
sufficient; the full stream must match. No model artifact is loaded or verified.

`inference_ready` can be true ONLY on a newly accepted bar when:

- The call explicitly uses `replay=False`.
- `now_ms - bar.end_time_ms <= max_age_ms` (equality is fresh).
- No unresolved recovery watermark or conflict exists.
- Model metadata is supplied and matches the complete stream.
- The contiguous window contains at least the model's required warm-up count.

Warm-up history may be replayed; a subsequent fresh live bar can qualify after
continuity is restored. Warm-up requirements exceeding window capacity block
forever until configuration is corrected. `now_ms` must be a strict v1-domain
Unix millisecond integer supplied by a trusted caller; uncertainty and clock
synchronization are not independently verified here. Freshness uses market end,
not metadata arrival times. Eligibility is evaluated per call, not a persistent
permission: never reuse a past result as current eligibility.

This module does not calculate indicators or expose an automatic indicator
callback. Snapshot windows are diagnostic state, not permission to calculate or
execute across a gap. Integration must honor acceptance and inference gates.
`paper_trading_enabled` is always false, even when inference is eligible. Model
feature/preprocessing versions, recursive-indicator initialization parity, and
execution safety remain integration responsibilities. The schema cannot prove
exchange finality; upstream Phase 3A.2 evidence remains a trust boundary.

## Bounds and concurrency

Defaults: at most 32 explicitly registered streams, 60 window entries and 256
history entries each. History capacity must cover the window. Each stream also
stores one recovery watermark and at most one two-event conflict pair. No future
bar queue, unbounded gap list or quarantine log exists. Memory is
O(max_streams * (window_size + history_size)), plus bounded conflict evidence.
V1 field lengths/domain bound accepted event sizes. Input JSON decoding and
caller-retained results/snapshots are transient caller-controlled allocations;
transport message-size limits belong to integration. Limits are configurable
positive integers, so operators must select reasonable capacities. No locking
or concurrent-writer safety is claimed.

## Phase 3A.4 integration and Phase 3B recovery

Phase 3A.4 must review adapters to route v1 events, configure stream bootstrap and
freshness, consume outcomes, fetch/resubmit backfills, and retain conflicts for
reconciliation. Only accepted events may extend downstream feature state; gaps
must suppress inference and conflicts must invalidate affected feature state.
A validated historical event can be stored without triggering predictions or
trades. Composite keys need migration from legacy timestamp-only keys. Future
ML adaptation needs verified model metadata and feature parity tests; the
current bot's raw-event path must not be activated implicitly.

Phase 3B owns durable deduplication/quarantine, cursor and feature-state recovery,
Kafka offset coordination, publication acknowledgements, and crash/rebalance
handling. In-memory acceptance is not a durable commit, and duplicate evidence
is bounded. No durable or end-to-end exactly-once processing is claimed.

Tests: `python3 -B -m unittest discover -s tests -v`.
