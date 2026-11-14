# 07 · Platform Orchestration

**Runtime:** GCP Workflows or Dagster. Decide in the first milestone.

Connect the earlier subprojects into one operable pipeline with scheduling,
dependencies, retries, lineage and recovery. Build this last, after the
individual stages are stable.

## Scope

- Compare GCP Workflows and Dagster on the real pipeline. Record the decision
  in an ADR.
- Model the pipeline. Local stages (acquisition, Silver, Gold, release) stay
  scripts and are only observed. Cloud stages (release detection, validation,
  ingestion, analytics, training and serving release) are orchestrated.
- Detect a new release by its `_SUCCESS` file and trigger ingestion.
- Add scheduling, retry policy, failure alerts and run history.
- Link every run to its source commit, input data version and output.
- Write and test a recovery runbook for a failed stage.

## Milestones

- **M1.** Orchestrator ADR and a dependency graph of existing stages.
- **M2.** Orchestrate release detection, ingestion and analytics load end to
  end.
- **M3.** Add feature build and training.
- **M4.** Failure injection, recovery exercise and runbook.

## Acceptance

- A failed stage can be rerun without redoing earlier stages.
- A run record shows inputs, code revision, outputs and quality results.
- Credentials and state stay outside Git.

## Depends on

Projects 03 to 06. Projects 01 and 02 stay local tools unless continuous
unattended ingestion becomes a requirement.

## Outputs

An orchestrated pipeline, run history and a recovery runbook.
