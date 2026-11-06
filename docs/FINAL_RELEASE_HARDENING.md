# Final release-hardening handoff

The offline core was approved independently; public release remains gated. The independent reviewer reported 159 tests (158 passed, 1 skipped), 160 demo bars/101 features, 29 parse/import checks, compileall and 80-member manifest verification. Those are reviewer observations, not rerun claims. This environment's pre-patch baseline was 159 tests (157 passed, 2 skipped) in 40.911s: kafka-python and XGBoost are both absent locally. No dependencies were installed to change that result.

## Kafka interface

BarConsumerSession now loads concrete client TopicPartition/OffsetAndMetadata types before processing and preflights their constructors. There is no local Offset default, offset_factory override, record-wrapper requirement or tuple commit fallback. Native record fields build a typed mapping before persistence; actual commit remains after durable effects. Missing/incompatible types reject construction before application effects. Strict fake tests cover direct native records, misleading wrapper attributes, unavailable/incompatible types and the actual CLI consume path, retaining all prior fencing/replay/error regressions. No broker was used or verified.

## Verification portability

`python3 -B -m tools.verify` runs mandatory unit, syntax/import, compile, demo and benchmark checks in repositories and clean source extractions. Git metadata is recognized only at the exact source root; absent metadata cannot inherit a parent or GIT_* override. Missing history is NOT RUN with null scan counts; corrupt/failed history is INCOMPLETE. Source scanning remains heuristic and always reports security clearance INCOMPLETE/owner review required. No security clearance or publication approval is inferred from passing offline checks.

Repository evidence: docs/verification/results.txt, unittest.txt, security.txt, demo.txt and benchmark.txt. Clean-extraction execution evidence is retained independently under docs/verification/archive/. Repository and archive evidence must be read with their recorded mode/source_kind/Git status.

## Strict release mode

`python3 -B -m tools.verify --release --owner-review PATH` requires real completed Git history plus an owner-created JSON attestation:

```json
{
  "approved": true,
  "reviewer": "OWNER ENTERS THEIR REVIEW IDENTITY",
  "head": "EXACT REVIEWED HEAD",
  "source_sha256": "EXACT review_source_sha256 FROM CURRENT REPOSITORY VERIFICATION"
}
```

This is a format example, not an attestation or authorization. No actual owner attestation was created or supplied. Store it outside archived source/configuration (for example in an owner-controlled ignored location). The digest binds source, tests, safe configuration and documentation, excluding generated docs/verification evidence and review_artifacts. Any source change invalidates the review. Missing/stale attestation, unavailable history or credential-pattern findings cause failure. A local declaration is not an authenticated signature; owner process remains essential. Even satisfied checks do not publish, commit, trade or assert production readiness.

## Sanitized archive

`python3 -B -m tools.review_archive` creates review_artifacts/final-release-review.tar.gz and final-release-review.sha256. The builder validates .env.example (only the reviewed credential-free loopback setting/comments), includes changed/untracked relevant source/tests/docs/safe configuration, and refuses missing relevant coverage. Credentials, other .env files, Git, runtime databases, datasets, caches, private metadata and legacy raw logs remain excluded. Symlinks and credential-pattern content fail closed rather than being silently followed/packaged.

MANIFEST.txt records per-file sizes and hashes, including CHANGE_SUMMARY.md; SHA256SUMS.txt additionally hashes the manifest. The archive is verified against all inventory hashes. Its external .sha256 covers the full archive, including the checksum inventory itself. The file inventory and actual Git change summary distinguish this pass from earlier uncommitted completion work.

## Unchanged publication gates

- Real Kafka broker behavior is unverified; client-shaped fakes do not establish broker compatibility.
- Reviewed real-market ML evaluation remains unavailable; fixture results are not profitability evidence.
- Production readiness is unsupported.
- Storage remains single-writer under its existing filesystem/value-ownership assumptions.
- No hardware power-loss certification or production-scale performance claim.
- Remote CI has not run.
- Owner review of history/metadata, optional dependency/image vulnerabilities, data licensing and all changed/untracked files is required before any publication.

Exact post-patch test counts, skips, commands and archive evidence are recorded in the verification files and final handoff, rather than inferred from the independent report.
