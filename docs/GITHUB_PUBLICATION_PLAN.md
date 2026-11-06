# GitHub publication plan

Prepared from the actual local repository on 2026-11-05. This is an owner-reviewed publication plan, not authorization to stage, commit, push, change visibility, create an attestation, or trade. No external requests, installations or services were used during this pass. Only this release document and regenerated verification evidence change; implementation source and the existing review archive remain preserved.

## A. Current Git state and review identity

- Branch: `feat/end-to-end-project-completion`; HEAD: `84ded6597bf79ed2640fe80e73bcb51911c52b28`.
- No upstream is configured. Index was empty on entry and must remain untouched during this preparation.
- On entry: 37 tracked files, 11 tracked modifications, 53 untracked files, 31 ignored files. Adding this plan makes 54 untracked files: **65 proposed staging paths = 11 modified + 54 added**. No deletions or renames are proposed.
- Fetch and push remote `origin`: credential-free HTTPS endpoint `github.com/jameskakakaka/Algo_Trading_Project`; no URL userinfo, query or fragment found. Remote visibility is **UNVERIFIED**. No GitHub/API/fetch/push request was made.
- Cached `origin/main` and symbolic `origin` point at `1312ed31ad1d9e20360bdc71864695d4ade41bee`. This is stale local evidence, not live remote state. Pushing this branch exposes reachable prior history as well as the new commits.
- 12 reachable commits; 2 author identities and 2 committer identities. Non-noreply email metadata is present. Actual names/email values are intentionally omitted; the owner must review them privately. Default hooks directory has no active non-sample hooks.

Recent commits, already present and **not to be duplicated**:

| Commit | Date | Existing change |
| --- | --- | --- |
| 84ded65 | 2026-11-01 | Per-stream validated bar processor |
| 367335a | 2026-11-01 | Market-bar v1 contract |
| 068e7c0 | 2026-11-01 | Finalized REST bar fetcher |
| fa6288c | 2026-11-01 | Contract hardening |
| 64f7620 | 2026-11-01 | Model-based storage reliability tests |
| c64c79d | 2026-11-01 | Manual full compaction |
| 401911f | 2026-11-01 | Atomic SSTable publication |
| 00e34f3 | 2026-11-01 | Typed keys and null reads |
| 796d42d | 2026-11-01 | WAL replay and synchronized append |
| 62128e5 | 2026-10-28 | Executability and worker fixes |

Storage, schema, finalized-fetcher and processor source/tests already committed at HEAD are retained. No reset, clean, rebase, squash, history rewrite, commit or staging was performed.

### Match to independently verified source

Before creating this plan, current distributable source/configuration/docs matched the last verified source digest:
`adc36cb79680d2ccc152ab44e2964733b775e951c4b1c6850593227f2368583f`.

The existing `review_artifacts/final-release-review.tar.gz` has 92 members; external SHA-256, all manifest hashes and SHA256SUMS hashes verified. Its SHA-256 is `39fe82a5cedcb4a5594db661290ab87f89768be076c08251c6de0a211e11c96a`. On entry its source matched the workspace; differences were confined to four generated files: `docs/verification/{benchmark,results,security,unittest}.txt`.

**This new plan changes the reviewed source digest.** That archive remains valid historical core-review evidence, but does not contain this plan or freshly regenerated reports. Do not describe it as the final publication snapshot. Before a release archive is distributed, rebuild a separately named handoff after the final source/docs/commits and independently verify its manifest, coverage and clean-extraction run. No previous archive is deleted or overwritten in this pass. The current digest belongs in fresh `docs/verification/results.txt`, not a self-referential literal inside this document.

## B. Exact file inventory and inclusion decisions

Categories: A = required distributable source/tooling (not production-readiness certification); B = required tests; C = documentation/license; D = safe configuration; E = verification evidence; F = local-only artifact; G = potentially sensitive material; H = owner review/placeholder. `G1/G2/G3` below identify proposed commits; `KEEP` means already committed and unchanged. Every tracked or nonignored untracked path is listed. All new core modules, the three pre-existing integration files, tools, tests and workflow are explicitly included.

Category counts: A=29, B=17, C=24, D=7, E=13, G=0, H=1. F has 31 observed ignored files listed separately. No G-class credential candidate was found in the scoped inventory; this is not exhaustive clearance of private metadata.

| File | Git state | Category | Proposed disposition |
| --- | --- | --- | --- |
| `.env.example` | untracked | D | G1 |
| `.gitattributes` | tracked, unchanged | D | KEEP |
| `.github/workflows/offline.yml` | untracked | D | G3 |
| `.gitignore` | modified | D | G1 |
| `LICENSE` | tracked, unchanged | C | KEEP |
| `README.md` | modified | C | G3 |
| `ai_op/backtester.py` | modified | A | G2; deprecated/compatibility source, not the recommended path |
| `ai_op/feature_engineer.py` | modified | A | G2; deprecated/compatibility source, not the recommended path |
| `ai_op/features.py` | untracked | A | G2 |
| `ai_op/research.py` | untracked | A | G2 |
| `ai_op/train_pipeline.py` | modified | A | G2; deprecated/compatibility source, not the recommended path |
| `ai_op/train_pipelinev2.py` | modified | A | G2; deprecated/compatibility source, not the recommended path |
| `docker/docker-compose.yml` | modified | D | G1 |
| `docs/ARCHITECTURE.md` | untracked | C | G3 |
| `docs/COMPLETION_REVIEW.md` | untracked | C | G3 |
| `docs/ENGINEERING_DECISIONS.md` | untracked | C | G3 |
| `docs/ENGINEERING_MASTER_PLAN.md` | untracked | C | G3 |
| `docs/ENGINEERING_PROGRESS.md` | untracked | C | G3 |
| `docs/FINAL_RELEASE_HARDENING.md` | untracked | C | G3 |
| `docs/GITHUB_PUBLICATION_PLAN.md` | untracked | C | G3 |
| `docs/KAFKA_RECOVERY.md` | untracked | C | G3 |
| `docs/ML_METHODOLOGY.md` | untracked | C | G3 |
| `docs/RELEASE_READINESS.md` | untracked | C | G3 |
| `docs/REPRODUCIBILITY.md` | untracked | C | G3 |
| `docs/TESTING.md` | untracked | C | G3 |
| `docs/VALIDATION_MATRIX.md` | untracked | C | G3 |
| `docs/verification/archive/benchmark.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/archive/demo.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/archive/execution.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/archive/results.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/archive/security.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/archive/unittest.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/benchmark.txt` | untracked | E | G3 |
| `docs/verification/demo.txt` | untracked | E | G3 |
| `docs/verification/hardening_changes.txt` | untracked | E | G3; historical review evidence, retain provenance |
| `docs/verification/results.txt` | untracked | E | G3 |
| `docs/verification/security.txt` | untracked | E | G3 |
| `docs/verification/unittest.txt` | untracked | E | G3 |
| `execution_engine/order_router.py` | tracked, unchanged | H | KEEP; empty placeholder, owner review; no execution implementation |
| `execution_engine/paper_trading_bot.py` | modified | A | G2; deprecated/compatibility source, not the recommended path |
| `execution_engine/simulator.py` | untracked | A | G2 |
| `ingestion/FINALIZED_BARS.md` | tracked, unchanged | C | KEEP |
| `ingestion/fetcher.py` | modified | A | G1; deprecated/compatibility source, not the recommended path |
| `ingestion/finalized_bars.py` | tracked, unchanged | A | KEEP |
| `ingestion/historical_downloader.py` | modified | A | G1; deprecated/compatibility source, not the recommended path |
| `ingestion/requirements.txt` | modified | D | G1 |
| `pyproject.toml` | untracked | D | G1 |
| `schemas/MARKET_BAR_V1.md` | tracked, unchanged | C | KEEP |
| `schemas/data_types.py` | tracked, unchanged | A | KEEP |
| `storage_engine/PHASE2D_RELIABILITY.md` | tracked, unchanged | C | KEEP |
| `storage_engine/PHASE2D_TEST_OUTPUT.txt` | tracked, unchanged | E | KEEP; historical synthetic test log, audited and already committed |
| `storage_engine/SSTABLE_COMPACTION.md` | tracked, unchanged | C | KEEP |
| `storage_engine/SSTABLE_PUBLICATION.md` | tracked, unchanged | C | KEEP |
| `storage_engine/SSTABLE_READ_CORRECTNESS.md` | tracked, unchanged | C | KEEP |
| `storage_engine/WAL_RECOVERY.md` | tracked, unchanged | C | KEEP |
| `storage_engine/data_lake_worker.py` | tracked, unchanged | A | KEEP; deprecated/compatibility source, not the recommended path |
| `storage_engine/lsm_core.py` | tracked, unchanged | A | KEEP |
| `streaming/BAR_PROCESSOR.md` | tracked, unchanged | C | KEEP |
| `streaming/OFFLINE_PIPELINE.md` | untracked | C | G1 |
| `streaming/bar_processor.py` | tracked, unchanged | A | KEEP |
| `streaming/kafka_transport.py` | untracked | A | G1 |
| `streaming/offline_pipeline.py` | untracked | A | G1 |
| `streaming/research_pipeline.py` | untracked | A | G2 |
| `tests/test_bar_processor.py` | tracked, unchanged | B | KEEP |
| `tests/test_end_to_end.py` | untracked | B | G2 |
| `tests/test_finalized_bars.py` | tracked, unchanged | B | KEEP |
| `tests/test_kafka_transport.py` | untracked | B | G1 |
| `tests/test_market_bar_contract.py` | tracked, unchanged | B | KEEP |
| `tests/test_offline_pipeline.py` | untracked | B | G1 |
| `tests/test_optional_backends.py` | untracked | B | G3 |
| `tests/test_paper.py` | untracked | B | G2 |
| `tests/test_phase1_executability.py` | tracked, unchanged | B | KEEP |
| `tests/test_release_tools.py` | untracked | B | G3 |
| `tests/test_research.py` | untracked | B | G2 |
| `tests/test_safety.py` | untracked | B | G2 |
| `tests/test_sstable_compaction.py` | tracked, unchanged | B | KEEP |
| `tests/test_sstable_publication.py` | tracked, unchanged | B | KEEP |
| `tests/test_sstable_reads.py` | tracked, unchanged | B | KEEP |
| `tests/test_storage_lifecycle.py` | tracked, unchanged | B | KEEP |
| `tests/test_wal_recovery.py` | tracked, unchanged | B | KEEP |
| `tools/__init__.py` | untracked | A | G1 |
| `tools/benchmark.py` | untracked | A | G2 |
| `tools/check.py` | untracked | A | G3 |
| `tools/demo.py` | untracked | A | G2 |
| `tools/fixtures.py` | untracked | A | G1 |
| `tools/kafka_demo.py` | untracked | A | G1 |
| `tools/legacy.py` | untracked | A | G1 |
| `tools/repository.py` | untracked | A | G3 |
| `tools/review_archive.py` | untracked | A | G3 |
| `tools/security_audit.py` | untracked | A | G3 |
| `tools/verify.py` | untracked | A | G3 |

### Exact local-only exclusions

All ignored files below are **F / DO NOT STAGE**. Archives contain historical duplicate source, manifests/summary files are local review products, and bytecode caches are regenerated. None is required to run a fresh checkout. Public review evidence is the curated `docs/verification/` inventory above, not arbitrary runtime logs. No large binary is proposed for Git.

| Ignored path | Exclusion reason |
| --- | --- |
| `ai_op/__pycache__/backtester.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `ai_op/__pycache__/feature_engineer.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `ai_op/__pycache__/train_pipeline.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `ai_op/__pycache__/train_pipelinev2.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `execution_engine/__pycache__/order_router.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `execution_engine/__pycache__/paper_trading_bot.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `ingestion/__pycache__/fetcher.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `ingestion/__pycache__/historical_downloader.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `review_artifacts/CHANGE_SUMMARY.md` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/MANIFEST.txt` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/SHA256SUMS.txt` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/final-archive-verification.txt` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/final-release-review.sha256` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/final-release-review.tar.gz` | Local review archive; publish only as a separately approved asset, never blindly stage |
| `review_artifacts/phase3a-final-review.tar.gz` | Local review archive; publish only as a separately approved asset, never blindly stage |
| `review_artifacts/phase3a3-review.tar.gz` | Local review archive; publish only as a separately approved asset, never blindly stage |
| `review_artifacts/phase3a4-review.tar.gz` | Local review archive; publish only as a separately approved asset, never blindly stage |
| `review_artifacts/project-completion-review.sha256` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/project-completion-review.tar.gz` | Local review archive; publish only as a separately approved asset, never blindly stage |
| `review_artifacts/source-verification-candidate.sha256` | Local manifest/checksum/review record; keep outside Git staging |
| `review_artifacts/source-verification-candidate.tar.gz` | Local review archive; publish only as a separately approved asset, never blindly stage |
| `schemas/__pycache__/data_types.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `storage_engine/__pycache__/data_lake_worker.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `storage_engine/__pycache__/lsm_core.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_market_bar_contract.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_phase1_executability.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_sstable_compaction.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_sstable_publication.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_sstable_reads.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_storage_lifecycle.cpython-312.pyc` | Python bytecode/cache; machine-generated |
| `tests/__pycache__/test_wal_recovery.cpython-312.pyc` | Python bytecode/cache; machine-generated |

Additional exclusion policy: real `.env` files, credentials/private keys, `.aws/`, `.codex/`, `.agents/`, databases/WAL/SSTables, datasets, model artifacts, dependency environments, sensitive logs and unreviewed binaries must remain local. No such tracked credential/data/model artifact was found by the scoped scan; private metadata directories are excluded rather than asserted safe. `.env.example` is the reviewed exception: comments plus `KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092`, no credentials; it is **not ignored** because of the explicit negation rule.

Plaintext `review_artifacts/` files currently rely on `.git/info/exclude` (`/review_artifacts/`), a nonportable local rule. Root `.gitignore` explicitly ignores archive/checksum extensions, but does not ignore all plaintext review records. This is a WARNING: use this exact inventory; consider an owner-approved portable ignore rule before future artifact generation. This pass does not change configuration or assume private files are safe to add. No `git add .`, `git add -A` or force-add is permitted in this plan.

## C. Security and history assessment

Actual `tools.security_audit` inspected 54 reachable unique historical blobs; largest blob was 15,823 bytes. No sensitive tracked paths, local env files, credential-pattern findings or large historical blobs were found. The only two matches are the scanner's own personal-path regex at `tools/security_audit.py:16`, manually classified as pattern-definition self-matches. Additional read-only checks searched historical sensitive filenames, bearer literals and JWT shapes; no additional candidates were found. `git fsck --full --no-reflogs` and `git diff --check` succeeded. All tracked file modes are ordinary `100644`; no tracked symlink/executable mode was found. `pip check` succeeded, but that checks installed requirement consistency, **not vulnerabilities**.

The scan is heuristic and excludes unreferenced objects, private metadata and ignored research/runtime data. It does not revoke credentials, authenticate authorship or prove no secret exists. No exposed credential is suspected from current evidence. If one is suspected later: stop staging/publication, identify only its location, privately revoke/rotate it at the issuer, review account usage and existing copies, and obtain an owner-approved history/remediation plan. Never paste the value into reports; do not rewrite history automatically.

| Finding / unresolved condition | Classification | Required owner action |
| --- | --- | --- |
| No approval/attestation for final committed HEAD/source | BLOCKER | Review final contents and explicitly authorize local commits, then create their own bound attestation |
| Remote visibility and live remote refs unverified | BLOCKER | Authorize read-only GitHub inspection; confirm destination and exposure before any network write |
| Non-noreply author/committer metadata present | BLOCKER pending consent | Review existing reachable identities privately and approve disclosure; changing future Git identity does not erase old metadata |
| Optional dependency/image security not assessed | BLOCKER pending review/risk acceptance | Approve a scoped security review or explicitly accept documented nondeployment limits before release claims |
| Final publication archive does not yet include this new plan | BLOCKER for distributing a final archive | Rebuild/version and review an archive of the frozen final snapshot; preserve historical archives |
| Source and tests remain partly untracked/uncommitted | BLOCKER for pushing | Complete only the approved exact staging groups; confirm HEAD contains every required file |
| Action references use mutable version tags | WARNING | Review and preferably pin audited action commit SHAs in a separately approved change; do not invent SHA values |
| `review_artifacts/` plaintext ignore is local-only | WARNING | Keep all F paths excluded; consider a portable owner-approved ignore rule |
| Python/OS versions and package resolutions are not a full lockfile | WARNING | Record approved environment/resolution for optional workflows; do not assume core checks validate extras |
| Retained legacy modules/stub and raw worker entry point | WARNING | Use recommended tools only; old worker can connect to Kafka if explicitly invoked, storage legacy demo can write `./data`; archived pickle code is not approved for reuse |
| Real Kafka broker and remote CI unverified | DOCUMENTED LIMITATION | Verify before advertising those levels; remote CI must run against the actual pushed SHA |
| Real-market ML evaluation unavailable | DOCUMENTED LIMITATION | No predictive/profitability claims; owner-provided licensed finalized 1m data needed for evaluation |
| Single-writer storage; filesystem/immutable-value assumptions | DOCUMENTED LIMITATION | No concurrency, HA, hardware power-loss certification or production-readiness claim |
| Synthetic demo/benchmark only | DOCUMENTED LIMITATION | No HFT or economic performance claims |
| Dataset/source licensing provenance not established for future real data | WARNING | MIT code license does not license exchange datasets; review before adding or redistributing data |

No finding authorizes a remote change. Owner review remains mandatory even if the programmatic release gate reports SATISFIED.

## D. Dependencies, containers, workflow and licensing

Core commands require Python 3.11+ and the standard library. `pyproject.toml` specifies `setuptools>=68` for optional packaging (not immutable), optional Kafka `2.3.3`, numpy `2.2.6`, scikit-learn `1.7.2`, XGBoost `3.4.1`, plus legacy requests/pandas/ta/joblib pins. These are direct pins, not a hash-locked transitive environment or security certification. Locally observed setuptools is 68.1.2 and requests is 2.31.0, different from the legacy requests pin; Kafka and ML packages are absent. No optional dependency installation was performed or recommended without approval. `gitleaks`, `trufflehog`, `pip-audit`, `trivy`, `ruff` and `bandit` were unavailable; no new tool was installed. No advisory database was queried.

Compose retains `confluentinc/cp-kafka:7.5.0` and `cp-zookeeper:7.5.0`: loopback-published ports, plaintext transport, one broker/replica, no approved image digest/CVE scan. Do not infer safety from the tags or start containers as part of release preparation.

The single workflow `.github/workflows/offline.yml` uses push/pull_request events (not pull_request_target), global `contents: read`, Ubuntu and Python 3.11/3.12, and standard-library verification. There is no deploy, secret injection, registry login or release job. It references checkout@v4, setup-python@v5 and upload-artifact@v4 using mutable tags. Artifacts contain curated verification reports; owner review of action provenance, runner exposure and future report sensitivity remains required. No remote CI was checked or run.

The existing code license is MIT. The included acquisition/demo data is deterministic synthetic fixture code, not a redistributed real-market dataset. The plan author does not certify ownership of third-party contributions or future exchange data; owner review of code/data provenance and notices is required.

## E. Tests, demo and documentation evidence

The independent reviewer reported 174 tests (173 passed, 1 skipped). This environment has neither Kafka nor XGBoost installed: the fresh local run observed **174 tests, 172 passed, 2 explicit optional-backend skips, 0 failures/errors**, with 30 parse/import checks and compileall passing. Do not substitute the independent environment's skip count for local results. The final post-documentation rerun is authoritative at `verification/results.txt`; its timing and source digest are deliberately read from that report rather than frozen inside a self-referential plan.

Executed locally: `python3 -B -m tools.verify`; separate `python3 -B -m tools.demo`; `git diff --check`; `git fsck --full --no-reflogs`; actual Git-history security audit; extra history filename/token-shape checks; `python3 -m pip check`; archive checksum/member coverage checks. Demo output: **160 persisted/reconciled bars and 101 feature rows**, duplicate suppression, gap/conflict detection, replay inference blocked, paper execution disabled, zero exchange requests by construction. The verifier also completed the synthetic temporary single-writer benchmark; numbers are in `verification/benchmark.txt` and are not extrapolated to production.

README commands were matched to real module entry points. Local `--help` checks confirmed verify (--release/--owner-review), review_archive (--name), benchmark (--records) and research (dataset/--provenance/--output/--kind) interfaces. Tests and demo were actually executed. The optional Docker/Kafka commands were inspected only, not run. Archive extraction evidence under `verification/archive/` and `review_artifacts/final-archive-verification.txt` is historical evidence for the prior hardening source digest; no fresh Git-free run of this new plan is claimed.

README already communicates the engineering problem, code-based architecture, LSM design/recovery tests, stream correctness, research methodology/limitations, quickstart, evidence and unsupported functions. No marketing rewrite or implementation change is necessary. Its real-Kafka, real-data ML, production, single-writer, power-loss and remote-CI limitations remain intact.

## F. Dependency-ordered commit plan — commands for owner use only

The index is currently empty. The commands below are **proposed, not executed**. First inspect all paths and approve local commits/metadata. Each file appears once. Already committed storage/schema/fetcher/processor code and tests are not staged again; no duplicate/empty commit is intended.

For each group: run its exact git add, review `git diff --cached --name-status`, `git diff --cached --stat`, `git diff --cached --check`, and the full `git diff --cached --`. Stop if any unexpected file or secret appears. Run `git diff --cached --quiet`: exit 1 means changes; exit 0 means skip the commit instead of making an empty one. Never bypass hooks or use --allow-empty/--no-verify automatically.

Stage and test an isolated snapshot to avoid falsely validating a commit using unstaged later groups:

```bash
snapshot_dir=$(mktemp -d /tmp/algo-staged-review.XXXXXX)
git checkout-index --all --prefix="$snapshot_dir/"
(cd "$snapshot_dir" && python3 -B -m unittest discover -s tests -v)
# Keep the temporary snapshot for owner inspection; no destructive cleanup command.
```

After G3, that snapshot also supports `python3 -B -m tools.verify` without .git. The optional tooling/ML helpers needed by each earlier group's tests are deliberately staged in that group or its predecessors. Partial groups must not be pushed as the completed release.

### G1: Offline pipeline and Kafka infrastructure (16 paths)

```bash
git add -- \
  .gitignore \
  .env.example \
  pyproject.toml \
  docker/docker-compose.yml \
  ingestion/requirements.txt \
  ingestion/fetcher.py \
  ingestion/historical_downloader.py \
  streaming/offline_pipeline.py \
  streaming/OFFLINE_PIPELINE.md \
  streaming/kafka_transport.py \
  tools/__init__.py \
  tools/fixtures.py \
  tools/kafka_demo.py \
  tools/legacy.py \
  tests/test_offline_pipeline.py \
  tests/test_kafka_transport.py
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git diff --cached --
# After private review, a successful isolated-snapshot test, and explicit approval:
git commit -m 'feat(streaming): integrate finalized bars and typed Kafka transport'
```

### G2: ML research, shared features and isolated paper safety (15 paths)

```bash
git add -- \
  ai_op/features.py \
  ai_op/research.py \
  ai_op/backtester.py \
  ai_op/feature_engineer.py \
  ai_op/train_pipeline.py \
  ai_op/train_pipelinev2.py \
  execution_engine/simulator.py \
  execution_engine/paper_trading_bot.py \
  streaming/research_pipeline.py \
  tools/demo.py \
  tools/benchmark.py \
  tests/test_research.py \
  tests/test_paper.py \
  tests/test_end_to_end.py \
  tests/test_safety.py
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git diff --cached --
# After private review, a successful isolated-snapshot test, and explicit approval:
git commit -m 'feat(research): add shared features and safe offline simulation'
```

### G3: Reproducibility, CI, documentation, security and release tooling (34 paths)

```bash
git add -- \
  tools/check.py \
  tools/repository.py \
  tools/review_archive.py \
  tools/security_audit.py \
  tools/verify.py \
  tests/test_release_tools.py \
  tests/test_optional_backends.py \
  .github/workflows/offline.yml \
  README.md \
  docs/ARCHITECTURE.md \
  docs/COMPLETION_REVIEW.md \
  docs/ENGINEERING_DECISIONS.md \
  docs/ENGINEERING_MASTER_PLAN.md \
  docs/ENGINEERING_PROGRESS.md \
  docs/FINAL_RELEASE_HARDENING.md \
  docs/GITHUB_PUBLICATION_PLAN.md \
  docs/KAFKA_RECOVERY.md \
  docs/ML_METHODOLOGY.md \
  docs/RELEASE_READINESS.md \
  docs/REPRODUCIBILITY.md \
  docs/TESTING.md \
  docs/VALIDATION_MATRIX.md \
  docs/verification/archive/benchmark.txt \
  docs/verification/archive/demo.txt \
  docs/verification/archive/execution.txt \
  docs/verification/archive/results.txt \
  docs/verification/archive/security.txt \
  docs/verification/archive/unittest.txt \
  docs/verification/benchmark.txt \
  docs/verification/demo.txt \
  docs/verification/hardening_changes.txt \
  docs/verification/results.txt \
  docs/verification/security.txt \
  docs/verification/unittest.txt
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git diff --cached --
# After private review, a successful isolated-snapshot test, and explicit approval:
git commit -m 'chore(release): add reproducibility, CI, security and review documentation'
```


Generated evidence is a separate class from source changes. G3 includes the exact curated report paths, including historical archive evidence with its original provenance; it excludes every review_artifacts file. Running verification later may alter only `docs/verification/`. If the owner chooses a separate evidence checkpoint commit, stage only individually reviewed report paths and commit only a nonempty delta, then capture the **new** HEAD and obtain review for it. Do not chase a self-referential loop of commits to make a report's embedded HEAD equal the commit that contains it. Report capture HEAD plus source digest expresses provenance; fresh local evidence may remain a clearly identified evidence-only worktree delta.

## G. Strict release gate and owner attestation

Only after the source/config/docs and local commit sequence are frozen:

```bash
git rev-parse HEAD
git status --short --untracked-files=all
python3 -B -m tools.verify
python3 -B - <<'PY_GATE'
import json
from pathlib import Path
r = json.loads(Path('docs/verification/results.txt').read_text())
print('Reviewed HEAD:', r['git_history'].get('head'))
print('Reviewed source digest:', r['review_source_sha256'])
print('Git history status:', r['git_history']['status'])
PY_GATE
```

Privately review all source/config/docs, metadata, security findings and accepted risks. The owner must personally create the external/ignored review JSON with keys: `approved` (boolean true), `reviewer` (their nonempty review identity), `head` (the final actual reviewed commit SHA), and `source_sha256` (the current verified source digest). This plan does not create a file, approve release or supply a real attestation. A local declaration is not an authenticated signature. Do not commit the attestation or credentials.

Then, substituting the owner's actual existing file path:

```bash
release_head=$(git rev-parse HEAD)
python3 -B -m tools.verify --release --owner-review "$owner_review_path"
test "$(git rev-parse HEAD)" = "$release_head"
git rev-parse HEAD
git diff --check
```

The gate requires successful offline checks, actual completed Git-history inspection, no credential-pattern findings except separately reviewed personal-path items, and an attestation matching current HEAD and source digest. It never authorizes publication automatically. No .git means history NOT RUN/INCOMPLETE and release rejection. Source digest covers allowlisted source/tests/config/docs, excludes generated docs/verification and review_artifacts, and does **not** prove that all worktree files were committed. Therefore also require no staged changes, no untracked publishable files, and no tracked source/config/docs delta before push:

```bash
git diff --cached --name-status
git ls-files --others --exclude-standard
git diff --name-only HEAD -- . ':(exclude)docs/verification/**'
# These three outputs must be empty for a frozen publication source snapshot.
```

Fresh report-only deltas under docs/verification must be reviewed separately and kept out of any accidental blanket staging. The gate currently does not enforce remote visibility, action pinning, dependency vulnerability clearance, broker tests, real-data evaluation, licensing or remote CI. They remain explicit human gates/limits even if SATISFIED is printed.

If source/config/docs changes after review: stop publication, rerun tests/security/diff, update this plan only as necessary, create only authorized additional local commits, capture the new HEAD/source digest, and request a new owner review. Any new commit invalidates the old HEAD binding, even if it contains reports only. Regenerating report-only evidence does not alter source digest, but changed reports still need sensitivity/provenance review. Never silently reuse stale owner approval.

For a final review archive, preserve the current historical artifact and use a separate basename only after the frozen snapshot is reviewed:

```bash
python3 -B -m tools.review_archive --name github-publication-review
```

The checksum file contains a basename; check it from the artifact directory:

```bash
(cd review_artifacts && sha256sum --check github-publication-review.sha256)
```

Require a successful checksum check; do not accept a skipped/missing-file result. The builder also regenerates generic MANIFEST.txt/CHANGE_SUMMARY.md/SHA256SUMS.txt, so preserve earlier copies if the owner needs those sidecars. It excludes sensitive/runtime/Git/cache/data artifacts and enforces relevant changed/untracked coverage, but does not turn owner review into approval. Independently verify the bundled manifest/SHA256SUMS and rerun tools.verify in a clean extraction; missing Git must remain explicit. Keep the archive/checksum local unless the owner separately approves publishing an asset. Do not claim the newly named archive exists until actually built.

## H. Safe GitHub publication sequence — not executed

Each external operation below requires separate owner authorization. An existing remote does not imply private visibility or permission to publish. GitHub CLI is installed; only its local help/version was inspected. No API call or account access was made.

1. Confirm exact local fetch/push endpoints without printing any unexpected credential-bearing URL:

```bash
python3 -B - <<'PY_REMOTE'
import subprocess
base = 'https://github.com/jameskakakaka/Algo_Trading_Project'
allowed = {base, base + '.git'}
for args in [('remote', 'get-url', '--all', 'origin'),
             ('remote', 'get-url', '--push', '--all', 'origin')]:
    urls = subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout.splitlines()
    if len(urls) != 1 or urls[0] not in allowed:
        raise SystemExit('STOP: unexpected remote endpoint; inspect privately')
print('Confirmed expected credential-free origin endpoints')
PY_REMOTE
```

2. After approval for this read-only network request, verify remote identity/visibility in GitHub:

```bash
gh repo view jameskakakaka/Algo_Trading_Project --json nameWithOwner,url,isPrivate,defaultBranchRef
```

If inaccessible or unexpected, STOP. If `isPrivate` is false, pushing a branch exposes its entire reachable history immediately, even before a release/tag; get explicit consent for that exposure. If it is true, do not change visibility automatically. If remote CI is required before any public exposure and origin is already public, an owner-approved private validation process is needed first; do not push merely to obtain CI.

3. Review Git identities privately, approve G1/G2/G3, stage only their exact paths, inspect/test the staged snapshots, and create only the authorized nonempty local commits from section F. Do not rewrite existing commits. Confirm required files are in `git ls-tree -r --name-only HEAD`. Run the strict gate in G and freeze source/HEAD. No owner review file is created by these commands.

4. With read-only network approval, refresh remote refs and confirm no unexpected target history. With separate approval for public/private branch publication, dry-run then push exactly the intended branch; never use --force:

```bash
git fetch --no-tags origin
git ls-remote --heads origin refs/heads/feat/end-to-end-project-completion
git rev-parse HEAD
git log -6 --oneline
# STOP on any failure; retain release_head from the successful strict review.
test "$(git branch --show-current)" = "feat/end-to-end-project-completion"
test "$(git rev-parse HEAD)" = "$release_head"
git push --dry-run origin HEAD:refs/heads/feat/end-to-end-project-completion
# Only after owner approval of destination, visibility, full contents/history and strict gate:
git push --set-upstream origin HEAD:refs/heads/feat/end-to-end-project-completion
```

A dry-run contacts the remote and is not a privacy/security clearance. Stop on a non-fast-forward or any mismatch; do not reset, rebase or force-push. Do not push main, all refs, all tags, a PR or a release automatically.

5. After the authorized push, inspect actual remote CI for the exact reviewed SHA:

```bash
# Keep the frozen release_head from section G; do not substitute a newer commit.
gh run list --repo jameskakakaka/Algo_Trading_Project \
  --branch feat/end-to-end-project-completion --commit "$release_head" \
  --workflow offline.yml --json databaseId,headSha,status,conclusion
# Owner selects the matching run ID; never assume an absent/skipped run passed.
gh run watch "$run_id" --repo jameskakakaka/Algo_Trading_Project --exit-status
gh repo view jameskakakaka/Algo_Trading_Project \
  --branch feat/end-to-end-project-completion --json nameWithOwner,url,isPrivate
```

Inspect both Python matrix jobs, their evidence, README rendering and links, documented limits, and unchanged visibility. If fixes are required, repeat local tests, exact staging/authorized commit, owner-review binding and push/CI checks. Remote CI success is still not Kafka or real-market ML validation. This pass does not claim it ran.

6. Optional **research snapshot tag**, only after passing actual CI and an explicit owner decision; not a production-release assertion:

```bash
# Ensure the selected name is absent locally and remotely; any match means STOP.
git tag --list v0.1.0-research
git ls-remote --tags origin refs/tags/v0.1.0-research 'refs/tags/v0.1.0-research^{}'
# Set release_head to the actual owner-reviewed SHA and verify it again.
git tag -a v0.1.0-research "$release_head" -m 'Offline research snapshot; documented limitations apply'
git push origin refs/tags/v0.1.0-research:refs/tags/v0.1.0-research
```

Review tagger identity too. Do not move/overwrite an existing tag. No GitHub release, asset upload, visibility setting or repository creation command is authorized or executed here.

## I. Remaining release blockers

No-go for automatic public release. Required decisions/actions: owner contents/metadata approval; explicit remote identity/visibility confirmation; dependency/image security review or documented risk acceptance; complete approved local commits; final source-bound attestation and strict gate; regenerated final archive if distributing one; actual CI evidence for the pushed SHA (or an explicitly limited validation process before public exposure). An unverified broker and unavailable real-market evaluation prohibit stronger functionality/performance claims, even if an offline research snapshot is approved.

## J. Portfolio-ready claims and boundaries

Defensible README/CV wording:

> Built and fault-tested a single-writer Python LSM store with WAL recovery, atomic SSTable publication and manual full compaction; integrated finalized market-bar identity/continuity validation and replay-safe durable processing; added shared feature computation and purged time-series research evaluation with a reproducible offline demonstration.

Supporting results: locally verified 174 tests with environment-specific optional skips; 160 durable/reconciled synthetic bars and 101 feature rows; strict fake Kafka acknowledgement/commit/fencing tests; Linux process-crash/fault and randomized lifecycle tests; shared 1m features, train-only preprocessing, expanding purged folds, final holdout, baselines and metadata compatibility. These are infrastructure/methodology results, not trading or real-market model performance. Recommend linking README, architecture, ML methodology, tests and captured reports to recruiters rather than quoting synthetic accuracy/throughput as market evidence.

Explicitly unsupported/unverified claims: real trading profitability, exactly-once guarantees, production-ready Kafka, HFT performance, HA, real-market predictive performance, hardware power-loss certification, production readiness and remote CI success. No live trading or real funds are in scope.

## K. Go/no-go and preparation scope

**GO for owner review of an offline research/portfolio snapshot. NO-GO for push/publication/tagging until the identified human and remote gates are satisfied.** No owner attestation exists or was fabricated. This pass does not stage, commit, push, install tools, make external requests, start services, trade, change visibility or discard existing files. Implementation code is deliberately untouched. Final generated-evidence changes are separated from the one new release document, and the index must remain identical to its entry state.
