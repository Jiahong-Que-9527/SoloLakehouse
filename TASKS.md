# TASKS.md — SoloLakehouse v1.0 Implementation

> **For agents:** Execute tasks in order within each block. Each task is self-contained.
> Blocks B0–B5 must be completed before B6 (tests). B7 (CI) after B6.
> Mark tasks `[x]` when done. Skip nothing — every task maps to a required v1.0 deliverable.
>
> **Key references:**
> - Architecture: `docs/architecture.md`, `docs/medallion-model.md`
> - Patterns: `CLAUDE.md` (Collector, Schema, Transformation, Logging, MinIO I/O patterns)
> - Detailed phase plan: `docs/EVOLVING_PLAN.md`
> - Roadmap: `docs/roadmap.md`

---

## Block 0 — Project Skeleton

### B0-1 `requirements.txt`

Create `requirements.txt` at repo root. Pin all versions exactly.

```
minio==7.2.7
pandas==2.2.2
pyarrow==15.0.2
pydantic==2.7.4
structlog==24.1.0
requests==2.32.3
xgboost==2.0.3
lightgbm==4.3.0
mlflow==2.13.0
scikit-learn==1.5.0
pytest==8.2.0
pytest-cov==5.0.0
ruff==0.4.4
mypy==1.10.0
```

### B0-2 `.env.example`

Create `.env.example` at repo root with all required variables and safe local-dev defaults:

```
MINIO_ROOT_USER=sololakehouse
MINIO_ROOT_PASSWORD=sololakehouse123
MINIO_ENDPOINT=localhost:9000
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
PG_PORT=5432
S3_ACCESS_KEY=sololakehouse
S3_SECRET_KEY=sololakehouse123
S3_ENDPOINT=http://minio:9000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
MLFLOW_TRACKING_URI=http://localhost:5000
AWS_ACCESS_KEY_ID=sololakehouse
AWS_SECRET_ACCESS_KEY=sololakehouse123
```

### B0-3 `Makefile`

Create `Makefile` at repo root. All `docker compose` commands use `-f docker/docker-compose.yml`.

Targets:
- `up`: `docker compose -f docker/docker-compose.yml up -d` then print service URLs
- `down`: `docker compose -f docker/docker-compose.yml down`
- `clean`: `docker compose -f docker/docker-compose.yml down -v`
- `pipeline`: `python scripts/run-pipeline.py`
- `verify`: `python scripts/verify-setup.py`
- `test`: `pytest tests/ -v --tb=short --ignore=tests/integration`
- `test-cov`: `pytest tests/ -v --tb=short --ignore=tests/integration --cov=ingestion --cov=transformations --cov=ml --cov-report=term-missing --cov-fail-under=70`
- `test-cov-html`: same as `test-cov` with `--cov-report=html`
- `test-integration`: `pytest tests/integration/ -v --tb=short -m integration`
- `lint`: `ruff check .`
- `typecheck`: `mypy ingestion/ transformations/ ml/ scripts/`
- `setup`: check docker running → copy `.env.example` if `.env` missing → `docker compose pull` → `make up`
- `wait`: poll `make verify` every 10s, 5-min timeout, print progress dots

### B0-4 `.gitignore`

Create `.gitignore`:

```
.venv/
__pycache__/
*.pyc
*.pyo
.env
htmlcov/
.coverage
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
data/bronze/
data/silver/
data/gold/
```

### B0-5 Package `__init__.py` files

Create empty `__init__.py` in:
- `ingestion/`
- `ingestion/collectors/`
- `ingestion/schema/`
- `ingestion/quality/`
- `transformations/`
- `ml/`
- `tests/`
- `tests/integration/`

---

## Block 1 — Docker Infrastructure

### [x] B1-1 `docker/docker-compose.yml`

Create with 6 services. No top-level `version:` key (Compose V2).

**minio:**
```yaml
image: minio/minio:RELEASE.2024-06-13T22-53-53Z
container_name: slh-minio
environment:
  MINIO_ROOT_USER: ${MINIO_ROOT_USER}
  MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
command: server /data --console-address ":9001"
ports: ["9000:9000", "9001:9001"]
volumes: [minio_data:/data]
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```

**minio-init:**
```yaml
image: minio/mc:latest
container_name: slh-minio-init
depends_on:
  minio: {condition: service_healthy}
entrypoint: ["/bin/sh", "/init-minio.sh"]
volumes: ["./scripts/init-minio.sh:/init-minio.sh:ro"]
environment:
  MINIO_ROOT_USER: ${MINIO_ROOT_USER}
  MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
restart: "no"
```

**postgres:**
```yaml
image: postgres:15
container_name: slh-postgres
environment:
  POSTGRES_USER: ${POSTGRES_USER}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
ports: ["5432:5432"]
volumes:
  - postgres_data:/var/lib/postgresql/data
  - ./config/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```

**hive-metastore:**
```yaml
build: ./hive-metastore
container_name: slh-hive-metastore
depends_on:
  postgres: {condition: service_healthy}
  minio: {condition: service_healthy}
environment:
  DB_HOST: postgres
  DB_USER: ${POSTGRES_USER}
  DB_PASS: ${POSTGRES_PASSWORD}
  S3_ENDPOINT: ${S3_ENDPOINT}
  S3_ACCESS_KEY: ${S3_ACCESS_KEY}
  S3_SECRET_KEY: ${S3_SECRET_KEY}
ports: ["9083:9083"]
healthcheck:
  test: ["CMD", "bash", "-c", "echo 'status' | nc -w 2 localhost 9083 || exit 1"]
  interval: 15s
  timeout: 5s
  retries: 5
  start_period: 60s
```

**trino:**
```yaml
image: trinodb/trino:435
container_name: slh-trino
depends_on:
  hive-metastore: {condition: service_healthy}
  minio: {condition: service_healthy}
environment:
  S3_ACCESS_KEY: ${S3_ACCESS_KEY}
  S3_SECRET_KEY: ${S3_SECRET_KEY}
ports: ["8080:8080"]
volumes:
  - ./config/trino/config.properties:/etc/trino/config.properties:ro
  - ./config/trino/catalog:/etc/trino/catalog:ro
  - ./scripts/trino-entrypoint.sh:/usr/local/bin/trino-entrypoint.sh:ro
entrypoint: ["/bin/bash", "/usr/local/bin/trino-entrypoint.sh"]
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/v1/info"]
  interval: 15s
  timeout: 5s
  retries: 10
  start_period: 90s
```

**mlflow:**
```yaml
build: ./mlflow
container_name: slh-mlflow
depends_on:
  postgres: {condition: service_healthy}
  minio: {condition: service_healthy}
environment:
  MLFLOW_S3_ENDPOINT_URL: ${MLFLOW_S3_ENDPOINT_URL}
  AWS_ACCESS_KEY_ID: ${S3_ACCESS_KEY}
  AWS_SECRET_ACCESS_KEY: ${S3_SECRET_KEY}
ports: ["5000:5000"]
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 15s
  timeout: 5s
  retries: 5
  start_period: 30s
```

**volumes:** `minio_data:`, `postgres_data:`

### [x] B1-2 `config/postgres/init.sql`

```sql
CREATE DATABASE hive_metastore;
CREATE DATABASE mlflow;
```

### [x] B1-3 `docker/hive-metastore/Dockerfile`

Use `apache/hive:4.0.0` as base. Copy a custom `entrypoint.sh` that:
1. Runs `envsubst` on `metastore-site.xml.template` → `metastore-site.xml`
2. Runs `schematool -dbType postgres -initSchemaTo 4.0.0 || true` (idempotent)
3. Starts `hive --service metastore`

The `metastore-site.xml.template` must include Postgres JDBC connection using `${DB_HOST}`, `${DB_USER}`, `${DB_PASS}` and S3/MinIO config using `${S3_ENDPOINT}`, `${S3_ACCESS_KEY}`, `${S3_SECRET_KEY}`.

### [x] B1-4 `docker/mlflow/Dockerfile`

```dockerfile
FROM python:3.11-slim
RUN pip install mlflow==2.13.0 psycopg2-binary boto3
CMD ["mlflow", "server",
     "--host", "0.0.0.0",
     "--port", "5000",
     "--backend-store-uri", "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres:5432/mlflow",
     "--default-artifact-root", "s3://mlflow-artifacts/"]
```

Use a shell-form entrypoint script that reads env vars at runtime. The `--backend-store-uri` and `--default-artifact-root` must be built from env vars in the entrypoint, not hardcoded.

### [x] B1-5 `config/trino/config.properties`

```properties
coordinator=true
node-scheduler.include-coordinator=true
http-server.http.port=8080
discovery.uri=http://localhost:8080
query.max-memory=1GB
query.max-memory-per-node=512MB
```

### [x] B1-6 `config/trino/catalog/hive.properties`

This is a template file — `${VAR}` placeholders are replaced by `envsubst` at container startup:

```properties
connector.name=hive
hive.metastore.uri=thrift://hive-metastore:9083
hive.s3.endpoint=http://minio:9000
hive.s3.path-style-access=true
hive.s3.aws-access-key=${S3_ACCESS_KEY}
hive.s3.aws-secret-key=${S3_SECRET_KEY}
hive.s3.ssl.enabled=false
hive.non-managed-table-writes-enabled=true
hive.storage-format=PARQUET
```

### [x] B1-7 `scripts/trino-entrypoint.sh`

```bash
#!/bin/bash
set -e
# Replace ${VAR} placeholders in catalog config
envsubst < /etc/trino/catalog/hive.properties > /tmp/hive.properties
cp /tmp/hive.properties /etc/trino/catalog/hive.properties
# Start Trino
exec /usr/lib/trino/bin/run-trino
```

### [x] B1-8 `scripts/init-minio.sh`

```bash
#!/bin/sh
set -e
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing local/sololakehouse
mc mb --ignore-existing local/mlflow-artifacts
echo "MinIO buckets initialized."
```

---

## Block 2 — Ingestion Layer

### [x] B2-1 `ingestion/exceptions.py`

Define two custom exception classes:

```python
class CollectorUnavailableError(Exception):
    """Raised when a data source is unreachable after all retries."""

class StepError(Exception):
    """Raised when a pipeline step fails. Wraps original exception."""
    def __init__(self, step_number: int, step_name: str, original: Exception):
        self.step_number = step_number
        self.step_name = step_name
        self.original = original
        super().__init__(f"Step {step_number} ({step_name}) failed: {original}")
```

### [x] B2-2 `ingestion/schema/ecb_schema.py`

Pydantic v2 model for a single ECB MRO rate observation.

Fields:
- `observation_date: datetime.date` — parsed from ISO string
- `rate_pct: float` — MRO rate as percentage (e.g. 4.5)
- `_ingestion_timestamp: datetime.datetime` — set by default factory
- `_source: str` — default `"ECB_SDW"`

Validators:
- `observation_date` must not be in the future
- `rate_pct` must be in range -5.0 to 20.0
- Use `model_dump()` (not `.dict()`) when serialising

### [x] B2-3 `ingestion/schema/dax_schema.py`

Pydantic v2 model for a single DAX daily OHLCV record.

Fields:
- `observation_date: datetime.date`
- `open_price: float`
- `high_price: float`
- `low_price: float`
- `close_price: float`
- `volume: float`
- `_ingestion_timestamp: datetime.datetime` — default factory
- `_source: str` — default `"DAX_SAMPLE"`

Validators:
- `high_price >= low_price` (model_validator)
- `open_price > 0`, `close_price > 0`
- `observation_date` must not be in the future

### [x] B2-4 `ingestion/quality/bronze_checks.py`

Implement these functions (all raise `ValueError` on failure):

```python
def check_no_nulls(df: pd.DataFrame, columns: list[str]) -> None:
    """Raise if any of the specified columns contain nulls."""

def check_date_range(df: pd.DataFrame, date_col: str,
                     min_date: str, max_date: str) -> None:
    """Raise if dates fall outside [min_date, max_date]."""

def check_no_future_dates(df: pd.DataFrame, date_col: str) -> None:
    """Raise if any date in date_col is later than datetime.date.today()."""

def check_date_continuity(df: pd.DataFrame, date_col: str,
                          max_gap_days: int) -> None:
    """Raise if any gap between consecutive dates exceeds max_gap_days."""

def check_schema_version(df: pd.DataFrame, expected_columns: list[str]) -> None:
    """Raise if df is missing any column from expected_columns."""

def run_ecb_bronze_checks(df: pd.DataFrame) -> None:
    """Run all ECB-specific bronze checks. Calls above functions with ECB params:
    - check_no_nulls on ['observation_date', 'rate_pct']
    - check_no_future_dates on 'observation_date'
    - check_date_continuity with max_gap_days=180
    - check_schema_version with ECB expected columns
    """

def run_dax_bronze_checks(df: pd.DataFrame) -> None:
    """Run all DAX-specific bronze checks. Calls above functions with DAX params:
    - check_no_nulls on OHLCV columns
    - check_no_future_dates on 'observation_date'
    - check_date_continuity with max_gap_days=5
    - check_schema_version with DAX expected columns
    """
```

### [x] B2-5 `ingestion/bronze_writer.py`

`BronzeWriter` class with two methods:

```python
class BronzeWriter:
    def __init__(self, minio_client, bucket: str = "sololakehouse"):
        ...

    def write(self, df: pd.DataFrame, source: str,
              ingestion_date: str | None = None) -> str:
        """Write df as Parquet (snappy) to:
        bronze/{source}/ingestion_date={YYYY-MM-DD}/{source}.parquet
        Returns the object path. Uses today's date if ingestion_date not given."""

    def write_rejected(self, records: list[dict], source: str,
                       ingestion_date: str | None = None) -> str | None:
        """Write rejected records to:
        bronze/rejected/source={SOURCE}/ingestion_date={YYYY-MM-DD}/rejected.parquet
        Each record must include a 'rejection_reason' string field.
        Returns path or None if records list is empty."""
```

Use the MinIO/PyArrow I/O pattern from `CLAUDE.md`:
```python
buffer = BytesIO()
pq.write_table(pa.Table.from_pandas(df), buffer, compression="snappy")
buffer.seek(0)
minio.put_object(bucket, path, buffer, length=buffer.getbuffer().nbytes)
```

### [x] B2-6 `ingestion/collectors/ecb_collector.py`

`ECBCollector` following the Collector Pattern in `CLAUDE.md`.

**ECB SDW API endpoint:**
`https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.RT0.BB.R.1.YYYY.R.A`
Query params: `?format=jsondata&startPeriod=1999-01-01`

**Implementation requirements:**
- `_fetch_data()`: HTTP GET with 3 retries (10s timeout each, 2s between retries). Raises `CollectorUnavailableError` after all retries exhausted.
- `_validate_records()`: validate each record against `ECBRecord`. Returns `(valid, rejected)` tuples. Rejected records get a `rejection_reason` field with the Pydantic error message.
- Incremental check: before writing, list `bronze/ecb_rates/` objects and find latest `ingestion_date=YYYY-MM-DD` partition. If today's date already has a partition, log `ecb_already_ingested_today` and return `{"status": "skipped", "reason": "already_ingested_today"}`.
- `collect()` orchestrates: fetch → validate → `run_ecb_bronze_checks()` → `bronze_writer.write()` → `bronze_writer.write_rejected()`. Returns summary dict: `{"status": "ok", "valid_count": N, "rejected_count": M, "path": "...", "rejected_path": "..." | None}`.
- Log with structlog: `ecb_fetch_started`, `ecb_validation_complete`, `ecb_ingestion_complete`.

### [x] B2-7 `ingestion/collectors/dax_collector.py`

`DAXCollector` following the Collector Pattern in `CLAUDE.md`.

**Data source:** reads `data/sample/dax_daily_sample.csv` (path configurable via constructor).

Expected CSV columns: `date,open,high,low,close,volume`

**Implementation requirements:**
- `_fetch_data()`: `pd.read_csv()`, rename columns to schema names (`date` → `observation_date`, etc.).
- `_validate_records()`: validate each row against `DAXRecord`. Returns `(valid, rejected)`.
- Incremental check: same pattern as ECBCollector, checks `bronze/dax_daily/` for today's partition. Returns `{"status": "skipped", "reason": "already_ingested_today"}` if exists.
- `collect()`: fetch → validate → `run_dax_bronze_checks()` → write. Returns same summary dict pattern.
- Log: `dax_fetch_started`, `dax_validation_complete`, `dax_ingestion_complete`.

---

## Block 3 — Transformation Layer

### [x] B3-1 `transformations/quality_report.py`

```python
def run_silver_quality_report(df: pd.DataFrame, layer_name: str) -> dict:
    """Return quality metrics dict. Log result with structlog. Do NOT raise.

    Returns:
    {
        "layer": layer_name,
        "row_count": int,
        "null_counts": {col: int, ...},   # only columns with nulls > 0
        "date_range": {"min": str, "max": str},  # ISO format
        "duplicate_count": int
    }
    """
```

The function detects the date column automatically (first column with `date` in its name). Log the full dict via `logger.info("silver_quality_report", **result)`.

### [x] B3-2 `transformations/ecb_bronze_to_silver.py`

**Pure transform function:**
```python
def transform_ecb_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """
    1. Copy df (never mutate input)
    2. Filter: keep only MRO (Main Refinancing Operations) rows if a type column exists
    3. Cast observation_date to datetime.date, rate_pct to float
    4. Sort by observation_date ascending
    5. Forward-fill rate_pct gaps (policy rate holds until next decision)
    6. Add rate_change_bps: (rate_pct - rate_pct.shift(1)) * 100, rounded to 1dp
    7. Drop duplicates on observation_date (keep last)
    8. Drop Bronze metadata columns (_ingestion_timestamp, _source)
    9. Return explicit column subset: ['observation_date', 'rate_pct', 'rate_change_bps']
    """
```

**Orchestration function:**
```python
def run(minio_client, bucket: str = "sololakehouse") -> str:
    """Read all bronze/ecb_rates/ partitions, concat, transform, write silver.
    Write path: silver/ecb_rates_cleaned/ecb_rates_cleaned.parquet
    Call run_silver_quality_report() before returning.
    Returns silver path string."""
```

### [x] B3-3 `transformations/dax_bronze_to_silver.py`

**Pure transform function:**
```python
def transform_dax_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """
    1. Copy df
    2. Cast observation_date to datetime.date; OHLCV to float
    3. Filter out weekends (Saturday=5, Sunday=6)
    4. Sort by observation_date ascending
    5. Add daily_return: (close_price / close_price.shift(1) - 1) * 100, rounded to 4dp
    6. Drop duplicates on observation_date (keep last)
    7. Drop Bronze metadata columns
    8. Return: ['observation_date', 'open_price', 'high_price', 'low_price',
                'close_price', 'volume', 'daily_return']
    """
```

**Orchestration function:** same pattern — read bronze, transform, write silver to `silver/dax_daily_cleaned/dax_daily_cleaned.parquet`, call quality report.

### [x] B3-4 `transformations/silver_to_gold_features.py`

**Pure transform function:**
```python
def build_gold_features(ecb_df: pd.DataFrame, dax_df: pd.DataFrame) -> pd.DataFrame:
    """
    Event-study join: one row per ECB rate-change event.

    1. Filter ecb_df to rows where rate_change_bps != 0 (actual rate changes only)
    2. For each ECB event date, find the nearest DAX trading day (forward, max 3 days)
    3. Build features per event:
       - event_date: ECB decision date
       - rate_change_bps: change in basis points
       - rate_level_pct: rate_pct on event date
       - is_rate_hike: rate_change_bps > 0
       - is_rate_cut: rate_change_bps < 0
       - dax_pre_close: DAX close on the trading day before the event
       - dax_return_1d: DAX daily_return on event day (or next trading day)
       - dax_return_5d: cumulative return over 5 trading days after event
       - dax_volatility_pre_5d: std of daily_return over 5 trading days before event
    4. Drop events where DAX data is not available
    5. Sort by event_date
    6. Return explicit column subset
    """
```

**Orchestration function:** read both silver parquets, call `build_gold_features`, write to `gold/rate_impact_features/ecb_dax_features.parquet`, call quality report.

---

## Block 4 — ML Layer

### [x] B4-1 `ml/train_ecb_dax_model.py`

```python
def train(df: pd.DataFrame, model_type: str = "xgboost",
          params: dict | None = None) -> tuple[Any, dict]:
    """
    Train a binary classifier: predict DAX direction after ECB event.

    Target: dax_return_1d > 0 → 1 (up), else 0 (down)
    Features: rate_change_bps, rate_level_pct, is_rate_hike, is_rate_cut,
              dax_volatility_pre_5d, dax_pre_close

    Use TimeSeriesSplit(n_splits=5) — NO random cross-validation.
    model_type: "xgboost" or "lightgbm"

    Returns (trained_model, metrics_dict).
    metrics_dict keys: accuracy, precision, recall, f1, n_splits, model_type, params
    """
```

### [x] B4-2 `ml/evaluate.py`

```python
def run_experiment_set(minio_client, mlflow_tracking_uri: str,
                       bucket: str = "sololakehouse") -> str:
    """
    Run multiple hyperparameter combinations and log all to MLflow.

    Experiment name: "ecb_dax_impact"
    Hyperparameter grid (run all combinations):
      - model_type: ["xgboost", "lightgbm"]
      - n_estimators: [50, 100, 200]
      - max_depth: [3, 5]

    For each combination:
      1. Call train() from train_ecb_dax_model.py
      2. Log params, metrics, and model artifact to MLflow
      3. Log structlog event: ml_run_complete with run_id and accuracy

    Returns: best run_id (highest accuracy)
    """
```

---

## Block 5 — Scripts

### [x] B5-1 `scripts/run-pipeline.py`

Linear 6-step orchestrator. Key requirements:

```python
# StepError is imported from ingestion.exceptions

def retry_step(fn: Callable, max_attempts: int = 3, delay: float = 5.0) -> Any:
    """Retry fn up to max_attempts times with delay seconds between attempts.
    Re-raises StepError after max attempts exhausted."""

STEPS = [
    (1, "ECB Ingestion",      lambda clients: ECBCollector(...).collect()),
    (2, "DAX Ingestion",      lambda clients: DAXCollector(...).collect()),
    (3, "ECB Bronze→Silver",  lambda clients: ecb_bronze_to_silver.run(...)),
    (4, "DAX Bronze→Silver",  lambda clients: dax_bronze_to_silver.run(...)),
    (5, "Silver→Gold",        lambda clients: silver_to_gold_features.run(...)),
    (6, "ML Experiment",      lambda clients: evaluate.run_experiment_set(...)),
]
```

Rules:
- Steps 1 and 2 use `retry_step(fn, max_attempts=3, delay=5)`.
- Steps 3–6 run once; failure raises `StepError` immediately.
- Each step wrapped in try/except; on failure log `pipeline_step_failed` with step name + error, then raise `StepError`.
- `CollectorUnavailableError` from collectors logged as `upstream_api_unavailable` (distinct message).
- `--force` argparse flag: when set, pass `force=True` to both collectors to bypass incremental skip.
- Exit code 1 on any failure, print `PIPELINE FAILED at step N (step_name)`.
- Log `pipeline_complete` with all step statuses on success.

All credentials and endpoints from env vars (use `os.environ.get` with defaults matching `.env.example`).

### [x] B5-2 `scripts/verify-setup.py`

Check all 5 services. Requirements:

```python
# Each check returns a tuple: (service_name, status, detail)
# status: "PASS" | "FAIL" | "TIMEOUT"

def check_minio() -> tuple[str, str, str]: ...
def check_postgres() -> tuple[str, str, str]: ...
def check_hive_metastore() -> tuple[str, str, str]: ...
def check_trino() -> tuple[str, str, str]: ...
def check_mlflow() -> tuple[str, str, str]: ...
```

Per-service rules:
- **MinIO**: `GET http://{MINIO_ENDPOINT}/minio/health/live`, also verify buckets `sololakehouse` and `mlflow-artifacts` exist.
- **PostgreSQL**: attempt `psycopg2.connect()` (add `psycopg2-binary` to requirements.txt), check both databases exist.
- **Hive Metastore**: TCP socket connect to port 9083, 5s timeout.
- **Trino**: `GET http://localhost:8080/v1/info`, check `"starting": false` in response JSON.
- **MLflow**: `GET http://localhost:5000/health`.

Output: aligned `PASS/FAIL/TIMEOUT` status table:
```
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS    Buckets: sololakehouse, mlflow-artifacts
PostgreSQL       PASS    Databases: hive_metastore, mlflow
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200
```

Also validate required env vars are set (read from `.env` if present), print missing ones.
Exit code: 0 if all PASS, 1 otherwise.

---

## Block 6 — Tests

### [x] B6-1 `tests/test_schemas.py`

Test `ECBRecord` and `DAXRecord` with at least:
- Valid record parses without error
- Invalid `rate_pct` (out of range) raises `ValidationError`
- Future `observation_date` raises `ValidationError`
- `high_price < low_price` on DAX raises `ValidationError`
- `model_dump()` returns the expected keys

Use a `make_ecb_record()` / `make_dax_record()` helper that returns valid base data.

### [x] B6-2 `tests/test_quality_checks.py`

Test each function in `ingestion/quality/bronze_checks.py`:
- `check_no_future_dates`: pass (past date), fail (tomorrow's date)
- `check_date_continuity`: pass (gap=3 days within limit), fail (gap=200 days for ECB limit=180)
- `check_schema_version`: pass (all columns present), fail (missing column, descriptive error)
- `check_no_nulls`: pass, fail with null
- `run_ecb_bronze_checks` / `run_dax_bronze_checks`: integration of checks, smoke test both pass and fail paths

### [x] B6-3 `tests/test_bronze_writer.py`

Mock `minio.Minio` with `unittest.mock.MagicMock`.

Tests:
- `write()` calls `minio.put_object` with correct bucket and path pattern
- `write()` path contains today's date in `ingestion_date=YYYY-MM-DD` format
- `write_rejected()` writes to `bronze/rejected/source=.../` path with `rejection_reason` column
- `write_rejected()` returns `None` on empty records list

### [x] B6-4 `tests/test_transformations.py`

Use small synthetic DataFrames (10–20 rows). Test pure functions only (no I/O).

- `transform_ecb_bronze_to_silver`: output has `rate_change_bps`, no weekend filter needed, forward-fill works, dedup works
- `transform_dax_bronze_to_silver`: weekend rows removed, `daily_return` calculated, output column subset correct
- `build_gold_features`: event rows only (rate_change_bps != 0), feature columns present, events without DAX data dropped

Each test class groups tests: `TestECBTransform`, `TestDAXTransform`, `TestGoldFeatures`.

### [x] B6-5 `tests/test_pipeline.py`

Class `TestPipelineRetry`. Use `unittest.mock.patch`.

Tests:
- Step 1 (ECB) retries 3 times on `StepError`, then raises after max attempts
- Step 3 (transform) does NOT retry — fails immediately on `StepError`
- `--force` argument passed through to collectors (mock collector receives `force=True`)
- `CollectorUnavailableError` produces distinct log message vs generic step failure

### [x] B6-6 `tests/integration/` (3 files)

**`conftest.py`:**
- `minio_client` fixture: connects to real MinIO at env var endpoint, skips if unreachable
- `test_bucket` fixture: creates `sololakehouse-test` bucket, yields bucket name, deletes on teardown

**`test_bronze_writer_integration.py`** (`@pytest.mark.integration`):
- Write small DataFrame to real MinIO, read it back, assert row count matches
- Rejected records written to correct path with `rejection_reason` column

**`test_pipeline_smoke.py`** (`@pytest.mark.integration`):
- Run full `scripts/run-pipeline.py` end-to-end
- Assert Gold parquet exists in MinIO
- Assert Gold parquet row count > 0

---

## Block 7 — Code Quality & CI

### [x] B7-1 `ruff.toml`

```toml
line-length = 100
[lint]
select = ["E", "F", "I"]
```

After creating, run `ruff check .` and fix all violations before proceeding.

### [x] B7-2 `mypy.ini`

```ini
[mypy]
python_version = 3.11
ignore_missing_imports = True
strict = False
check_untyped_defs = True
```

Add return type annotations and parameter type annotations to all public functions in `ingestion/`, `transformations/`, `ml/`. Run `mypy ingestion/ transformations/ ml/ scripts/` and fix all errors.

### [x] B7-3 `.github/workflows/test.yml`

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install ruff==0.4.4
      - run: ruff check .

  typecheck:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - run: mypy ingestion/ transformations/ ml/ scripts/

  test:
    runs-on: ubuntu-latest
    needs: typecheck
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short --ignore=tests/integration
               --cov=ingestion --cov=transformations --cov=ml
               --cov-report=term-missing --cov-fail-under=70
```

### [x] B7-4 Update `.gitignore`

Add: `htmlcov/`, `.coverage`, `.mypy_cache/`, `.ruff_cache/`

---

## Block 8 — Sample Data

### [x] B8-1 `data/sample/dax_daily_sample.csv`

Create a CSV with at least 500 rows of simulated DAX OHLCV data from 2000-01-03 to ~2024-12-31 (trading days only, no weekends).

Required columns: `date,open,high,low,close,volume`

Constraints:
- `date` in `YYYY-MM-DD` format
- No weekends
- `high >= low`, all prices > 0
- Realistic price range: open ~3000–20000 range, daily moves ±3%
- `volume` ~ 50M–150M

This can be generated with a Python script or committed as a static file. The file must be committed to the repo (not gitignored).

---

## Block 9 — v1.0 Release

### [x] B9-1 `CHANGELOG.md`

Keep a Changelog format. Create `v1.0.0` entry with sections: `Added`, `Changed`, `Fixed`.

### [x] B9-2 Update `docs/deployment.md`

Add a `## Troubleshooting` section with the following 5 scenarios (if section already exists, expand it):

1. `hive-metastore` fails to start → PostgreSQL not ready → `make clean && make up`
2. Trino "catalog not available" → wait 60s for hive-metastore, run `make verify`
3. ECB API timeout during `make pipeline` → retry with `make pipeline` (ECB API is rate-limited)
4. MinIO "bucket already exists" error → safe to ignore; `minio-init` is idempotent
5. MLflow UI shows no experiments → run `make pipeline` first; experiments auto-created

### [x] B9-3 Update `README.md`

Add a `## Quick Validation` section after `## Quick start`. Show expected `make verify` output (aligned PASS table). Add `## Common Issues` with a link to `docs/deployment.md#troubleshooting`.

### [x] B9-4 `docs/V1_RELEASE_CHECKLIST.md`

Create manual validation checklist:

```markdown
# v1.0 Release Checklist

- [x] `make clean && make up` completes without errors
- [ ] `make verify` shows all 5 services as PASS
- [ ] `make pipeline` runs end-to-end without errors
- [ ] `make test` passes with coverage >= 70%
- [ ] `make lint` passes with zero violations
- [ ] `make typecheck` passes with zero errors
- [ ] MLflow UI at http://localhost:5000 shows experiment `ecb_dax_impact`
- [ ] Trino query `SELECT * FROM hive.gold.ecb_dax_features LIMIT 5` returns rows
- [ ] `make down && make up` (restart) preserves all data in volumes
- [ ] CI (GitHub Actions) passes on clean branch push
```

### [x] B9-5 Tag v1.0.0

Once all checklist items in `docs/V1_RELEASE_CHECKLIST.md` are verified:
1. Update `README.md` version badge (if present)
2. Update `CLAUDE.md` Roadmap table: mark v1.0 as `current`
3. `git tag v1.0.0 && git push origin v1.0.0`

---

## Status Summary

| Block | Description | Tasks | Done |
|-------|-------------|-------|------|
| B0 | Project skeleton | B0-1 to B0-5 | 5/5 |
| B1 | Docker infrastructure | B1-1 to B1-8 | 8/8 |
| B2 | Ingestion layer | B2-1 to B2-7 | 7/7 |
| B3 | Transformation layer | B3-1 to B3-4 | 4/4 |
| B4 | ML layer | B4-1 to B4-2 | 2/2 |
| B5 | Scripts | B5-1 to B5-2 | 2/2 |
| B6 | Tests | B6-1 to B6-6 | 6/6 |
| B7 | Code quality & CI | B7-1 to B7-4 | 4/4 |
| B8 | Sample data | B8-1 | 1/1 |
| B9 | v1.0 release | B9-1 to B9-5 | 5/5 |
| **Total** | | **44** | **44/44** |

---

## Post-v1 Governance Track (v3 planning reference)

This file is the completed v1 implementation ledger.  
For active v2/v3 execution backlog, use `docs/EVOLVING_PLAN.md`.

v3 governance-focused scope (tracked in `docs/EVOLVING_PLAN.md` Phase 4 and `docs/governance-v3-matrix.md`):

- multi-environment promotion governance (`dev -> staging -> production`)
- secrets lifecycle and least-privilege access governance
- data governance contracts (owner/SLA/quality class/lineage responsibility)
- SLO-driven observability and alert governance
- incident runbooks, drills, and governance evidence reviews
