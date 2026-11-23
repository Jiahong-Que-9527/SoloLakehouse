# Data Engineering

<!-- [Antigravity·2026-11-23] Initialize Data Engineering (dbt + DuckDB CI + GCP BigQuery + Apache Airflow) project planning. -->

Deliver an end-to-end modern **Data Engineering** platform on **Python, SQL, dbt, DuckDB, Google BigQuery, and Apache Airflow** over a hybrid German EV charging and roaming commerce workload (`European EV Charging & Roaming Commerce`). Each stage builds verifiable capabilities expected of a mid-to-senior Data Engineer: resumable raw ingestion, Kimball dimensional modeling, dbt testing pyramids and data contracts, incremental merge with late-arriving settlements and SCD Type 2 snapshots, Slim CI, BigQuery partitioning and cost governance, Airflow orchestration with failure recovery, and run observability.

**Status:** E01–E08 planned (scaffold landed; **E01** next).

## Cloud target and cost boundary

- **Single cloud target: GCP BigQuery (`slh-gcp-test`, `europe-west3`)** paired with **local DuckDB (`dbt-duckdb`)** for zero-cost offline CI. Databricks remains scoped exclusively to [databricks/](../databricks/README.md).
- **Zero-cost rule:** every BigQuery exercise stays within the monthly BigQuery Free Tier (10 GB storage, 1 TB query scan) and uses no Cloud Composer, Cloud NAT, or always-on VMs. See the mandatory [GCP cost gate](../AGENTS.md).
- **Local runtime:** Python 3.12 managed with `uv`, SQLFluff for SQL style, and Apache Airflow running locally in standalone mode (with an optional Compose definition).

## Hybrid workload and data availability

To combine real-world dirty data with deterministic end-to-end financial reconciliation:

1. **Real German open data (locked snapshots + SHA-256 manifests for offline CI, optional `--live` refresh):**
   - **Bundesnetzagentur Ladesäulenregister** (`CC BY 4.0`) — public German EV charging stations (operator, postal code, city, coordinates, kW capacity, commissioning date, connector types).
   - **SMARD** (Bundesnetzagentur) — German electricity market load and wholesale prices (no API key).
   - **ECB Data Portal** — daily reference exchange rates (`EUR/CHF`, `EUR/PLN`, `EUR/USD`, no API key) for multi-currency settlement normalization and holiday-gap handling.
2. **Anchored deterministic synthetic commerce streams (seeded Python generator):**
   - `charging_sessions` keyed to real BNetzA station IDs, including duplicate events, 48-hour late settlements, negative-kWh dirty rows, refunds/reversals, and CET/CEST DST boundaries.
   - `roaming_settlements` via a mock paginated REST API with cursor resume, rate-limit retries, and deliberate schema drift.
   - `stations` and `tariff_plans` snapshot sequences representing power upgrades and tariff changes to drive **SCD Type 2** history.

## Stages

1. [E01 · Ingestion and raw layer](01-ingestion-raw-layer/README.md) — deterministic data sources, resumable file/API ingestion, raw lineage metadata, and schema-drift quarantine.
2. [E02 · Dimensional modeling with dbt](02-dimensional-modeling-dbt/README.md) — `sources` with freshness, `staging` / `intermediate` / Kimball star `marts`, SQLFluff, and DuckDB CI.
3. [E03 · Testing, data contracts and versioning](03-testing-contracts-versioning/README.md) — generic/custom/singular conservation tests, native dbt `unit_tests`, enforced `contract`, and `v1 → v2` model versions.
4. [E04 · Incremental models, backfill and SCD Type 2](04-incremental-backfill-scd2/README.md) — `merge` with a 48h lookback window, parameterized backfill, `--full-refresh` parity, and `dbt snapshot` point-in-time joins.
5. [E05 · Macros, exposures and Slim CI](05-macros-exposures-slim-ci/README.md) — cross-database Jinja macros, `exposures.yml`, `dbt docs` lineage, and `state:modified+ --defer` Slim CI.
6. [E06 · BigQuery warehouse and FinOps](06-bigquery-warehouse-finops/README.md) — `--target bq` live verification in `europe-west3`, daily partitioning (`require_partition_filter`), clustering, authorized view, and `INFORMATION_SCHEMA.JOBS` bytes-billed comparison.
7. [E07 · Orchestration with Apache Airflow](07-orchestration-airflow/README.md) — layered Airflow DAG (`ingest -> snapshot -> build -> publish`), failure-stop + clear-node recovery, backfill, and Airflow vs Dagster ADR.
8. [E08 · Observability and DE platform template](08-observability-template/README.md) — `run_results.json` / `sources.json` operational telemetry, freshness SLO drill, and onboarding a second source from the extracted template.

Read the [delivery plan](docs/delivery-plan.md), [evidence guide](docs/evidence-guide.md), and [data contract](docs/data-contract.md) before starting `E01`.

## Layout

Stage directories (`01`–`08`) hold stage specs, ADRs, and recorded evidence. All executable code, fixtures, dbt models, Airflow DAGs, and tests live in one tree under [reference-warehouse/](reference-warehouse/README.md). Raw outputs, local DuckDB files, and Airflow runtime state stay outside Git.
