# Financial ETL Automation

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D02 · Implemented (Databricks Free Edition · Serverless + bundle CLI)** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Package the financial transforms as a deployable Databricks workflow with explicit dependencies, retries and observable runs.

## Technical scope

Lakeflow Jobs, Declarative Automation Bundles, PySpark and GitHub Actions.

## Input and output

- **Input.** A pinned version of the [D01](../01-ecb-delta-lakehouse/README.md) transformations and a fixture for a dedicated test target.
- **Output.** A scheduled job and deployment evidence for ingest, transform, quality checks and publication.

## Run the job

Use the pinned D01 and D02 code from the same Git checkout. From this directory,
with the Free Edition CLI profile configured, run:

```bash
rev=$(git rev-parse HEAD)
schema=ecb_d02_dev_my_check
args=(--target dev --profile slh-free --var "schema=$schema"   --var "git_sha=$rev" --var "failure_email=$DATABRICKS_FAILURE_EMAIL")
databricks bundle validate "${args[@]}"
databricks bundle deploy "${args[@]}"
databricks bundle run "${args[@]}" d02_financial_etl
```

Set `DATABRICKS_FAILURE_EMAIL` to the intended notification address. Each
deployment target has its own namespace. A working schema name begins with
`ecb_d02_dev_` or `ecb_d02_prod_` for the corresponding target. The job deploys
with its schedule paused and runs at most one window at a time.

GitHub Actions runs the D01/D02 test suites. The manual deploy workflow on
`main` also validates the target and pushes it with the schedule paused.
Configure the repository secret `DATABRICKS_TOKEN` and variables
`DATABRICKS_HOST` and `DATABRICKS_FAILURE_EMAIL` for that deployment.

## Acceptance

1. Validate the GitHub Actions deploy path and capture one scheduled job run with each task's status.
2. Induce a task failure. Verify downstream publication stops and the retry behavior matches the error type.
3. Repair the input and rerun. Verify one accepted release, link it to the job run and record the run logs.

## Free Edition execution scope

- Runs on **Databricks Free Edition** Serverless compute with 4 sequential tasks (`ingest -> transform -> quality -> publish`), staying within the 5-concurrent-task limit.
- Validated in CI (`pytest` + `databricks bundle validate`) and deployed/triggered via **Databricks CLI** with PAT authentication (`databricks bundle deploy` / `run`, see [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md)). Keep job schedules paused after verification.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
