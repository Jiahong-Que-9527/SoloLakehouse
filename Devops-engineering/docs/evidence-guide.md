# Acceptance evidence

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

All phases start as planned. Mark a phase accepted after its listed checks have run and link the results from its phase README.

## Record for each run

- Scenario, target behavior, command or procedure, UTC timestamp and observed result.
- Source commit, image digest when applicable, runtime versions and redacted configuration identity.
- Audit input identity or fixture revision. Capture the dataset or report checksum where applicable.
- Expected and observed outcomes including failures, skipped checks and the reason for each.
- Links to logs, CI runs, release manifests or a short sanitized summary that can be reproduced.

## Release and incidents

For a release exercise, record requested digest, prior digest, the deployed digest after verification, smoke-test output and rollback outcome. Record failed release attempts even when the prior version stays active.

For an incident, record the injection, first observed symptom, alert time, recovery action, recovery time and the data-integrity check. Define timestamps consistently so that detection and recovery durations can be compared across exercises. Run failures against a disposable fixture or isolated environment.

Keep the synthetic fixture and reproduction steps suitable for a fresh checkout. Inspect screenshots and logs before committing evidence to avoid publishing secrets, private paths or raw source exports.
