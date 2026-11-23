# Architecture and Agent Operating Blueprint

<!-- [Antigravity·2026-11-23] Define end-to-end architecture, directory blueprint, and agent rules for Data-engineering/. -->

## 1. Vision and target proof

`Data-engineering/` demonstrates end-to-end **Data Engineering** capability for mid-to-senior Data Engineer and Data Platform Engineer roles using **Python 3.12, SQL, dbt, DuckDB (local/CI), GCP BigQuery (`europe-west3`), and Apache Airflow**:

1. Reliable ingestion from imperfect real-world and API sources with lineage metadata, resume checkpoints, and schema-drift quarantine.
2. Layered Kimball dimensional modeling in `dbt` with SQLFluff style enforcement.
3. Enforced `dbt` data contracts, model versioning (`v1 -> v2`), native `unit_tests`, and exact raw-to-mart revenue conservation.
4. Incremental `merge` processing for 48-hour late-arriving settlements, bounded backfills, and SCD Type 2 history via `dbt snapshot`.
5. Production workflow hygiene: cross-database Jinja macros, `exposures.yml`, `dbt docs` lineage, and `state:modified+ --defer` Slim CI.
6. Zero-fork cloud delivery on BigQuery (`slh-gcp-test`) with daily partitioning, clustering, authorized views, and `INFORMATION_SCHEMA.JOBS` `bytes_billed` FinOps evidence.
7. Apache Airflow orchestration, failure isolation, single-task recovery, artifact observability, and reusable platform templating.

## 2. End-to-end data flow

```text
+-------------------------------------------------------------------------+
| Hybrid Sources                                                          |
|  1. Real German Open Data (locked offline slices + optional --live):    |
|     - BNetzA Ladesaeulenregister (CC BY 4.0): raw_stations_bnetza       |
|     - SMARD wholesale electricity prices:     raw_smard_prices          |
|     - ECB daily FX (CHF/PLN/USD per EUR):     raw_ecb_fx_rates          |
|  2. Seeded Commerce & Drift Streams (anchored to real BNetzA IDs):      |
|     - Charging session events (dups, 48h late, DST, negative kWh)       |
|     - Mock paginated Roaming API (cursor resume, 429 retry, drift)      |
|     - Tariff plan & station upgrade snapshots (t0 -> t1 -> t2)          |
+------------------------------------+------------------------------------+
                                     |  E01: Python ingest CLI
                                     |  (_batch_id, _ingested_at, _source_hash)
                    +----------------+----------------+
                    v                                 v
      +---------------------------+     +---------------------------+
      | Raw Layer (append-only)   |     | raw_quarantine            |
      | DuckDB / Parquet / BQ     |     | (schema drift & bad types)|
      +-------------+-------------+     +---------------------------+
                    |  E02-E05: dbt-core (cross-db macros, SQLFluff)
                    v
      +-------------------------------------------------------------+
      | dbt Staging (stg_*) -> Snapshots (SCD2) -> Intermediate     |
      | -> Kimball Marts (fct_charging_sessions, fct_daily_revenue, |
      |    dim_stations_scd2, dim_tariffs_scd2, dim_date)           |
      | -> Contracts (enforced), Unit Tests & Conservation Checks   |
      +-------------+-------------------------------+---------------+
                    |                               |
       --target duckdb (CI, EUR 0)     --target bq (slh-gcp-test, EUR 0)
                    |                               |
                    v                               v
      +---------------------------+     +---------------------------+
      | GitHub Actions Slim CI    |     | BigQuery (europe-west3)   |
      | state:modified+ --defer   |     | Partitioned + Clustered   |
      +-------------+-------------+     | + Authorized View         |
                    |                   +-------------+-------------+
                    +----------------+----------------+
                                     |  E07: Apache Airflow (local standalone / Compose)
                                     |  E08: run_results.json + sources.json telemetry
                                     v
      +-------------------------------------------------------------+
      | ops_dbt_run_audit + ops_freshness_slo + Reusable Template   |
      +-------------------------------------------------------------+
```

## 3. Target repository blueprint (`reference-warehouse/`)

All executable code lives under `Data-engineering/reference-warehouse/` so tests, contracts, and CI stay cohesive across stages `E01`–`E08`:

```text
Data-engineering/
├── README.md
├── docs/
│   ├── architecture.md               # This blueprint
│   ├── delivery-plan.md              # Checkpoints, file ownership map, handoff checklist
│   ├── data-contract.md              # Column-level schemas and mathematical invariants
│   └── evidence-guide.md             # Required verification and FinOps evidence format
├── 01-ingestion-raw-layer/           # E01 spec + docs/{design,implementation}.md + evidence/
├── 02-dimensional-modeling-dbt/      # E02 spec + docs/{design,implementation}.md + evidence/
├── 03-testing-contracts-versioning/  # E03 ...
├── 04-incremental-backfill-scd2/     # E04 ...
├── 05-macros-exposures-slim-ci/      # E05 ...
├── 06-bigquery-warehouse-finops/     # E06 ...
├── 07-orchestration-airflow/         # E07 ...
├── 08-observability-template/        # E08 ...
└── reference-warehouse/
    ├── pyproject.toml                # Python 3.12 + dbt-core + dbt-duckdb + dbt-bigquery + sqlfluff
    ├── uv.lock
    ├── .sqlfluff
    ├── fixtures/                     # Locked BNetzA/SMARD/ECB slices + manifest.json (SHA-256)
    ├── src/charging_commerce/
    │   ├── generator.py              # Seeded commerce streams + mock roaming API server
    │   ├── open_data.py              # Locked fixture loader + optional --live BNetzA/SMARD/ECB fetch
    │   ├── ingestion.py              # Resumable ingestion, quarantine, raw DuckDB/BQ loader
    │   ├── observability.py          # run_results.json & sources.json audit parser (E08)
    │   └── cli.py                    # Typer/argparse entrypoint (generate, ingest, audit-dbt)
    ├── dbt_project/
    │   ├── dbt_project.yml
    │   ├── packages.yml              # dbt_utils
    │   ├── profiles.yml              # duckdb (default/CI) + bq (europe-west3, maximum_bytes_billed)
    │   ├── models/
    │   │   ├── staging/
    │   │   ├── intermediate/
    │   │   └── marts/
    │   ├── snapshots/                # dim_stations_scd2, dim_tariffs_scd2
    │   ├── macros/                   # cross-db date/division/partition helpers
    │   └── tests/                    # singular conservation & parity tests
    ├── airflow/                      # Isolated uv env/pyproject + optional docker-compose.yml + DAGs
    ├── template/                     # Extracted DE starter template + 2nd onboarded workload (E08)
    └── tests/                        # pytest suite (ingestion, parity, contracts, DAG parse, ops)
```

## 4. Mandatory rules for every agent

1. **Single cloud target & GCP cost gate:** BigQuery targets `slh-gcp-test` in `europe-west3` only, using `maximum_bytes_billed` caps and Free Tier limits (10 GB storage, 1 TB scan/month). Never provision Cloud Composer, Cloud NAT, static external IPs, or always-on VMs. Follow [AGENTS.md](../../AGENTS.md).
2. **Python 3.12 & dependency isolation:** pin `requires-python = ">=3.12,<3.13"` in `reference-warehouse/pyproject.toml`. Keep `apache-airflow` in its own isolated `uv` environment under `reference-warehouse/airflow/` so Airflow dependencies never conflict with `dbt`.
3. **Offline deterministic CI:** GitHub Actions PRs run exclusively against locked fixtures and `dbt-duckdb` (`--target duckdb`) with zero network calls or GCP credentials. Live source refreshes (`--live`) and BigQuery targets (`--target bq`) are explicit operator runs.
4. **Cross-warehouse SQL parity:** write models once using dbt cross-db macros (`dbt.dateadd`, `dbt.datediff`, `dbt.date_trunc`, `dbt.safe_cast`, and project macros for safe division and target-conditional `partition_by`/`cluster_by`). Never fork separate SQL files for DuckDB vs BigQuery.
5. **Honest acceptance & evidence:** a stage stays `planned` until every check in its `implementation.md` passes after the final edit and its evidence note is committed under `<stage>/evidence/`. Never silently drop malformed rows — route them to `raw_quarantine` and reconcile every cent in revenue conservation.
6. **Worktree isolation:** verify you are in a dedicated branch/worktree for `Data-engineering/` work and never overwrite uncommitted work from sibling project sessions.

## 5. Data volumes, retention and free-tier budget

<!-- [ZCode·2026-11-23] Add volume estimates and retention policy so FinOps (E06) and the free-tier gate have numbers to reconcile against. -->

**Volume estimates (locked fixtures, deterministic):**

| Source | Rows | Raw size |
|---|---|---|
| BNetzA Hesse/Frankfurt station slice × `t0/t1/t2` | ≤ 10,000 | < 2 MB |
| SMARD hourly prices + load (locked window) | ≤ 50,000 | < 2 MB |
| ECB daily FX (3 pairs) | ≤ 2,000 | < 0.1 MB |
| Seeded charging sessions (incl. duplicates/late/dirty) | ≤ 100,000 | < 5 MB |
| Roaming settlements (paginated mock API) | ≤ 30,000 | < 2 MB |

Total: well under 200,000 rows / ~10 MB — local DuckDB stays tens of MB, and the BigQuery `de_raw` upload is `< 10 MB` (E06), i.e. `< 0.1%` of the 10 GB Free-Tier storage and `< 0.01%` of the 1 TB monthly scan allowance even before partition pruning.

**Retention policy:**

- Local raw databases/Parquet and Airflow state stay outside Git (`.gitignore`) and may be rebuilt from fixtures + seed at any time; nothing local is authoritative.
- Git holds code, contracts, fixtures manifests, and evidence — the authoritative artifacts.
- BigQuery uses **passive expiration, not active destroys**: `de_raw`/`de_stg` datasets get a 90-day `default_table_expiration`, marts persist for the life of the track. This preserves the `0 destroys` cost-gate rule while bounding storage.
- Evidence receipts (`INFORMATION_SCHEMA.JOBS`, acceptance records) are copied into Git at acceptance time, so cloud state can expire safely.

## 6. Related documents

- [Project overview](../README.md)
- [Delivery plan](delivery-plan.md)
- [Data contract](data-contract.md)
- [Evidence guide](evidence-guide.md)
- [Glossary](glossary.md)
- [Architecture decision records](adr/README.md)
- [Reference warehouse](../reference-warehouse/README.md)
- [Databricks track (separate free-edition track)](../../databricks/README.md)
