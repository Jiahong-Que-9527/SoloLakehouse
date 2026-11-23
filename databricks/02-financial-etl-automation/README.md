# Financial ETL Automation

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D02 · Planned (Databricks Free Edition · Serverless + DABs CLI)** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Package the financial transforms as a deployable Databricks workflow with explicit dependencies, retries and observable runs.

## Technical scope

Lakeflow Jobs, Declarative Automation Bundles, PySpark and GitHub Actions.

## Input and output

- **Input.** A pinned version of the [D01](../01-ecb-delta-lakehouse/README.md) transformations and a fixture for a dedicated test target.
- **Output.** A scheduled job and deployment evidence for ingest, transform, quality checks and publication.

## Acceptance

1. Deploy from GitHub Actions and capture one scheduled job run with each task's status.
2. Induce a task failure. Verify downstream publication stops and the retry behavior matches the error type.
3. Repair the input and rerun. Verify one accepted release, link it to the job run and record the run logs.

## Free Edition execution scope

- Runs on **Databricks Free Edition** Serverless compute with 4 sequential tasks (`ingest -> transform -> quality -> publish`), staying within the 5-concurrent-task limit.
- Validated in CI (`pytest` + `databricks bundle validate`) and deployed/triggered via **Databricks CLI** with PAT authentication (`databricks bundle deploy` / `run`, see [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md)). Keep job schedules paused after verification.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
