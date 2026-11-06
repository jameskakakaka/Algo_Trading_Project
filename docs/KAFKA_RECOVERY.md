# Kafka delivery and recovery

## Scope and client evidence

The local optional demonstration targets `kafka-python==2.3.3`, one broker, one delete-retained topic partition and one consumer session at a time. No client is installed in the review environment. The optional API smoke test is skipped there. No broker was started. Consumer commit and seek APIs were checked against [upstream 2.3.3 source](https://raw.githubusercontent.com/dpkp/kafka-python/2.3.3/kafka/consumer/group.py); [PyPI](https://pypi.org/project/kafka-python/2.3.3/) confirms the candidate release. Source inspection is not runtime validation. Offset structure construction adapts the installed namedtuple fields, and the runtime enforces the chosen version.

`BarConsumerSession(consumer, pipeline)` now resolves the reviewed client's concrete `TopicPartition` and `OffsetAndMetadata` classes at construction and rejects unavailable/incompatible types before processing. It constructs commit arguments directly from validated native record fields; no tuple fallback or local offset type is permitted. The CLI uses this same direct session without wrapping records. The former permissive `offset_factory` keyword is intentionally removed; callers must use the typed client boundary. Offline tests replace only the type-loader boundary with strict client-shaped fake classes, exercising both direct sessions and the actual CLI path. These tests do not verify a broker.

## Policy

- Topic `market-bars-v1`; delete retention 7 days; one partition and replication factor 1 for demonstration only. Logical-stream key is exchange:market:symbol:timeframe; event identity additionally includes bar open.
- Producer uses acks=all, retries=3, one in-flight request per connection, 5s request/max-block limits and observed future resolution within 10s. A timeout or send error has unknown outcome. Replay identical validated content; never invent a new identity or log unobserved success.
- Group `market-bars-lsm-v1`; automatic commits disabled; no silent offset-reset fallback. One record per poll. Default local consumer session has a 10s request timeout, 6s session timeout and 2s heartbeat interval.
- Initial assignment explicitly seeks retained beginning. Every restart must replay from trusted per-stream starting opens to rebuild continuity and features. Committed offsets are progress evidence, not a sufficient checkpoint. This is deliberately inefficient but simple; broker replay memory is bounded by processor history, while old storage content remains authoritative.
- Retention must cover the full requested reconstruction history. Missing initial bars produce a gap and no commit; offset discontinuities fence. Empty/expired history is incomplete rather than success. Missing unregistered streams cannot be inferred: the owner must provide a complete stream registry and expected coverage.
- Validate bytes, duplicate JSON keys, payload size, schema and partition key before side effects. Poison, conflict, gap, stale future metadata, storage failure or commit failure fences and stops; no skip or dead-letter publication occurs. Retained broker payload and sanitized topic/partition/offset/stage evidence support reconciliation. If broker retention expires, a separate authoritative archive is required.
- A duplicate is committable only if this session already confirmed its content, or restart replay reconciled stored identical content through a fresh processor. A read after uncertain fsync is not fresh durability; reopen and explicitly synchronize/reconcile first as required by the offline pipeline contract.
- Revocation after assignment fences immediately. Even successful reassignment requires a new session. Empty revoke before first assignment is harmless. A second assignment is conservatively refused. Group membership fencing is broker enforcement, not storage multi-writer locking.

## Crash windows and evidence

| Window | Result / recovery | Offline test |
| --- | --- | --- |
| Before storage / invalid input | No commit; stop | poison/key/gap tests |
| During storage | Unknown effect; fence; reopen/reconcile | failure and unknown-write tests |
| Durable storage before commit | Replay finds identical content; no extra write | commit-timeout restart test |
| During commit | Offset may or may not be saved; fence; replay from beginning | uncertain commit test |
| After commit | Still reconstruct history on restart | committed-event restart test |
| Rebalance / retention hole | Stop, no unsafe continuation | assignment/revocation and offset-hole tests |

Delivery is at least once. Application idempotency prevents extra bar writes for proven duplicates; storage synchronization is a separate guarantee. Neither produces exactly-once trading or a transaction spanning Kafka and LSM. Optional live-broker integration is BLOCKED pending owner-authorized environment and dependency setup. The synthetic CLI uses a fresh temporary store per invocation; persistent service orchestration/checkpointing is not implemented.
