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

## Optional local Kafka demonstration — not run here

Only after explicit owner approval for dependency installation and local service startup:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install '.[kafka]'
docker compose -f docker/docker-compose.yml up -d
# Wait for broker readiness, then use a fresh fixture topic/group.
.venv/bin/python -B -m tools.kafka_demo create-topic --allow-local-kafka
.venv/bin/python -B -m tools.kafka_demo publish --allow-local-kafka
.venv/bin/python -B -m tools.kafka_demo consume --allow-local-kafka
```

These are setup instructions, not executed evidence. Existing-topic creation errors are deliberate; inspect contents instead of deleting user topics. The CLI sends only deterministic synthetic bars and connects only to loopback. A fresh temporary store is used for each consume invocation; replaying retained data demonstrates reconstruction, not persistent daemon deployment. The default dataset has 160 bars; the consumer requires the expected count, never labels empty history complete. All streams/start cursors must be explicitly known. .env.example supplies the only supported broker variable; export it yourself if needed. No credentials are supported.

The Compose images remain pinned to the existing Confluent 7.5.0 demonstration stack. Ports are loopback-bound but plaintext; no TLS/authentication, replicas, volumes/HA or approved vulnerability status is claimed. Optional dependencies and image compatibility need owner verification before service startup. Never expose these ports publicly.

Optional ML: after owner approval, install `.[ml]`, run tests/test_optional_backends.py through unittest discovery, then run ai_op.research with --kind xgboost on reviewed input. Preserve the full dependency resolution and platform details for real experiments. Legacy extras exist only for source archaeology and are not the recommended execution path.
