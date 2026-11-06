# Release readiness and security checklist

Status: prepared for owner engineering review, NOT approved for public release or deployment. No commit, push, PR or publication was performed.

## Observed local audit

Read-only current-tree/all-reachable-Git-blob scan: [verification/security.txt](verification/security.txt). No credential-pattern matches or tracked sensitive artifacts were found in the initial 54 historical blobs. Scanner path-pattern definitions may match themselves and are documented false positives, not leaked credentials. Subsequent exact counts are captured by tools.verify. No user secret values were printed. No historical rewrite or revocation was attempted. The scan excludes Git internals, private runtime metadata directories, ignored datasets and unreferenced objects; it is not exhaustive.

Current source has no real exchange order-submission implementation. The recommended path never calls the exchange. Legacy paper construction/CLI and import-time backtest are disabled. Unsafe pickle use remains in archived legacy source but is not reached by the recommended path. Owner must not bypass those boundaries with untrusted files.

## Publication checklist (owner action)

- [ ] Independently review every changed and untracked file, including the three pre-existing offline pipeline files.
- [ ] Rerun tools.verify on the intended release tree; inspect failures, skips and generated evidence.
- [ ] Review current/history secret scan, local ignored .env/config and Git author name/email for intended disclosure. Rotate/revoke independently if any exposure is discovered; a clean scan is not revocation evidence.
- [ ] Audit optional direct/transitive dependencies and Docker image vulnerabilities using approved tooling. No vulnerability database scan or install was performed here.
- [ ] Validate the pinned Kafka client/broker demo if Kafka functionality is advertised beyond fake tests. Broker verification remains BLOCKED.
- [ ] Validate XGBoost and genuine finalized-market data before claiming market predictive performance. Performance validation remains BLOCKED.
- [ ] Review data licensing/provenance and avoid committing datasets, pickles, databases, credentials or account logs.
- [ ] Review single-writer ownership, filesystem assumptions, recovery and namespace preconditions; no hardware power-loss certification.
- [ ] Review GitHub Actions permissions and pin third-party actions to audited commit SHAs if desired. Remote CI has not run.
- [ ] Check README/CV wording against evidence; no WebSocket, exactly-once, HA, HFT, profit or production claims.
- [ ] Verify review archive manifest/hash and confirm it contains source/config/docs only.
- [ ] Owner alone authorizes staging/commits and eventual publication. No automatic publishing flow exists.

No known critical secret disclosure was established by available evidence. Outstanding verification and owner approval remain visible release conditions. Optional service setup and market evaluation are not represented as passed.

## Strict verification gate

Offline success does not satisfy release review. `tools.verify --release` requires real Git history and an explicit owner review bound to HEAD plus the current source digest. No owner attestation has been supplied for this work, and no publication is authorized. An extraction without `.git` can verify its offline core but must report history NOT RUN and overall security clearance INCOMPLETE. Do not treat historical reports shipped inside an archive as a fresh history scan of that extraction.

Final handoff: review_artifacts/final-release-review.tar.gz, MANIFEST.txt, SHA256SUMS.txt and final-release-review.sha256. The reviewed loopback-only .env.example is included; real .env files remain excluded. Repository completeness checking includes relevant tracked changes and untracked files. See FINAL_RELEASE_HARDENING.md for source/extraction evidence and remaining gates.
