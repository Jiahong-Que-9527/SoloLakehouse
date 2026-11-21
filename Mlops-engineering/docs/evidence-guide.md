# Acceptance evidence

<!-- [魏征·2026-11-21] Initialize evidence recording rules. -->

All stages start as planned. Mark a stage accepted after its listed checks have run and link the results from its stage README.

## Record for each run

- Scenario, target behavior, command or procedure, UTC timestamp and observed result.
- Source commit, image digest when applicable, runtime versions (Python, uv lock, MLflow, Dagster) and redacted configuration identity.
- Data release ID and dataset checksum for every training, evaluation or scoring run. Model runs add the model release ID or the MLflow run ID.
- Expected and observed outcomes, including failures, skipped checks and the reason for each.

## Model releases

For a model release, record the manifest digest, the previously pinned version, the evaluation summary against the pinned baseline and the determinism check result (two runs, identical metrics). Record failed promotion attempts even when the previous version stays pinned.

## Drills and incidents

For the drift drill, record the injection, first observed symptom, alert time, retraining trigger, retraining completion, recovery action and the post-recovery metric. Use consistent timestamps so detection and recovery durations compare across exercises. Run drills against disposable outputs.

Keep the synthetic fixtures and reproduction steps suitable for a fresh checkout. Inspect logs and reports before committing evidence to avoid publishing secrets, private paths or oversized outputs.
