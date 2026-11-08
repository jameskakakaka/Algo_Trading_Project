# Phase 3A.4 — reproducible offline finalized-bar storage integration

## Architecture and opt-in interface

Synthetic injected HTTP -> FinalizedBarFetcher -> validated MARKET_BAR_V1 ->
BarProcessor (replay only) -> AcceptedBarStore -> injected get/put store.
Integration tests supply real LSMTreeEngine instances in TemporaryDirectory.
No existing module is changed, no service starts on import, and no live entry
point, model, inference callback or trading execution interface is present.

```python
with TemporaryDirectory() as directory:
    engine = LSMTreeEngine(data_dir=directory)
    try:
        pipeline = OfflineBarPipeline(engine, fetcher=synthetic_fetcher)
        stream = pipeline.register_stream(
            exchange='binance', symbol='BTCUSDT', timeframe='1m',
            start_time_ms=1800000000000,
        )
        result = pipeline.fetch_and_store(
            now_ms=trusted_processing_time_ms,
            exchange='binance', symbol='BTCUSDT', timeframe='1m',
            start_time_ms=1800000000000, end_time_ms=1800000180000,
        )
    finally:
        engine.wal.close()
```

Supply standard-library synthetic client/clock/sleep implementations as in
`tests/test_offline_pipeline.py`. The harness has no default HTTP transport or
clock and borrows storage lifecycle; it never creates production `./data`.
`deliver(event, now_ms=...)` also supports explicit deliveries/backfill/replay.
The processing time and fetch request-start evidence are distinct caller inputs.
Schema/fetcher finality and clock assumptions remain unchanged.

`OfflineBarPipeline` constructs fresh owned processor state, accepts processor
configuration, and forwards explicit stream registration. All deliveries force
`replay=True, model=None`: no inference or paper action is performed. A caller
must exclusively own the processor/store and not mutate storage outside this
single-threaded harness. This is neither a transaction manager nor a broker
consumer. Storage and processor interfaces are reused, not reimplemented.

## Adapter and outcome semantics

`AcceptedBarStore.persist` revalidates an event and requires a matching accepted
processor result/key. It cannot accept gap, duplicate, conflict, out-of-order,
rejected or deferred outcomes. Canonical decimal strings and composite v1 string
keys pass unchanged to LSM. Stored dictionaries are copied before put so caller
mutation cannot modify LSM memory outside its API.

Before put, the adapter reads the key:

- Absent: call put once; return `stored` only after successful return.
- Matching canonical market content: return `already_stored`, without put.
  Existing operational metadata is preserved, even if replay metadata differs.
- Different content: raise StoredBarConflict; never overwrite; retain both bars.
- Invalid existing value/identity: fail closed with StoredBarIntegrityError.

The namespace is dedicated exclusively to valid v1 bars. LSM get returns None
for both absence and stored null; the public API cannot distinguish them. Stored
null violates this namespace precondition and cannot be detected as corruption
by this adapter. Shared arbitrary-value/legacy directories need separate audit
and migration; this layer does not solve null presence or legacy collisions.
get-then-put is safe only under the existing single-writer ownership assumption;
it is not atomic compare-and-set and provides no concurrent writer protection.

A DeliveryResult separates `processing` from `persistence`:

| Persistence | Meaning |
| --- | --- |
| stored | Put returned successfully; write_acknowledged=true |
| already_stored | Existing matching content reconciled; no new write/fsync acknowledgement |
| not_attempted | Processor did not accept; no adapter read/write |
| conflict | Accepted in memory but disagreed with stored content; pipeline fenced |
| storage_error | Adapter read/validation/write failed; pipeline fenced |
| fenced | Previously fenced; no processor or storage work performed |

`storage_confirmed` is true only for stored/already_stored. It is NOT a Kafka
commit or a claim that a read establishes fresh durability. `write_acknowledged`
is true only after this call's successful put. Existing content relies on the
caller's clean, reconciled store and the original engine durability assumptions.
No successful durability result is returned from the failing delivery.

Per-stream `confirmed_next_cursor_ms` begins at the trusted replay start and
advances only after accepted content is written or found matching. It remains
unchanged on storage failure. It is an in-memory reconciled-prefix cursor, not a
persisted recovery checkpoint. `snapshot` shows both processor and confirmed
cursors so their divergence after failure is explicit.

Known processor duplicates skip adapter calls entirely. Unrecognized old events
remain out_of_order; they are not silently promoted to duplicates. Retained
processor conflicts quarantine/fence only their stream using its existing
snapshot contract. Storage-level conflicts instead fence the whole pipeline,
since its processor has already accepted inconsistent content. The pipeline
quarantine property returns copies of its first stored/fetch conflict pair.

## Fetch batches, gaps, and completeness

Fetcher output is already sorted, normalized and deduplicated; the harness does
not duplicate that logic. A fetch-level conflict conservatively fences the whole
pipeline before delivering any of that batch, including otherwise valid prefix
bars. The full FetchResult remains available in BatchResult for inspection.

Otherwise selected bars are delivered in fetched order. A missing interval makes
the processor report gap for later bars; those never reach storage. Backfill
from the confirmed cursor in ascending order and resubmit future bars. The
existing processor recovery watermark prevents silently skipping the gap.
A later fetch/processing/storage failure does not roll back an already successful
prefix. BatchResult.complete requires fetch completeness, no global fence and
storage-confirmed deliveries or known duplicates; it describes the requested
batch, not all registered history or an atomic multi-key transaction. Fetch
errors/deferred bars/gaps remain explicit even when a valid prefix is stored.
There is no automatic backfill/retry loop in the harness.

## Acceptance before persistence: failure protocol

Counterexample: processor accepts open T and moves to T+interval, then put raises.
Retrying in the same processor could be classified duplicate without storing T.
Therefore any adapter exception fences the entire harness immediately. The
accepted ProcessResult is diagnostic only; storage_confirmed remains false and
the confirmed cursor does not advance. Every subsequent delivery is refused,
and fenced fetch calls do not touch HTTP. Process-control interruptions during
persistence also fence before being re-raised. No in-place unfence exists.

Recovery requires explicit external action:

1. Stop using the old pipeline/processor. Close the engine's WAL handle.
2. Reopen the engine, allowing its WAL/table recovery contract to apply. The
   attempted write may be absent or present; exceptions do not guarantee rollback.
3. Inspect/reconcile uncertain content with authoritative validated history.
   A readable recovered record does not prove a failed fsync completed. If
   synchronization was uncertain, durably republish recovered state using the
   existing flush_to_sstable API (or another separately verified synchronization
   procedure) before treating reads as durable reconciled evidence. Failure of
   recovery/synchronization must stop this procedure too.
4. Construct a NEW pipeline/processor over the clean reconciled engine. Register
   trusted replay starts and replay validated history chronologically. Matching
   keys rebuild memory without writes; absent keys are written; mismatches fence.
5. Do not resume from the old processor's advanced cursor or blindly reset from
   the failed event. Rebuild enough history for contiguous state and review any
   quarantined conflict before reuse.

The borrowed-store protocol cannot mechanically verify that a caller reopened
or synchronized correctly; it is an explicit recovery precondition. Reusing the
same fenced harness is mechanically blocked. After actual machine power loss,
recovered visible state depends on the storage contracts/filesystem, not this
harness. The real-fsync-failure test explicitly synchronizes recovered state.

## Exact storage guarantees and limits

Successful put inherits Phase 2's synchronized WAL append and threshold flush
publication under its single-writer, immutable-value and filesystem assumptions.
The harness adds semantic no-overwrite and no-extra-write checks; it changes no
WAL/SSTable format. Tests span threshold flush, reopen, exact composite keys,
canonical decimal content, and complete/absent uncertain write outcomes.
They do not establish hardware power-loss safety, transactional batch atomicity,
thread safety, durable checkpoints, persistent quarantine or deduplication after
arbitrary restart. Storage compaction, media corruption, legacy data repair,
external table deletion and disk exhaustion remain existing engine limitations.

Processor state retains its configured bounds; pipeline adds one cursor per
registered stream and one conflict pair. Fetch/batch results are bounded by
fetcher range/page limits but retained result memory is caller-controlled.
Previously confirmed values cannot be retracted by later conflicts. No exactly-once
processing/delivery guarantee is claimed.

## Phase 3B boundary

Kafka integration must define explicit groups/partitions, offset handling,
producer acknowledgements, durable replay starts/checkpoints and quarantine,
rebalance ownership and crash/replay ordering. In-memory acceptance or a returned
LSM result is not a Kafka offset commitment; no transaction spans them. ML and
trading adapters remain disabled and require their own reviewed contracts.

Verification: `python3 -B -m unittest discover -s tests -v`.
