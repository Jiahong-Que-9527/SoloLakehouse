# Agent Guide for SoloLakehouse

This file helps AI coding agents (Cursor, Copilot, etc.)
understand the project quickly. Read this before making any changes.

## What This Project Is

SoloLakehouse is a **reference implementation** of a Lakehouse architecture,
not a framework or library. It demonstrates how platforms like Databricks and
Snowflake work internally, using only open-source tools on a single Docker
Compose node.

**Development target: v1.0** — eight-layer enterprise-style platform built on a five-layer core (see `docs/roadmap.md`). Focus: effortless deployment and later self-serve usability (see Roadmap context below).

**Domain:** Financial data engineering + ML (ECB interest rates + DAX stock index).

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Object Storage | MinIO (S3-compatible) | RELEASE.2025-09-07 |
| Metadata DB | PostgreSQL | 17 |
| Table Catalog | Apache Hive Metastore (standalone) | 4.0.0 |
| Query Engine | Trino | 480 |
| ML Tracking | MLflow | 3.10.1 |
| Language | Python | 3.11+ |
| Validation | Pydantic v2 | 2.12.5 |
| Data Format | Parquet (snappy) via PyArrow | 23.0.1 |
| Logging | structlog | 25.5.0 |
| Testing | pytest | 9.0.2 |

## Commands

```bash
make up          # Start all Docker services + init MinIO buckets (no host deps)
make down        # Stop services (data preserved in volumes)
make pipeline    # Run the full ingestion → transform → ML pipeline
make verify      # Health-check all services
make test        # Run unit tests (pytest, no Docker needed)
make clean       # Stop services + delete all data volumes
```

## Project Layout

```
ingestion/
  collectors/         # One class per data source (ECBCollector, DAXCollector)
  schema/             # Pydantic v2 models for record validation
  quality/            # Bronze-layer quality check functions
  bronze_writer.py    # Writes validated data to MinIO as Parquet

transformations/
  ecb_bronze_to_silver.py   # ECB: type cleanup, forward-fill, rate_change_bps
  dax_bronze_to_silver.py   # DAX: weekend filter, daily_return
  silver_to_gold_features.py # Join ECB+DAX, build event-study features

ml/
  train_ecb_dax_model.py    # XGBoost/LightGBM with TimeSeriesSplit CV
  evaluate.py               # MLflow experiment runner (multiple hyperparams)

scripts/
  run-pipeline.py           # End-to-end orchestrator (linear, not DAG)
  verify-setup.py           # Service health checks
  init-minio.sh             # Legacy bucket init (now handled by minio-init container)
  trino-entrypoint.sh       # envsubst for Trino catalog config

config/
  trino/catalog/hive.properties  # Template — uses ${S3_ACCESS_KEY}/${S3_SECRET_KEY}
  trino/config.properties        # Trino coordinator settings
  postgres/init.sql              # Creates hive_metastore + mlflow databases

docker/
  docker-compose.yml        # All 5 services
  hive-metastore/           # Custom Dockerfile + entrypoint (envsubst)
  mlflow/                   # Custom Dockerfile

tests/                      # Unit tests (mocked I/O, no Docker needed)
docs/                       # See docs/README.md — architecture, ADRs, roadmap, deployment
data/sample/                # Committed sample CSV for DAX
```

## Architecture Patterns — Follow These When Adding Code

### Collector Pattern (ingestion/collectors/)

```python
class NewCollector:
    def __init__(self, minio_client, config: dict):
        self.minio = minio_client
        self.bronze_writer = BronzeWriter(minio_client)

    def _fetch_data(self, ...) -> list | pd.DataFrame:
        """Pull from source. Use structlog for logging."""

    def _validate_records(self, raw_data) -> tuple[list, list]:
        """Validate each record against a Pydantic schema.
        Returns (valid_dicts, rejected_dicts)."""

    def collect(self, ...) -> dict:
        """Orchestrate: fetch → validate → write Bronze.
        Returns summary dict with counts."""
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

2. **Orchestration function** (reads MinIO, calls transform, writes MinIO):
   ```python
   def run(minio_client, bucket="sololakehouse") -> str:
       # read Bronze Parquet(s) → transform → write Silver Parquet
       return silver_path
   ```

### Testing Pattern (tests/)

- `class TestXxx` grouping, plain pytest (no unittest.TestCase)
- Mock MinIO with `unittest.mock.MagicMock`
- Test pure transform functions with small synthetic DataFrames
- Test schemas for both valid and invalid inputs
- Helper functions like `make_ecb_bronze()` for test data

### Logging Pattern

```python
import structlog
logger = structlog.get_logger()

logger.info("event_name_snake_case", rows=100, path="bronze/ecb/...")
```

- Event names: `snake_case`
- Context: key-value pairs, not formatted strings
- Log at step boundaries with counts

### MinIO / Parquet I/O Pattern

```python
# Write
buffer = BytesIO()
pq.write_table(pa.Table.from_pandas(df), buffer, compression="snappy")
buffer.seek(0)
minio.put_object(bucket, path, buffer, length=buffer.getbuffer().nbytes)

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

## Data Flow (Medallion)

```
ECB API / DAX CSV
    → Bronze (raw Parquet, partitioned by ingestion_date, immutable)
    → Silver (cleaned, typed, deduped, derived fields)
    → Gold   (ML-ready feature table: one row per ECB event)
    → MLflow (XGBoost/LightGBM experiments with TimeSeriesSplit CV)
```

MinIO bucket: `sololakehouse` (paths: `bronze/`, `silver/`, `gold/`)
MLflow bucket: `mlflow-artifacts`

## Key Design Decisions

- **Docker Compose, not K8s** — single-node reference; K8s is v3 (ADR-001)
- **Trino, not DuckDB** — federation + Hive metadata (ADR-002)
- **Parquet, not Delta Lake** — no ACID overkill for append-only batch workloads (ADR-003)
- **ECB/DAX data** — public APIs, temporal structure, no API keys (ADR-004)
- **No Prometheus/Grafana until post-core** — meaningful metrics require custom instrumentation (ADR-005)
- **TimeSeriesSplit** — no random CV on time-series data (look-ahead bias)
- **Quality checks raise exceptions** — fail-fast, not silent degradation

## Things to Watch Out For

- `config/trino/catalog/hive.properties` is a **template** with `${VAR}` placeholders — envsubst runs at container startup via `scripts/trino-entrypoint.sh`
- PostgreSQL is shared by Hive Metastore AND MLflow (two databases: `hive_metastore`, `mlflow`)
- Bronze data is immutable — never update in place, always write new partitions
- Tests run without Docker — they mock all external services
- The `version: "3.8"` field was intentionally removed from docker-compose.yml (deprecated in Compose V2)

## Roadmap context

Canonical tables and v1+ milestones: **`docs/roadmap.md`**. Detailed task list: **`docs/EVOLVING_PLAN.md`**. Backlog: **`TASKS.md`**.

| Version | Theme | Status |
|---------|-------|--------|
| **v1.0** | Full platform + Effortless Deployment (8-layer target, one-command setup, health checks, troubleshooting) | **current** |
| **v2.0** | Orchestrated Platform (Dagster DAG, retries/policies, scheduling, UI) + self-serve usability | planned |
| **v3.0** | Production Infrastructure (Kubernetes/Helm, Terraform, cloud provisioning) | planned |
| **v4.0** | Self-Serve Usability (docs-first onboarding, repeatable verification, clearer failure modes) | planned |

Ingestion-hardening and related tasks: **`docs/EVOLVING_PLAN.md`** Phase 1 (historical label “v0.2”).

## History maintenance (required)

To preserve long-term evolution context across v2/v3/v4, every major milestone update must also update `docs/history/`.

Required actions per version:

1. Update `docs/history/timeline.md` with milestone status, delivered scope, and next decision gate.
2. Update `docs/history/architecture-evolution.md` with architecture choices made, alternatives rejected, and rationale.
3. Create or update a version planning note using `docs/history/planning-template.md` (for example `docs/history/v2-planning.md`) before implementation starts.
4. Cross-link version artifacts: release tag, release notes, checklist, and key ADRs.
