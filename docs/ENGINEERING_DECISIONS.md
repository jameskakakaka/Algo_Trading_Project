# Engineering decisions

1. Preserve verified storage and supplied offline integration. No WAL/table migration, engine rewrite or optimization without evidence. Existing randomized and fault tests remain intact.
2. Use an offline-first recommended path with injected sources and standard-library core. Optional services and ML packages do not block basic reproducibility.
3. Fail closed after acceptance/persistence divergence. Rebuild/replay instead of rolling back an in-memory cursor whose durable effect is unknown.
4. Prefer at-least-once Kafka with explicit full-history reconstruction over pretending offset commits checkpoint feature/processor state. Local one-partition limitation is explicit; no elastic multi-writer architecture.
5. Adopt 1m modeling as an explicit policy, matching finalized ingestion. Existing 15m models are incompatible. The bounded 60-bar feature spec eliminates hidden train/live initialization differences.
6. Use purged walk-forward and an untouched final holdout. Keep a simple deterministic logistic/majority baseline; optional XGBoost is not evidence until actually run on reviewed data.
7. Retire unsafe paper activation and import-time backtesting while retaining legacy sources. New JSON models avoid implicit pickle loading. No real-order implementation is introduced.
8. Keep PaperAccount independent and disabled. Replay, stale/incomplete state and duplicate signals cannot produce additional fills. Explicit snapshots contain cash, quantity, seen IDs and fills; persistence is caller-owned and snapshots are not trusted authentication tokens.
9. Bind Docker ports to loopback. Single plaintext broker and ZooKeeper images are local demonstration configuration, not a secure deployment or HA claim. Image/dependency audit is owner work before broader use.
10. Prefer dependency-free parse/import/compile checks and reproducible tests to a cosmetic formatting rewrite. Third-party lint/static typing and cryptographically pinned CI actions may be added after owner review.
