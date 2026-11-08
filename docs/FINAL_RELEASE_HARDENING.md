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

## Security review 2026-11-06

Scope: reviewed HEAD `c040fd05758aa07354384f2cf80a58629660deb2`, plus the working-tree changes described here. Four verification reports were already modified before this pass. The required verifier refreshes repository reports; previous archive/extraction evidence remains historical. No container, dependency installation, remote CI, commit, push, history rewrite, owner attestation or visibility change is part of this review.

### Kafka support and startup block

**Compose startup is BLOCKED.** The old Kafka/ZooKeeper 7.5.0 services were removed; `docker/docker-compose.yml` now has an empty services map. There is no service to start by name or profile. The reproducibility guide no longer recommends Docker startup or optional installation. Offline execution remains `python3 -B -m tools.demo` and `python3 -B -m tools.verify` with no third-party dependencies.

The official [Confluent lifecycle table](https://docs.confluent.io/platform/7.9/installation/versions-interoperability.html) lists 7.5 standard support ending August 25, 2025 and Platinum support ending August 25, 2026. Both dates have passed. [CONFSA-2024-02 / CVE-2024-27309](https://support.confluent.io/hc/en-us/articles/25955147061780-CONFSA-2024-02-CVE-2024-27309-Zookeeper-to-KRaft-migration-could-result-in-lack-of-enforcement-of-Kafka-ACLs-under-specific-conditions) includes 7.5.0 among affected releases, with specific ACL-removal conditions during ZooKeeper-to-KRaft migration. This confirms an old-version advisory, not that this plaintext demo exercised its preconditions. Loopback port publication does not resolve lifecycle or image vulnerabilities.

Recommended replacement **for compatibility validation**: one `confluentinc/cp-kafka:7.9.10` broker/controller in KRaft combined mode, without ZooKeeper, paired with the existing `kafka-python==2.3.3` client. As of this review, the [vendor release notes](https://docs.confluent.io/platform/7.9/release-notes/index.html) confirm 7.9.10, and the lifecycle table maps 7.9 to Kafka 3.9 with standard support through February 19, 2027. The official [Docker configuration example](https://docs.confluent.io/platform/7.9/installation/docker/config-reference.html#cp-kafka-example) explicitly names that image/tag and documents combined mode for local experimentation, excluding production support for this topology. The version/tag is vendor-documented; no registry manifest, platform digest or container contents were verified, and no digest is invented here. Recheck support and current security patches before future use.

The candidate should publish only `127.0.0.1:9092:9092`, advertise `127.0.0.1:9092` to host clients, keep controller/internal listeners unpublished, and use a dedicated local Docker network with no host networking. Follow the vendor's KRaft node/roles, unique cluster ID, controller quorum/listener and single-node offset replication settings. Use one partition/replica for fresh synthetic fixtures and preserve the existing explicit loopback CLI opt-in, durable-before-commit and replay/fencing policies. Plaintext still permits trusted host/container peers to access the service; this is isolated development only, with no credentials, real-market inputs, production data or trading.

**Compatibility is not verified.** The [maintainer's 2.3.3 package description](https://pypi.org/project/kafka-python/2.3.3/) documents consumer groups, producer acknowledgements and protocol probing, but does not establish this repository's exact client/configuration/broker pair. Confluent's image example likewise does not validate this client's admin/create-topic, produce, consume, offset and recovery behavior. No supported runnable replacement is claimed or enabled. Before restoring a recipe, verify official registry identity and the target-platform digest, review current image advisories, and record an authorized local integration run covering topic creation, acknowledged produce, durable consume/commit, restart replay, conflict/gap fencing and loopback-only exposure. No existing volumes or user topics should be migrated or deleted to perform that check.

### GitHub Actions provenance

[GitHub recommends full commit pins and verifying repository origin](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions). Each release page below linked to the full commit in the corresponding official `actions/*` repository and displayed GitHub's verified-signature indicator. These observations confirm source identity; no independent signature verification or comprehensive code/dependency audit is claimed.

| Official action release | Full commit pin (official commit page) |
| --- | --- |
| [checkout v4.3.1](https://github.com/actions/checkout/releases/tag/v4.3.1) | [34e114876b0b11c390a56381ad16ebd13914f8d5](https://github.com/actions/checkout/commit/34e114876b0b11c390a56381ad16ebd13914f8d5) |
| [setup-python v5.6.0](https://github.com/actions/setup-python/releases/tag/v5.6.0) | [a26af69be951a213d495a4c3e4e4022e16d87065](https://github.com/actions/setup-python/commit/a26af69be951a213d495a4c3e4e4022e16d87065) |
| [upload-artifact v4.6.2](https://github.com/actions/upload-artifact/releases/tag/v4.6.2) | [ea165f8d65b6e75b540449e92b4886f43607fa02](https://github.com/actions/upload-artifact/commit/ea165f8d65b6e75b540449e92b4886f43607fa02) |

The workflow retains push/pull_request triggers, `contents: read`, Python 3.11/3.12 and the offline verification command. Pins stay within the existing action major versions. Runner images (`ubuntu-latest`), Python patch resolution and action downloads remain external mutable inputs; commit pins do not make remote CI fully offline or reproducible. Remote CI has not run. Two dependency-free regression guards enforce the disabled Compose boundary and full commit pins from the reviewed official action sources; they do not perform network provenance checks.

Fresh check results belong in `docs/verification/results.txt` and `unittest.txt`; `python3 -B -m tools.verify` and `git diff --check` are required for this tree. Security clearance remains INCOMPLETE: image/dependency vulnerability scans, broker compatibility, action code audit and owner release approval are still outstanding. Existing source-bound attestations and archives cannot approve these changed configuration/tests/docs; none was created or rebuilt in this pass.
