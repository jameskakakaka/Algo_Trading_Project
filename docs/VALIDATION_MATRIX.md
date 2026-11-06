# Validation matrix

Baseline: 128 tests passed. Completion: see verification/results.txt for exact current counts and platform. No skipped backend is counted as a passing test.

| Area / criterion | Status | Evidence / boundary |
| --- | --- | --- |
| A / AC1 actual architecture | VERIFIED | inventory, baseline, ARCHITECTURE.md |
| B / AC2-3 finalized/durable integration | VERIFIED | supplied 17 offline integration tests + new end-to-end/feature gates |
| C / AC4 Kafka offline semantics | VERIFIED | fake ack, commit, replay, poison and rebalance tests with real LSM |
| C / AC4 live Kafka | BLOCKED | client absent; no service authorization/run |
| D / AC6 methodology and parity | VERIFIED | shared features, purged labels/folds, train-only scaling, logistic reproducibility tests |
| D / AC6 XGBoost and market performance | BLOCKED | optional libraries and reviewed real dataset absent |
| E / AC7 execution safety | VERIFIED | disabled defaults, legacy bot rejection, replay/stale/dedup/restore tests |
| F / AC5 storage regression | VERIFIED | existing fault, randomized lifecycle, WAL/SSTable/compaction tests unchanged |
| F performance | VERIFIED (synthetic only) | benchmark.txt; no optimization, hardware/mount unspecified |
| G / AC8-9 packaging/lifecycle | VERIFIED locally | stdlib setup, parse/import/compile, regression tests |
| H / AC10 security inspection | VERIFIED within scope | security.txt; heuristic/current/reachable-history only; owner audit pending |
| I / AC8 demonstration | VERIFIED | demo.txt: 160 recovered bars, 101 feature rows, zero external requests by construction |
| J / AC12 local evidence | VERIFIED | unittest.txt and results.txt |
| J remote CI | BLOCKED | workflow not published or run |
| K / AC11 documentation/handoff | VERIFIED for owner review | accurate README, release checklist, archive/manifest |

No exactly-once, WebSocket, profitable strategy, HA, production-scale or hardware power-loss claim is supported. Public release remains owner-controlled.

## Final release-hardening evidence

Typed direct/CLI Kafka commits, pre-processing type rejection, Git-free syntax/import/security commands, strict history/owner gates, archive completeness, safe env inclusion and hash inventories have dedicated regression coverage. Actual final results live in verification/results.txt. Independent clean-extraction runs live in verification/archive/results.txt; those explicitly mark Git history NOT RUN and security INCOMPLETE. No release approval follows from either run.
