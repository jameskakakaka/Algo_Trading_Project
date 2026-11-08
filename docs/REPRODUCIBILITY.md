# Reproducibility

## Mandatory offline setup

Use an existing Python 3.11+ installation on Linux and run from the checkout root. There are no mandatory pip dependencies. No .env loading, credentials, Kafka or exchange access is needed. Optional pins are in pyproject.toml; they are proposed/reviewed version selections, not a verified full transitive lockfile. No packages were installed during completion work.

```bash
python3 -B -m tools.demo
python3 -B -m tools.verify
python3 -B -m tools.review_archive
```

The demo creates/removes only its own temporary directory. tools.verify writes allowlisted reports under docs/verification and bytecode under /tmp. tools.review_archive writes an allowlisted review bundle and SHA-256 manifest under review_artifacts. Commands do not operate on user datasets/databases. To train with owner-provided JSONL, follow ML_METHODOLOGY.md. Generated datasets/models belong under ignored artifacts/ or runtime/.

For a fresh checkout, source files, tests, tools and documents must first be reviewed and included in the owner's future commit; current untracked deliverables are intentionally not committed by the agent.

A review source extraction can run the same offline commands without Git. Its fresh results explicitly report history NOT RUN/security INCOMPLETE; inherited repository reports remain historical evidence only. The archive builder includes the validated loopback .env.example, rejects unsafe example edits, verifies changed/untracked relevant-file coverage when Git is available, and writes both a manifest and per-file SHA-256 inventory. Its default output is review_artifacts/final-release-review.tar.gz. Actual extraction verification results are kept under docs/verification/archive/ in the final handoff.

## Optional local Kafka demonstration — startup BLOCKED

The previous Confluent 7.5.0 Kafka/ZooKeeper stack is out of support. `docker/docker-compose.yml` deliberately defines no services; the old startup instructions have been withdrawn. Use `python3 -B -m tools.demo` for the offline demonstration.

The [2026-11-06 security review](FINAL_RELEASE_HARDENING.md#security-review-2026-11-06) records official lifecycle, image and advisory sources, a supported KRaft replacement candidate, and the checks needed before restoring a runnable recipe. Client/broker compatibility, image digest/provenance and vulnerabilities remain unverified. A vendor example or passing fake test does not clear this startup block.

The retained Kafka CLI sends deterministic synthetic bars and accepts only loopback connections with `--allow-local-kafka`. It uses a fresh temporary store per consume invocation and requires the expected count; empty history is incomplete. Existing-topic creation errors are deliberate, and all streams/start cursors must be explicitly known. No broker or optional dependency was started or installed in this review.

Optional ML: after owner approval, install `.[ml]`, run tests/test_optional_backends.py through unittest discovery, then run ai_op.research with --kind xgboost on reviewed input. Preserve the full dependency resolution and platform details for real experiments. Legacy extras exist only for source archaeology and are not the recommended execution path.
