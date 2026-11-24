# Data Engineering

<!-- [Antigravity·2026-11-23] Initialize Data Engineering (dbt + DuckDB CI + GCP BigQuery + Apache Airflow) project planning. -->
<!-- [ZCode·2026-11-23] Add human/reviewer entrypoint (quick start + stage status table) and glossary/ADR links. -->

Deliver an end-to-end modern **Data Engineering** platform on **Python, SQL, dbt, DuckDB, Google BigQuery, and Apache Airflow** over a hybrid German EV charging and roaming commerce workload (`European EV Charging & Roaming Commerce`). Each stage builds verifiable capabilities expected of a mid-to-senior Data Engineer: resumable raw ingestion, Kimball dimensional modeling, dbt testing pyramids and data contracts, incremental merge with late-arriving settlements and SCD Type 2 snapshots, Slim CI, BigQuery partitioning and cost governance, Airflow orchestration with failure recovery, and run observability.

**Status:** E01–E05 accepted with recorded evidence (contract at v1.5; full suite re-verified 2026-11-24, 36 passed); E06 implemented locally (cost-gate approval pending); E07–E08 planned (architecture, stage designs, and implementation plans ready; **E06 live acceptance** next).

## Human quick start

For reviewers and recruiters: the track is in its documentation phase; executable code lands stage by stage starting with **E01**. Two minutes of orientation:

- Skim the [stage list](#stages) below, then the [ADR index](docs/adr/README.md) for the decision story (why BigQuery only, why `dbt snapshot` for history).
- Unfamiliar with the domain? The [glossary](docs/glossary.md) explains BNetzA, SMARD, CPO/eMSP, roaming, and SCD2 in one line each.
- From `E01` onward, every stage runs offline from a fresh checkout with no cloud account:

  ```bash
  cd Data-engineering/reference-warehouse
  uv sync --locked --python 3.12
  uv run --locked pytest                       # stage tests (E01+)
  uv run --locked dbt build --target duckdb    # warehouse build (E02+)
  ```

- [Stage status and evidence](#stage-status-and-evidence) tracks what is accepted, each with a recorded acceptance file.

## Agent quick start

Read these four documents before implementing or modifying any stage:

1. [Architecture and agent rules](docs/architecture.md) — system diagram, `reference-warehouse/` directory blueprint, and mandatory operating constraints.
2. [Delivery plan](docs/delivery-plan.md) — stage checkpoints, stage-to-file ownership map, working loop, and session handoff checklist.
3. [Data contract](docs/data-contract.md) — column-level schemas for all Raw, Quarantine, Snapshot, and Star-Schema Mart tables plus invariants.
4. [Evidence guide](docs/evidence-guide.md) — exact checks, FinOps receipts, and negative drills required to mark a stage `accepted`.

Reference (read on demand): [Glossary](docs/glossary.md) · [ADR index](docs/adr/README.md) · [Data volumes & retention](docs/architecture.md)

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

1. **E01** · [Ingestion and raw layer](01-ingestion-raw-layer/README.md) — deterministic sources, resumable file/API ingestion, lineage metadata, and schema-drift quarantine.
   [Design](01-ingestion-raw-layer/docs/design.md) · [Implementation plan](01-ingestion-raw-layer/docs/implementation.md)
2. **E02** · [Dimensional modeling with dbt](02-dimensional-modeling-dbt/README.md) — `sources` with freshness, `staging` / `intermediate` / Kimball star `marts`, SQLFluff, and DuckDB CI.
   [Design](02-dimensional-modeling-dbt/docs/design.md) · [Implementation plan](02-dimensional-modeling-dbt/docs/implementation.md)
3. **E03** · [Testing, data contracts and versioning](03-testing-contracts-versioning/README.md) — generic/custom/singular conservation tests, native dbt `unit_tests`, enforced `contract`, and `v1 → v2` model versions.
   [Design](03-testing-contracts-versioning/docs/design.md) · [Implementation plan](03-testing-contracts-versioning/docs/implementation.md)
4. **E04** · [Incremental models, backfill and SCD Type 2](04-incremental-backfill-scd2/README.md) — `merge` with a 48h lookback window, parameterized backfill, `--full-refresh` parity, and `dbt snapshot` point-in-time joins.
   [Design](04-incremental-backfill-scd2/docs/design.md) · [Implementation plan](04-incremental-backfill-scd2/docs/implementation.md)
5. **E05** · [Macros, exposures and Slim CI](05-macros-exposures-slim-ci/README.md) — cross-database Jinja macros, `exposures.yml`, `dbt docs` lineage, and `state:modified+ --defer` Slim CI.
   [Design](05-macros-exposures-slim-ci/docs/design.md) · [Implementation plan](05-macros-exposures-slim-ci/docs/implementation.md)
6. **E06** · [BigQuery warehouse and FinOps](06-bigquery-warehouse-finops/README.md) — `--target bq` live verification in `europe-west3`, daily partitioning + clustering, the 100 MiB per-query cap as the enforced guard, authorized view, and `INFORMATION_SCHEMA.JOBS` bytes-billed comparison.
   [Design](06-bigquery-warehouse-finops/docs/design.md) · [Implementation plan](06-bigquery-warehouse-finops/docs/implementation.md)
7. **E07** · [Orchestration with Apache Airflow](07-orchestration-airflow/README.md) — layered Airflow DAG (`ingest -> snapshot -> build -> publish`), failure-stop + clear-node recovery, backfill, and Airflow vs Dagster ADR.
   [Design](07-orchestration-airflow/docs/design.md) · [Implementation plan](07-orchestration-airflow/docs/implementation.md)
8. **E08** · [Observability and DE platform template](08-observability-template/README.md) — `run_results.json` / `sources.json` operational telemetry, freshness SLO drill, and onboarding a second source from the extracted template.
   [Design](08-observability-template/docs/design.md) · [Implementation plan](08-observability-template/docs/implementation.md)

## Stage status and evidence

| Stage | Status | Acceptance record |
|---|---|---|
| E01 · Ingestion and raw layer | accepted | [e01-acceptance.md](01-ingestion-raw-layer/evidence/e01-acceptance.md) |
| E02 · Dimensional modeling with dbt | accepted | [e02-acceptance.md](02-dimensional-modeling-dbt/evidence/e02-acceptance.md) |
| E03 · Testing, contracts and versioning | accepted | [e03-acceptance.md](03-testing-contracts-versioning/evidence/e03-acceptance.md) |
| E04 · Incremental, backfill and SCD2 | accepted | [e04-acceptance.md](04-incremental-backfill-scd2/evidence/e04-acceptance.md) |
| E05 · Macros, exposures and Slim CI | accepted | [e05-acceptance.md](05-macros-exposures-slim-ci/evidence/e05-acceptance.md) |
| E06 · BigQuery warehouse and FinOps | implemented | [cloud-verification.md](06-bigquery-warehouse-finops/docs/cloud-verification.md) |
| E07 · Orchestration with Airflow | planned | — |
| E08 · Observability and template | planned | — |

Status moves `planned → accepted` only when the stage's checks in the [evidence guide](docs/evidence-guide.md) have run after the final edit and the acceptance record is committed under `<stage>/evidence/`; the table row then links to it.

## Layout

Stage directories (`01`–`08`) hold stage specs, designs, implementation plans, ADRs, and recorded evidence. All executable code, fixtures, dbt models, Airflow DAGs, and tests live in one tree under [reference-warehouse/](reference-warehouse/README.md). Raw outputs, local DuckDB files, and Airflow runtime state stay outside Git.
