# Architecture and ownership

## Recommended execution path

`python3 -B -m tools.demo` is authoritative. `tools.fixtures.FixtureHTTP` supplies deterministic 12-field REST rows to `FinalizedBarFetcher`. Request-start `TimeEvidence`, uncertainty and safety delay govern finalization. `schemas.data_types` validates MARKET_BAR_V1, preserving decimal strings and exchange/market/symbol/timeframe/open identity.

`OfflineBarPipeline` owns `BarProcessor` and confirmed cursors, borrowing an exclusively owned clean `LSMTreeEngine`. Only contiguous accepted results reach `AcceptedBarStore`. Existing identical content reconciles without rewriting; conflicts never overwrite. Operational metadata does not define market content. Processor conflicts quarantine a stream; storage/fetch uncertainty fences the whole pipeline. No in-place unfence exists.

A failed store may have persisted the attempted write. Stop, close, reopen, reconcile/synchronize uncertain recovered state, construct a fresh pipeline, register trusted history starts, and replay chronologically. Never resume from an unconfirmed in-memory cursor. The existing supplied [offline integration contract](../streaming/OFFLINE_PIPELINE.md) states detailed preconditions. The bar namespace must exclusively hold valid non-null v1 bars; arbitrary legacy/shared values are unsupported.

`ResearchPipeline` adds one shared feature row only after storage-confirmed acceptance. Duplicates add none. Explicit prediction checks durable cursor alignment, unresolved gaps, conflicts, warmup, freshness, replay flag and artifact metadata. Storage failures fence feature processing. Replay always defaults to blocked inference. Caller-provided processing time must be trustworthy; a stale clock is not corrected by software.

## Storage

Typed WAL -> MemTable -> v2 generation SSTables. Synchronization precedes durable acknowledgement; whole-table publication precedes WAL retirement. Automatic compaction is disabled. Manual full compaction publishes a newer durable summary before deleting inputs. Existing storage-specific contracts and regression tests remain authoritative. Values must not be externally mutated. Single-writer ownership is an operational assumption, not an enforced multi-process lock.

## Kafka

The optional path sends validated v1 events on `market-bars-v1`, with stable logical-stream keys, one partition for the local demo, observed acknowledgements and bounded producer retries. Consumer groups are explicit; automatic commits are disabled. Storage precedes synchronous offset+1 commits. Stop-on-poison policy retains evidence in Kafka and fences, requiring operator reconciliation. No skipped record is declared successful.

Every new session seeks retained beginning and reconstructs from trusted stream starts. Commits record progress but cannot replace historical feature/processor state. Rebalance revocation stops the session. Retention loss manifests as missing-prefix or offset-continuity failure; an empty/expired topic cannot certify completeness and the finite demo raises if expected records are missing. There is no distributed transaction or exactly-once claim. See KAFKA_RECOVERY.md.

## ML and execution

Recommended timeframe is 1m. Offline and streaming share `bounded-indicators-v1`, a fixed trailing 60-bar policy with documented seeds. JSON artifacts bind stream, feature order, preprocessing, warmup, configuration and dataset provenance. No legacy pickle loading occurs in the recommended path. Training uses expanding purged folds and an untouched chronological holdout. PaperAccount is separate and disabled by default; no inference callback automatically invokes it. No real order interface exists.

## Legacy boundaries

Legacy float raw_market_data, CSV downloaders, ta features, train scripts and paper bot are not interchangeable with v1. Direct entry points are disabled except the compatibility-only data-lake worker API. Their old sources remain for reference, with no automatic model/data migration. New integrations use finalized_bars, offline_pipeline, kafka_transport, research_pipeline and ai_op.research. Broker service and XGBoost runtime verification remain blocked.
