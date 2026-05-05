# SoloLakehouse — Comprehensive Project State Overview

> Snapshot date: 2026-05-05
> Current baseline: v2.5 (single-track orchestrated platform)
> Purpose: a single document that lets a reader build a complete, accurate picture of the project's current state in 15 minutes, so the v3 evolution discussion and enterprise-grade adoption path can rest on shared facts.

---

## 1. What this project actually is

SoloLakehouse is a **runnable, readable, cloud-neutral** Lakehouse reference implementation.

It is **not**:
- A framework or a library
- A user-facing SaaS product
- An "open-source clone" of Databricks / Snowflake

It **is**:
- A complete Lakehouse architecture sample that runs on **a single Docker Compose host**
- A pure open-source demonstration of how Databricks / Snowflake work internally
- An engineering work piece that **declares platform-engineering capability** (forkable, criticizable, reusable)
- An end-to-end Bronze → Silver → Gold → ML demo grounded in a real financial domain (ECB rates + DAX index)

Repository main branch: `main`. Language: Python 3.13+. License: MIT.

---

## 2. Current technology stack (what v2.5 actually runs)

| Layer | Component | Version | Role |
|---|------|------|------|
| Object storage | MinIO (S3-compatible) | RELEASE.2025-09-07 | Bronze/Silver/Gold Parquet + MLflow artifacts |
| Metadata DB | PostgreSQL | 17 | Backend for Hive Metastore, MLflow, Dagster, Superset |
| Table catalog | Apache Hive Metastore (standalone) | 4.0.0 | Table schema, partitions, locations |
| Query engine | Trino | 480 | Hive + Iceberg dual catalogs |
| Gold table format | Apache Iceberg (via Trino) | — | Open table format for Gold |
| Data catalog | OpenMetadata | 1.5.x | Asset metadata + lineage UI |
| BI / SQL UI | Apache Superset | 6.0.0 | Dashboards + ad-hoc SQL |
| ML tracking | MLflow | 3.10.1 | Experiments, params, metrics, artifacts |
| Orchestration | Dagster | 1.7.x (default) | Asset / Job / Schedule / Sensor / Asset Check |
| Validation | Pydantic v2 | 2.12.5 | Per-record validation in ingestion |
| Data format | Parquet (snappy) | — | Default for Bronze/Silver |
| Logging | structlog | 25.5.0 | Structured event logs |
| Testing | pytest | 9.0.2 | Unit + integration |

Everything runs from `docker/docker-compose.yml` + `docker-compose.openmetadata.yml` + `docker-compose.superset.yml`, brought up by a single `make up`.

---

## 3. Repository layout (one diagram)

```
SoloLakehouse/
├── ingestion/           # Ingestion layer
│   ├── collectors/      # ECBCollector, DAXCollector (one class per source)
│   ├── schema/          # Pydantic v2 record models
│   ├── quality/         # Bronze-layer quality functions
│   ├── bronze_writer.py # Validated → MinIO Parquet
│   └── trino_sql.py     # Hive external table + Iceberg Gold CTAS via Trino REST
├── transformations/     # Transformation layer
│   ├── ecb_bronze_to_silver.py
│   ├── dax_bronze_to_silver.py
│   ├── silver_to_gold_features.py
│   └── quality_report.py
├── ml/                  # ML layer
│   ├── train_ecb_dax_model.py   # XGBoost/LightGBM + TimeSeriesSplit
│   └── evaluate.py              # MLflow experiment runner
├── dagster/             # Orchestration layer
│   ├── assets.py        # Software-defined assets + sensor + asset check
│   ├── resources.py     # MinIO/config resources
│   ├── definitions.py   # Job/Schedule registry
│   ├── io_managers.py
│   └── workspace.yaml / dagster.yaml
├── scripts/             # Platform scripts (health, bootstrap, template render)
├── config/              # Trino catalog/properties + Postgres init.sql
├── docker/              # Three compose files; custom Hive/MLflow/Superset images
├── tests/               # Unit + integration (mocked MinIO; no Docker needed)
├── docs/                # Architecture, ADRs, roadmap, history, release checklists
├── data/sample/         # Committed DAX sample CSV
├── TASKS.md             # Execution backlog (Block A–G order)
├── CLAUDE.md            # Project-level agent guide
└── Makefile             # `make up/down/pipeline/verify/test/lint/typecheck`
```

---

## 4. Data flow (medallion end-to-end)

```
ECB SDW REST API     DAX sample CSV
        │                  │
        ▼                  ▼
   Python collectors (Pydantic validation, rejected records persisted)
        │
        ▼
   Bronze Parquet (partitioned by ingestion_date, immutable)
        │
        ▼
   Silver Parquet (typed, deduped, derived: rate_change_bps, daily_return)
        │
        ▼
   Gold Parquet (ECB+DAX join, event-study features)
        │
        ├── Hive external table:    hive.gold.ecb_dax_features
        └── Iceberg Gold (Trino CTAS): iceberg.gold.ecb_dax_features_iceberg
                │
                ├──► Superset dashboards
                ├──► OpenMetadata metadata / lineage
                └──► MLflow (XGBoost/LightGBM + TimeSeriesSplit)
```

Buckets:
- `sololakehouse`: `bronze/`, `silver/`, `gold/`
- `mlflow-artifacts`: MLflow artifacts

---

## 5. Orchestration layer (Dagster v2 — delivered)

**Asset dependency graph:**
```
ecb_bronze       dax_bronze
    │                │
ecb_silver       dax_silver
       \            /
        gold_features
              │
         ml_experiment
```

**Delivered runtime shape:**
- `full_pipeline_job` — single Dagster job stitching all assets
- `daily_pipeline_schedule` — cron `0 6 * * 1-5` (06:00 UTC weekdays)
- `ecb_data_freshness_sensor` — checks ECB freshness every 30 min, can trigger `ecb_bronze`
- Asset checks for basic freshness/shape
- Persistence: Dagster instance storage backed by PostgreSQL DB `dagster_storage`

**Entry points:**
- `make pipeline` runs `full_pipeline_job` once
- `make dagster-ui` opens `http://localhost:3000`

---

## 6. Key architecture decisions (ADR catalogue)

The repository carries **16 ADRs**, organized in three groups:

| Group | ADR | Topic |
|---|---|---|
| Foundations | ADR-001 | Docker Compose vs Kubernetes |
|  | ADR-002 | Trino vs DuckDB |
|  | ADR-003 | Parquet vs Delta Lake |
|  | ADR-004 | ECB + DAX dataset choice |
|  | ADR-005 | v1 scope (why Prom/Grafana/CloudBeaver were deferred) |
|  | ADR-013 | Iceberg for Gold via Trino |
|  | ADR-014 | OpenMetadata (now in default v2.5 stack) |
|  | ADR-016 | Compute engine migration path |
| v2 Orchestration | ADR-006 | Dagster orchestration migration & fallback |
| v3 Governance / Productionization | ADR-007 | K8s + Helm + Terraform baseline |
|  | ADR-008 | Environment promotion gates (dev → staging → prod) |
|  | ADR-009 | Secrets and access governance |
|  | ADR-010 | SLO-driven observability |
|  | ADR-011 | ML productization boundary (experiments first, serving deferred) |
|  | ADR-012 | Data governance & catalog strategy |
|  | ADR-015 | Observability tooling choice |

Design philosophy threading the ADRs:
- **Local-first** — running on a single host is a non-negotiable readability constraint
- **Open table formats** — Iceberg for Gold, no engine lock-in
- **Fail loudly** — quality checks raise; no silent degradation
- **No random CV on time-series** — TimeSeriesSplit always
- **No component sprawl** — Prometheus/Grafana stay out of v2.5 default until the observability narrative is mature

---

## 7. Delivered capability inventory (what works today)

Platform foundation:
- [x] Single-command bring-up of 8+ services (`make up`)
- [x] Health check script (`make verify`)
- [x] Clean teardown and data wipe (`make down` / `make clean`)
- [x] PostgreSQL multi-tenancy (hive_metastore + mlflow + dagster_storage + superset)

Data flow:
- [x] Immutable Bronze writes + Pydantic validation + rejected-record persistence
- [x] Silver: type cleanup, deduplication, derived fields
- [x] Gold Parquet to MinIO
- [x] Gold registered both as Hive external table and as Iceberg table (Trino CTAS)

Orchestration:
- [x] Dagster asset graph, job, schedule, sensor, asset check all wired
- [x] Dagster persistence in PostgreSQL

Governance & BI:
- [x] OpenMetadata in default stack, ingesting Trino metadata
- [x] Superset in default stack, on top of Trino, dashboards + ad-hoc SQL

ML:
- [x] XGBoost / LightGBM with TimeSeriesSplit CV
- [x] MLflow tracking of params, metrics, artifacts; artifacts on MinIO

Engineering practice:
- [x] Unit + integration tests (pytest, no Docker required)
- [x] `ruff` lint + `mypy` type checking (covers `dagster/`)
- [x] GitHub Actions CI (test workflow)
- [x] Demo Runbook (CN+EN), User Guide (CN+EN)
- [x] Release readiness docs and v1/v2/v3 release checklists

---

## 8. Real boundaries today (what does NOT yet exist)

Per the current bottleneck list in `TASKS.md`, on top of v2.5 the following are still missing:

| Gap | Consequence |
|---|---|
| Multi-environment model (dev/staging/prod) | Only "local default" exists today; any prod scenario still needs the engineer to hand-fork configs |
| Promotion / rollback discipline | No executable promotion/rollback checklist — only narrative |
| Secrets and access governance | Credentials live in env vars + local defaults; no managed-secret integration |
| SLOs and alerting | No metric pipeline, no alert rules, no incident drill evidence |
| Dataset governance contracts | Owner/SLA/quality_class/consumers for Gold tables not formally captured in repo |
| ML productization discipline | Runs are tracked, but training input → model version → Gold data version lineage fields are not unified |
| Kubernetes / Helm / Terraform path | ADR-007/008 set direction; no chart, no module, no values layering yet |

These gaps are exactly what v3 is meant to address, but **as of 2026-05-05, none of them are in flight**.

---

## 9. Testing and quality

- Unit tests under `tests/test_*.py`:
  - `test_schemas.py` — Pydantic validation
  - `test_quality_checks.py` — Bronze quality functions
  - `test_bronze_writer.py` — Bronze write path
  - `test_transformations.py` / `test_transformation_runs.py` — pure transform tests
  - `test_collectors_ml_and_reports.py` — ingestion + reports
  - `test_trino_sql.py` — Trino REST registration logic
- Integration tests under `tests/integration/`
- Entry: `make test`, `make lint`, `make typecheck`
- Convention: all I/O in tests goes through `unittest.mock.MagicMock` — no Docker needed

---

## 10. Documentation set

`docs/` already forms a fairly complete documentation matrix:

| Category | Files |
|---|---|
| Onboarding | `quickstart.md`, `USER_GUIDE.md` / `USER_GUIDE_EN.md` |
| Demo | `DEMO_RUNBOOK.md` / `DEMO_RUNBOOK_EN.md` |
| Architecture | `architecture.md`, `medallion-model.md`, `DAGSTER_GUIDE.md` |
| Deployment | `deployment.md` |
| Decisions | `decisions/` (16 ADRs) |
| Evolution | `roadmap.md`, `history/timeline.md`, `history/architecture-evolution.md`, `history/v2.5-planning.md`, `history/v3-planning.md` |
| Governance | `governance-v3-matrix.md`, `governance-v3-runbook.md`, `v3-governance-navigation.md`, `v3-spec.md` |
| Release | `V1_RELEASE_CHECKLIST.md`, `V2_RELEASE_CHECKLIST.md`, `V3_RELEASE_CHECKLIST.md`, `release.md`, `release-readiness.md` |
| Self-assessment | `ASSESSMENT_LAKEHOUSE_DAX_ECB.md` |
| Chinese snapshots | `项目快照_2026-03-26.md`, `项目现状总览_2026-05-05.md` (this doc's CN sibling) |

`CLAUDE.md` is the project-level agent guide and stays in sync with the code.

---

## 11. Design philosophy (implicit rules across the repo)

1. **Readability is a first-class citizen** — the stack is deliberately small enough to run on one host, but complete enough to discuss production trade-offs.
2. **Failures must be visible** — Pydantic mismatch, quality breach, asset-check failure → all raise; no soft fallback.
3. **Externalize metadata** — Hive Metastore is the single source of truth for "what table, where, what schema"; metadata never hides inside scripts.
4. **Bronze never updates** — ingestion only appends partitions; corrections happen via new partitions and re-derived silver/gold.
5. **Credentials come from environment** — `os.environ.get()` + `envsubst` templates; no plaintext secrets in the repo.
6. **Time series is time series** — no random CV, no future-leak features, no leakage.
7. **Every ADR records what was rejected** — every architecture decision states the alternative and the reason it lost.

---

## 12. Audience positioning

SoloLakehouse means different things to different readers:

| Reader | What it is to them |
|---|---|
| Platform-engineering candidate | A résumé-grade end-to-end platform work piece an interviewer can fork and run |
| Data lead at a mid-size FI / asset manager | The reference answer for "what can we build at 1/10 the budget without Databricks" |
| Compliance / risk | An auditable sample where lineage, ownership, SLA can be pointed to in concrete files |
| Educator | Live material for explaining Lakehouse internals (Catalog, Iceberg, Medallion, orchestration) |
| Vendor-replacement evaluator | A reference for "can we hold 80% capability without locking into AWS / Azure / Snowflake" |

---

## 13. One-line summary

> **As of 2026-05-05, SoloLakehouse has shipped a small-but-complete open-source Lakehouse reference: orchestration, governance UI, BI, ML tracking, Iceberg Gold all in place — local, readable, modifiable. The next step is to evolve from "reference implementation" toward "enterprise-deliverable", and the critical gaps are multi-environment, secrets governance, SLO/alerting, data contracts, and the K8s deployment path.**

For the evolution roadmap, see `enterprise-evolution-plan-2026-05-05.md`.
