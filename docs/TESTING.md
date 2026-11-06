# Testing hierarchy

Run from the repository root with Python 3.11+:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B -m tools.check
PYTHONPYCACHEPREFIX=/tmp/algo-review-pycache python3 -m compileall -q ai_op execution_engine ingestion schemas storage_engine streaming tools tests
python3 -B -m tools.demo
python3 -B -m tools.verify
```

The baseline was 128 passing tests, including 17 supplied untracked offline-integration tests (historical claim: 111). Final exact counts/timings/skips live in [verification/results.txt](verification/results.txt), with individual test outcomes in [verification/unittest.txt](verification/unittest.txt). Do not substitute historical counts for current results.

| Level | Coverage |
| --- | --- |
| Unit | strict schema, identities, processor, indicators, model compatibility, safety gates |
| Component | injected REST/retries, storage lifecycle, fake Kafka acknowledgements/commits, research folds |
| Integration | finalized REST through real LSM, restart replay, durable features |
| Fault/recovery | abrupt subprocess exits, fsync/publication failures, unknown writes, compaction/restart, offset failures |
| End-to-end | tools.demo: actual application interfaces, temporary files, synthetic research, no orders |

All existing regression tests remain. New optional backend tests explicitly skip when kafka-python or XGBoost is absent. They do not silently pass. No live broker, exchange, order endpoint or remote CI was used. Optional Kafka client API inspection is not a broker integration test. Running supplied broker CLI commands requires owner-authorized loopback infrastructure; see REPRODUCIBILITY.md.

GitHub Actions configuration runs the same standard-library hierarchy on Ubuntu/Python 3.11 and 3.12, capturing reports. It was prepared locally but has not run remotely. Linux hard links, atomic replacement and directory fsync assumptions apply; Windows filesystem semantics are not claimed. Import smoke checks cover legacy modules without loading optional libraries or starting services.

Security evidence is a read-only heuristic scan of allowlisted current files and all reachable unique Git blobs. It does not prove absence of secrets, scan unreferenced objects, or certify vulnerable dependencies. Benchmark results are synthetic single-writer observations with disclosed platform and unspecified physical filesystem/hardware, not production/HFT evidence.

## Source archive and release modes

Mandatory `tools.verify`, unit tests, syntax/import checks, compileall, demo and benchmark work in a clean extraction without `.git`. Git whitespace/history checks are explicitly NOT RUN there; missing metadata never falls back to a parent repository or inherited GIT_* variables. Corrupt metadata reports INCOMPLETE. Repository mode retains a strict `git diff --check HEAD` check and scans real reachable history. Both modes report heuristic security clearance as INCOMPLETE and never grant publication authorization.

`python3 -B -m tools.verify --release --owner-review PATH` additionally requires completed real Git-history inspection and an owner attestation matching HEAD and the current source/config/documentation digest. Missing/stale review or missing history causes a nonzero exit. Attestations are never generated automatically. The file is a local owner declaration, not an authenticated signature. See FINAL_RELEASE_HARDENING.md for its format.

New regression tests enforce commit types, direct/CLI Kafka mappings, archive completeness and credential-free configuration, per-file hashes, source-archive execution, Git failure reporting and strict release gates. Final archive execution evidence is retained separately under verification/archive/ so it does not overwrite repository evidence.
