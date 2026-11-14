# 07 · Platform Orchestration

**Runtime:** GCP Workflows or Dagster. Decide in the first milestone.

Connect the earlier subprojects into one operable pipeline with scheduling,
dependencies, retries, lineage and recovery. Build this last, after the
individual stages are stable.

## Scope

- Compare GCP Workflows and Dagster on the real pipeline. Record the decision
  in an ADR.
- Model the pipeline: acquisition status, transformation, load, feature build,
  training and serving release.
- Add scheduling, retry policy, failure alerts and run history.
- Link every run to its source commit, input data version and output.
- Write and test a recovery runbook for a failed stage.

## Milestones

- **M1.** Orchestrator ADR and a dependency graph of existing stages.
- **M2.** Orchestrate transformation and analytics load end to end.
- **M3.** Add feature build and training.
- **M4.** Failure injection, recovery exercise and runbook.

## Acceptance

- A failed stage can be rerun without redoing earlier stages.
- A run record shows inputs, code revision, outputs and quality results.
- Credentials and state stay outside Git.

## Depends on

Projects 02 to 06. Project 01 stays a local tool unless continuous unattended
ingestion becomes a requirement.

## Outputs

An orchestrated pipeline, run history and a recovery runbook.
