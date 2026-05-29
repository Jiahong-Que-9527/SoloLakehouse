# Agent Guide for SoloLakehouse

This file helps AI coding agents (Cursor, Copilot, etc.)
understand the project quickly. Read this before making any changes.

## What This Project Is

SoloLakehouse is a **reference implementation** of a Lakehouse architecture,
not a framework or library. It demonstrates how platforms like Databricks and
Snowflake work internally, using only open-source tools on a single Docker
Compose node.

**Current: v2.5 single-track baseline** — orchestrated platform with Dagster assets/schedules/UI, **full-stack Iceberg** (Bronze/Silver/Gold all written via pyiceberg), and mandatory OpenMetadata + Superset in the default stack (see `docs/roadmap.md`).  
**Next target (v3.0):** production infrastructure and governance hardening (multi-environment deployment, secrets/access governance, SLO/alerting, release promotion controls).

**Domain:** Financial data engineering + ML (ECB interest rates + DAX stock index).

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Object Storage | MinIO (S3-compatible) | RELEASE.2025-09-07T16-13-09Z |
| Metadata DB | PostgreSQL | 17 |
| Table Catalog | Apache Hive Metastore (standalone) | 4.0.0 |
| Query Engine | Trino (Hive + Iceberg catalogs) | 480 |
| Table format (all layers) | Apache Iceberg via pyiceberg (Bronze/Silver/Gold) | ≥0.8.0 |
| Data catalog | OpenMetadata | 1.5.x |
| BI / SQL UI | Apache Superset | 6.0.0 |
| ML Tracking | MLflow | 3.10.1 |
| Orchestration | Dagster | 1.7.x (Python < 3.13) / 1.12.x (Python ≥ 3.13) |
| Language | Python | 3.13+ |
| Validation | Pydantic v2 | 2.12.5 |
| Data Format | Iceberg (Parquet data files, snappy) for all layers; PyArrow 23.0.1 internally | — |
| Logging | structlog | 25.5.0 |
| Testing | pytest | 9.0.2 |

## Commands

```bash
make up          # Start all Docker services + init MinIO buckets + create Iceberg namespaces/tables
make down        # Stop services (data preserved under docker/data/)
make pipeline    # Run Dagster full_pipeline_job (v2.5 default path)
make dagster-ui  # Open Dagster UI (http://localhost:3000)
make verify      # Health-check all services
make test        # Run unit tests (pytest, no Docker needed)
make lint        # ruff (CI)
make typecheck   # mypy on ingestion/, transformations/, ml/, scripts/, dagster/ (install requirements-dagster.txt so the local dagster/ folder does not shadow PyPI dagster)
make clean       # Stop services + delete docker/data/ + purge legacy named Docker volumes
```

## Project Layout

```
ingestion/
  collectors/         # One class per data source (ECBCollector, DAXCollector)
  schema/             # Pydantic v2 models for record validation
  quality/            # Bronze-layer quality check functions
  bronze_writer.py    # Writes validated data to Iceberg (pyiceberg append_table)
  iceberg_io.py       # Core I/O: append_table, overwrite_table, scan_table, get_catalog
  iceberg_schemas.py  # Iceberg Schema + PartitionSpec for all six tables
  trino_sql.py        # Trino REST utility (execute_trino_sql only; Hive staging removed)

transformations/
  ecb_bronze_to_silver.py   # ECB: type cleanup, forward-fill, rate_change_bps
  dax_bronze_to_silver.py   # DAX: weekend filter, daily_return
  silver_to_gold_features.py # Join ECB+DAX, build event-study features

ml/
  train_ecb_dax_model.py    # XGBoost/LightGBM with TimeSeriesSplit CV
  evaluate.py               # MLflow experiment runner (multiple hyperparams)

scripts/
  verify-setup.py           # Service health checks
  bootstrap-postgres.py     # Ensure DBs exist; TCP password check + align vs .env after docker-exec bootstrap
  prepare-docker-data-dirs.sh   # mkdir + perms for docker/data bind mounts
  purge-legacy-docker-volumes.sh # Remove pre-bind-mount Docker named volumes (after down)
  init-minio.sh             # Legacy bucket init (now handled by minio-init container)
  trino-entrypoint.sh       # Expands all Trino catalog *.properties templates

config/
  trino/catalog/hive.properties   # Template — uses ${S3_ACCESS_KEY}/${S3_SECRET_KEY}
  trino/catalog/iceberg.properties # Iceberg connector + Hive Metastore catalog
  trino/config.properties        # Trino coordinator settings
  postgres/init.sql              # Creates hive_metastore + mlflow databases

docker/
  docker-compose.yml        # Core platform services
  docker-compose.openmetadata.yml # OpenMetadata stack (included by default in Makefile)
  docker-compose.superset.yml # Superset stack (included by default in Makefile)
  data/                     # Bind-mounted runtime state (MinIO, Postgres, Dagster, OM; contents gitignored)
  dagster/                  # Dagster image build context
  hive-metastore/           # Custom Dockerfile + entrypoint (envsubst)
  mlflow/                   # Custom Dockerfile
  superset/                 # Custom Superset image + bootstrap config

dagster/
  assets.py                 # Software-defined assets, sensor, asset checks
  resources.py              # IcebergCatalogResource + config resources
  definitions.py            # Jobs/schedule/definitions registry
  workspace.yaml            # Dagster code location workspace
  dagster.yaml              # Dagster instance config (PostgreSQL storage)

tests/                      # Unit tests (mocked I/O, no Docker needed)
docs/                       # See docs/README.md — architecture, ADRs, roadmap, deployment
data/sample/                # Committed sample CSV for DAX
```

## Architecture Patterns — Follow These When Adding Code

### Collector Pattern (ingestion/collectors/)

```python
class NewCollector:
    def __init__(self, catalog: Catalog, bucket: str | None = None):
        self.catalog = catalog
        self.bronze_writer = BronzeWriter(catalog)

    def _fetch_data(self, ...) -> list | pd.DataFrame:
        """Pull from source. Use structlog for logging."""

    def _validate_records(self, raw_data) -> tuple[list, list]:
        """Validate each record against a Pydantic schema.
        Returns (valid_dicts, rejected_dicts)."""

    def _already_ingested_today(self) -> bool:
        """Check iceberg_io.scan_table for today's _ingestion_timestamp."""

    def collect(self, ...) -> dict:
        """Orchestrate: fetch → validate → write Bronze (Iceberg append).
        Returns summary dict with counts and iceberg: path."""
```

### Schema Pattern (ingestion/schema/)

```python
from pydantic import BaseModel, field_validator, model_validator

class NewRecord(BaseModel):
    field: type

    @field_validator("field")
    @classmethod
    def validate_field(cls, v):
        if bad: raise ValueError("reason")
        return v

    @model_validator(mode="after")    # for cross-field checks
    def check_consistency(self):
        if self.high < self.low: raise ValueError("...")
        return self
```

- Use `.model_dump()` (NOT `.dict()`) — this is Pydantic v2.

### Transformation Pattern (transformations/)

Every transformation file has two functions:

1. **Pure transform function** (testable, no I/O):
   ```python
   def transform_X_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
       df = df.copy()  # never mutate input
       # type conversions → filter → sort → derive fields → dedup → quality check
       return df[["col1", "col2", ...]]  # explicit column subset
   ```

2. **Orchestration function** (reads Iceberg, calls transform, writes Iceberg):
   ```python
   def run(catalog: Catalog) -> dict[str, object]:
       df = scan_table(catalog, "bronze", "source_name")
       silver_df = transform_X_bronze_to_silver(df)
       overwrite_table(catalog, "silver", "source_name_cleaned", silver_df, SILVER_SCHEMA)
       return {"table": "iceberg:silver.source_name_cleaned", "row_count": len(silver_df)}
   ```

### Iceberg I/O Pattern (ingestion/iceberg_io.py)

```python
from ingestion.iceberg_io import append_table, overwrite_table, scan_table, get_catalog

catalog = get_catalog()  # reads HIVE_METASTORE_URI, MINIO_ENDPOINT, S3_ACCESS_KEY from env

# Bronze (immutable append)
append_table(catalog, "bronze", "ecb_rates", df, BRONZE_ECB_RATES_SCHEMA, BRONZE_ECB_RATES_PARTITION)

# Silver / Gold (full overwrite on each run)
overwrite_table(catalog, "silver", "ecb_rates_cleaned", df, SILVER_ECB_RATES_SCHEMA)

# Read
df = scan_table(catalog, "gold", "ecb_dax_features")
```

### Testing Pattern (tests/)

- `class TestXxx` grouping, plain pytest (no unittest.TestCase)
- Mock `pyiceberg.Catalog` with `unittest.mock.MagicMock`; monkeypatch `iceberg_io.scan_table` / `iceberg_io.overwrite_table` to capture writes
- Test pure transform functions with small synthetic DataFrames
- Test schemas for both valid and invalid inputs
- Helper functions like `make_gold_training_frame()` for test data

### Logging Pattern

```python
import structlog
logger = structlog.get_logger()

logger.info("event_name_snake_case", rows=100, table="iceberg:bronze.ecb_rates")
```

- Event names: `snake_case`
- Context: key-value pairs, not formatted strings
- Log at step boundaries with counts

### MinIO / Parquet direct I/O

**No longer used in the pipeline** — all writes go through `iceberg_io`.
If you need a raw MinIO client for tooling only:

```python
# Read
response = minio.get_object(bucket, path)
df = pd.read_parquet(BytesIO(response.read()))
response.close()
response.release_conn()
```

### Environment Variables

All credentials and endpoints come from env vars with local-dev defaults:

```python
endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
user = os.environ.get("MINIO_ROOT_USER", "sololakehouse")
```

Never hardcode credentials. Config files that need credentials use `envsubst`
templates (see `config/trino/catalog/hive.properties`).

## Data Flow (Medallion — all Iceberg)

```
ECB API / DAX CSV
    → Bronze Iceberg (iceberg.bronze.{ecb_rates,dax_daily})
        append-only, day-partitioned on _ingestion_timestamp
    → Silver Iceberg (iceberg.silver.{ecb_rates_cleaned,dax_daily_cleaned})
        full overwrite each run; cleaned, typed, deduped, derived fields
    → Gold Iceberg (iceberg.gold.ecb_dax_features)
        full overwrite each run; one row per ECB rate-change event
        — readable via Trino: SELECT * FROM iceberg.gold.ecb_dax_features
    → MLflow (XGBoost/LightGBM experiments with TimeSeriesSplit CV)
        reads Gold from Trino (preferred) or pyiceberg scan_table
```

All writes go through `ingestion/iceberg_io.py` (pyiceberg HiveCatalog).
`ingestion/trino_sql.py` is now a thin utility for ad-hoc Trino SQL only
(Hive staging / CTAS removed — superseded by pyiceberg direct writes, ADR-020).

MinIO bucket: `sololakehouse` (Iceberg warehouse: `s3://sololakehouse/warehouse/`)
MLflow bucket: `mlflow-artifacts`

## Key Design Decisions

- **Docker Compose, not K8s** — single-node reference; K8s is v3 (ADR-001)
- **Trino, not DuckDB** — federation + Hive metadata (ADR-002)
- **Iceberg for all layers via pyiceberg** — replaces Parquet+Hive staging; eliminates write-path duplication (ADR-020 supersedes ADR-003 and ADR-013)
- **ECB/DAX data** — public APIs, temporal structure, no API keys (ADR-004)
- **No Prometheus/Grafana until post-core** — meaningful metrics require custom instrumentation (ADR-005)
- **TimeSeriesSplit** — no random CV on time-series data (look-ahead bias)
- **Quality checks raise exceptions** — fail-fast, not silent degradation
- **v3 governance-first productionization** — environment promotion, secrets/access governance, SLO-driven operations, and auditability are mandatory before claiming production readiness

## Things to Watch Out For

- `config/trino/catalog/*.properties` are **templates** with `${VAR}` placeholders — bash `eval` expansion runs at container startup via `scripts/trino-entrypoint.sh` (includes `hive` + `iceberg`)
- PostgreSQL is shared by Hive Metastore AND MLflow (two databases: `hive_metastore`, `mlflow`)
- Bronze data is immutable — `BronzeWriter` calls `iceberg_io.append_table`; never overwrite
- Iceberg namespaces/tables are bootstrapped by `scripts/init-iceberg-namespaces.py` (called by `make up`); if you reset the Hive Metastore run `make init-iceberg` to recreate them
- `HIVE_METASTORE_URI=thrift://localhost:9083` in `.env` is for host-side scripts; Docker services override to `thrift://hive-metastore:9083`
- Tests run without Docker — they mock `iceberg_io.scan_table` / `iceberg_io.overwrite_table`
- The `version: "3.8"` field was intentionally removed from docker-compose.yml (deprecated in Compose V2)

## Roadmap context

Canonical tables and v1+ milestones: **`docs/roadmap.md`**. Active backlog: **`TASKS.md`**. Historical planning: **`docs/history/`**.

| Version | Theme | Status |
|---------|-------|--------|
| **v1.0** | Full platform + Effortless Deployment (8-layer target, one-command setup, health checks, troubleshooting) | delivered |
| **v2.5** | Orchestrated platform baseline (Dagster + Iceberg + OpenMetadata + Superset) | **current** |
| **v3.0** | Production Infrastructure + Governance (Kubernetes/Helm, Terraform, environment promotion, secrets/access controls, SLO/alerting) | planned |
| **v4.0** | Self-Serve Usability (docs-first onboarding, repeatable verification, clearer failure modes) | planned |

Ingestion-hardening and related tasks: see **`TASKS.md`** and **`docs/history/v2-planning.md`**.

## History maintenance (required)

To preserve long-term evolution context across v2/v3/v4, every major milestone update must also update `docs/history/`.

Required actions per version:

1. Update `docs/history/timeline.md` with milestone status, delivered scope, and next decision gate.
2. Update `docs/history/architecture-evolution.md` with architecture choices made, alternatives rejected, and rationale.
3. Create or update a version planning note using `docs/history/planning-template.md` (for example `docs/history/v2-planning.md`) before implementation starts.
4. Cross-link version artifacts: release tag, release notes, checklist, and key ADRs.
