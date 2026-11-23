# Delivery plan

<!-- [Antigravity·2026-11-23] Initialize Data Engineering delivery plan. -->
<!-- [Antigravity·2026-11-23] Add stage-to-file ownership map and agent session handoff checklist. -->

## Intended outcome

From a fresh checkout and a deterministic seed + locked German open-data fixtures, an engineer can ingest raw charging, roaming, station, price, and FX feeds with quarantine and resume guarantees, transform them through a tested and contract-enforced Kimball star schema in `dbt` (running locally on DuckDB in CI and on GCP BigQuery in `europe-west3`), handle 48-hour late settlements and SCD Type 2 attribute history idempotently, ship changes with Slim CI, orchestrate and recover runs via Apache Airflow, and onboard a second source from the extracted project template.

## Checkpoints and handoffs

- **Checkpoint 1 · Foundation, modeling and quality (`E01–E03`).** Establish deterministic hybrid fixtures and resumable raw ingestion (`E01`), build the layered Kimball star schema with SQLFluff and DuckDB CI (`E02`), and lock in the full dbt testing pyramid including native `unit_tests`, enforced contracts, and `v1 → v2` model versions (`E03`).
- **Checkpoint 2 · Incremental state, Slim CI and BigQuery (`E04–E06`).** Add 48h-lookback incremental merge, parameterized backfill, and SCD Type 2 snapshots (`E04`), cross-database macros, exposures, and `state:modified+ --defer` Slim CI (`E05`), and prove the exact same dbt project on live GCP BigQuery with partitioning, clustering, authorized view, and `bytes_billed` FinOps records (`E06`).
- **Checkpoint 3 · Orchestration, observability and reuse (`E07–E08`).** Wire the end-to-end workflow into local Apache Airflow with failure injection and backfill (`E07`), then add dbt artifact observability (`run_results.json` / `sources.json`), SLO drills, and a reusable template proven on a second source (`E08`).

## Stage-to-file ownership map

| Stage | Primary code & config paths under `Data-engineering/reference-warehouse/` and `.github/` | Acceptance evidence file |
|---|---|---|
| **E01** | `pyproject.toml`, `uv.lock`, `fixtures/*`, `src/charging_commerce/{generator,open_data,ingestion,cli}.py`, `tests/test_ingestion.py` | `01-ingestion-raw-layer/evidence/e01-acceptance.md` |
| **E02** | `.sqlfluff`, `dbt_project/{dbt_project.yml,profiles.yml}`, `dbt_project/models/{staging,intermediate,marts}/*`, `tests/test_dbt_models.py`, `.github/workflows/data-engineering.yml` | `02-dimensional-modeling-dbt/evidence/e02-acceptance.md` |
| **E03** | `dbt_project/models/marts/schema.yml` (contracts, versions, unit_tests), `dbt_project/tests/generic/*`, `dbt_project/tests/singular/*`, `tests/test_contracts.py` | `03-testing-contracts-versioning/evidence/e03-acceptance.md` |
| **E04** | `dbt_project/snapshots/*`, incremental `fct_charging_sessions.sql`, backfill scripts/CLI flags, `tests/test_incremental_scd2.py` | `04-incremental-backfill-scd2/evidence/e04-acceptance.md` |
| **E05** | `dbt_project/packages.yml`, `dbt_project/macros/*`, `dbt_project/models/exposures.yml`, Slim CI steps in `.github/workflows/data-engineering.yml` | `05-macros-exposures-slim-ci/evidence/e05-acceptance.md` |
| **E06** | `dbt_project/profiles.yml` (`bq` target), BigQuery partitioning/clustering macro & IAM/view Terraform or manifest under `06-bigquery-warehouse-finops/infra/` | `06-bigquery-warehouse-finops/docs/cloud-verification.md` |
| **E07** | `airflow/{pyproject.toml,uv.lock,dags/charging_commerce_dag.py,docker-compose.yml}`, `tests/test_airflow_dag.py`, `07-orchestration-airflow/docs/adr-airflow-vs-dagster.md` | `07-orchestration-airflow/evidence/e07-acceptance.md` |
| **E08** | `src/charging_commerce/observability.py`, `template/*` + 2nd onboarded domain, `tests/test_observability.py` | `08-observability-template/evidence/e08-acceptance.md` |

## Working loop

1. **Resolve the stage's open decision first** under "Decisions to resolve by stage" below before writing code.
2. **Implement inside `reference-warehouse/`** (Python 3.12 + `uv`, `pytest`, `ruff`, `sqlfluff`, `dbt`), keeping stage directories for specs and evidence.
3. **Verify cross-warehouse portability** using dbt cross-db macros (`dbt.dateadd`, `dbt.datediff`, etc.) and target-conditional materialization configs so models run identically on `duckdb` and `bigquery`.
4. **Run the stage's positive checks and negative/failure drills**, record evidence per the [evidence guide](evidence-guide.md), link it from the stage README, and move the stage status from `planned` to `accepted`.

## Agent session handoff checklist

Every agent picking up a stage must verify:
1. **Before coding:** read `README.md`, `docs/architecture.md`, `docs/data-contract.md`, and the target stage's `docs/design.md` + `docs/implementation.md`. Confirm your isolated branch/worktree is based on latest `origin/main`.
2. **Before opening a PR:** run `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked pytest`, and (from `E02` onward) `sqlfluff lint` + `dbt build --target duckdb` after the final edit.
3. **Before finishing:** commit stage acceptance evidence under `evidence/`, update the stage `README.md` status and `Current position` below, and never push secrets, `.duckdb`, `.venv`, or raw state files.

## Decisions and rationale

- **Single cloud target: GCP BigQuery (`europe-west3`), €0 Free Tier.** Chosen over Databricks Free Edition to avoid duplicating `databricks/`, avoid Free Edition concurrency/quota caps, and align directly with German DE roles (`dbt + BigQuery + Airflow`). No Cloud Composer or always-on cloud compute is provisioned ([GCP cost gate](../../AGENTS.md)).
- **Python 3.12 pin.** Selected for full stability across `dbt-core`, `dbt-duckdb`, `dbt-bigquery`, `sqlfluff`, and `apache-airflow`.
- **Hybrid real + synthetic data.** Real German public registries/feeds (BNetzA Ladesäulenregister CC BY 4.0, SMARD, ECB) provide realistic cleaning/calendar challenges; seeded synthetic commerce streams anchor deterministic revenue-conservation and late-arrival invariants. Locked fixtures keep CI 100% offline.
- **Separate Airflow virtual environment from dbt.** `apache-airflow` and `dbt` maintain isolated `uv` dependency groups/environments; Airflow invokes `dbt` via isolated CLI/virtualenv execution to prevent dependency conflicts.
- **Dual-target parity via macros.** Cross-database SQL differences (date math, safe division, partitioning blocks) are abstracted once in shared dbt macros rather than maintaining two SQL codebases.

## Decisions to resolve by stage

- **E01:** Freeze the exact locked BNetzA Hesse/Frankfurt station subset row count, SMARD/ECB window, mock roaming API page size/drift rules, and raw table lineage columns.
- **E02:** Freeze `dbt-core` / `dbt-duckdb` / `dbt-bigquery` / `sqlfluff` pinned versions in `uv.lock`, schema naming (`raw`, `stg`, `int`, `mart`), and star-schema table list.
- **E03:** Freeze which models carry `contract: {enforced: true}`, the revenue conservation tolerance (`0.00 EUR`), and the `fct_daily_revenue` `v1 → v2` breaking/non-breaking column change.
- **E04:** Freeze the 48-hour incremental lookback boundary, backfill CLI variables (`start_date`, `end_date`), and `dbt snapshot` check columns for stations and tariffs.
- **E05:** Freeze the CI `manifest.json` artifact storage mechanism for `state:modified+ --defer` Slim CI in GitHub Actions.
- **E06:** Confirm BigQuery dataset layout in `slh-gcp-test` (`europe-west3`), `require_partition_filter: true` enforcement, authorized view reader role, and 100 MiB query billing caps.
- **E07:** Freeze Airflow standalone setup (`uv` isolated env + optional Compose), DAG task granularity (per-layer vs Cosmos), and write the Airflow vs Dagster ADR.
- **E08:** Select the second source (ECB daily FX summary mart) and define the `run_results.json` / `sources.json` operational table schema and freshness SLO threshold.

## Operating boundary

Local execution runs in WSL2 Ubuntu (Python 3.12, `uv`, DuckDB, standalone Airflow). BigQuery operations in `E06` target `slh-gcp-test` (`europe-west3`) strictly within Free Tier bounds and require zero destructive Terraform or paid infrastructure. Raw generated data, `.duckdb` files, Airflow SQLite/logs, and GCP credentials stay outside Git.
