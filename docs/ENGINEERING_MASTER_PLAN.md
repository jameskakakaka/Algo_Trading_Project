# Engineering master plan

Scope: smallest coherent offline-first research and storage system. No real orders, exchange requests, service startup, dependency installation, commits or publication.

## A: Repository audit

- Status: VERIFIED
- Defects: README overclaims; old entry points bypass v1; dependencies absent.
- Scope / proposal / non-goals: Inspect all modules, baseline and history; no remote access.
- Acceptance: Inventory and baseline recorded.
- Verify: `python3 -B -m unittest discover -s tests -v`.
- Risks / migration: Preserve three pre-existing untracked pipeline files.

## B: Finalized-bar integration

- Status: VERIFIED
- Defects: Acceptance precedes storage; restart reconstruction needed.
- Scope / proposal / non-goals: Reuse supplied offline pipeline with real LSM; no migration.
- Acceptance: Failure fencing, duplicate/conflict/gap tests pass.
- Verify: `python3 -B -m unittest discover -s tests -p test_offline_pipeline.py`.
- Risks / migration: Dedicated v1 storage namespace; caller replay prerequisites.

## C: Kafka transport

- Status: BLOCKED
- Defects: Legacy auto offsets; no observed acknowledgements.
- Scope / proposal / non-goals: Versioned adapters, explicit replay/groups/commits; fake verification.
- Acceptance: Crash windows, poison and replay tested; broker separately blocked.
- Verify: `python3 -B -m unittest discover -s tests -p test_kafka_transport.py`.
- Risks / migration: Kafka unavailable; single-partition replay policy; no exactly once.

## D: ML validity

- Status: BLOCKED
- Defects: Labels, feature parity and timeframe mismatch; no valid dataset.
- Scope / proposal / non-goals: Shared bounded feature spec, walk-forward research and artifacts.
- Acceptance: Parity, purged folds, metadata rejection; performance remains blocked.
- Verify: `python3 -B -m unittest discover -s tests -p test_research.py`.
- Risks / migration: No ML dependencies or reviewed market dataset.
Verified implementation: shared features, purged evaluation, metadata and logistic fixture path. Blocker: XGBoost dependencies and reviewed real data unavailable; no market performance result.

## E: Execution safety

- Status: VERIFIED
- Defects: Old bot active by default; no account simulator.
- Scope / proposal / non-goals: Disable legacy activation; deterministic isolated paper ledger.
- Acceptance: Default disabled; replay/stale/duplicate checks and fees tested.
- Verify: `python3 -B -m unittest discover -s tests -p test_paper.py`.
- Risks / migration: Simulator state restore required; no real orders.

## F: Storage integration/performance

- Status: VERIFIED
- Defects: No reproducible benchmark.
- Scope / proposal / non-goals: Preserve engine; temporary single-writer benchmark.
- Acceptance: Storage regression plus benchmark with environment recorded.
- Verify: `python3 -B -m tools.benchmark --records 200`.
- Risks / migration: Synthetic local performance only; no HFT claim.

## G: Maintainability

- Status: VERIFIED
- Defects: No package manifest; import-time backtest fetch.
- Scope / proposal / non-goals: Lightweight packaging, guarded legacy tools and safe configuration.
- Acceptance: Offline imports, compile and quality check.
- Verify: `python3 -B -m tools.check`.
- Risks / migration: Do not silently migrate legacy payloads/models.

## H: Security/release audit

- Status: VERIFIED
- Defects: Open Compose ports; history not screened.
- Scope / proposal / non-goals: Read-only content/history scan; safe env and localhost config.
- Acceptance: Locations-only report and owner release checklist.
- Verify: `python3 -B -m tools.security_audit`.
- Risks / migration: Heuristic scan cannot certify absence or dependency vulnerabilities.

## I: End-to-end demo

- Status: VERIFIED
- Defects: No recommended demo command.
- Scope / proposal / non-goals: Synthetic REST through real pipeline, restart, features and compatibility.
- Acceptance: Network-free deterministic smoke passes.
- Verify: `python3 -B -m tools.demo`.
- Risks / migration: Synthetic evidence is not profitability.

## J: Testing/CI

- Status: VERIFIED
- Defects: No CI or captured completion evidence.
- Scope / proposal / non-goals: Verification runner and GitHub Actions offline job.
- Acceptance: Full regression and smoke locally; remote CI unverified.
- Verify: `python3 -B -m tools.verify`.
- Risks / migration: CI not run remotely; supported Linux filesystem assumptions.
Local hierarchy verified; remote CI run is unverified and requires owner publication/authorization.

## K: Portfolio/handoff

- Status: VERIFIED
- Defects: Misleading README and missing handoff.
- Scope / proposal / non-goals: Accurate docs, evidence, allowlisted review archive.
- Acceptance: Inventory and archive verified; blockers explicit.
- Verify: `python3 -B -m tools.review_archive`.
- Risks / migration: Owner approval required before any publication.


## Final dependencies and acceptance boundary

C is implemented and fake-tested, but live client/broker validation is blocked by absent optional dependencies and lack of authorized service startup. D has a verified standard-library research path, but XGBoost and real-data performance remain blocked. Neither is claimed fully verified. No milestone is blocked by a hidden code failure in the observed offline suite.

Acceptance summary: AC1 architecture, AC2 finalized-bar correctness, AC3 recovery integration, AC5 existing storage, AC7 disabled execution, AC8 offline reproducibility, AC9 failure handling, AC10 visible security conditions, AC11 documentation and AC12 evidence are verified to their documented local scope. AC4 live Kafka and AC6 genuine model/backend validation are BLOCKED; their offline contracts/tests are verified. All release/publication actions require owner review.

Prioritized residual risks: (1) single-writer ownership and recovery/namespace preconditions are operational; (2) Kafka retained-prefix availability and real rebalance timing unverified; (3) no real-market or XGBoost evidence; (4) optional dependency/image vulnerabilities not certified; (5) no hardware power-loss, large-scale benchmark, multihost or remote CI validation.
