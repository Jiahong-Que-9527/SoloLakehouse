# Quick start

**Prerequisites:** Docker (with Compose plugin), `make`, Python 3.11+.

## 1. Clone and start

```bash
git clone <repository-url>
cd SoloLakehouse
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS; Windows (WSL): same
pip install -r requirements.txt
make up
```

Once `.venv` exists, `make` commands prefer `.venv/bin/python` automatically.

`make up` starts all Docker services (including Dagster), waits until every health check passes, then prints:

```
SoloLakehouse is ready.
  MinIO Console:  http://localhost:9001
  Trino UI:       http://localhost:8080
  MLflow UI:      http://localhost:5000
  Dagster UI:     http://localhost:3000
```

## 2. Verify

```bash
make verify
```

Checks MinIO (and buckets), PostgreSQL, Hive Metastore (9083), Trino `/v1/info`, MLflow API, and Dagster webserver (`/server_info`).

If you also started OpenMetadata with `make up-openmetadata`, run:

```bash
make verify-openmetadata
```

## 3. Run the example pipeline

```bash
make pipeline
```

By default in v2, this runs Dagster job orchestration (`full_pipeline_job`).

For v1-compatible legacy script behavior, use:

```bash
make pipeline PIPELINE_MODE=v1
# or
make pipeline-v1
# or (same script, no PIPELINE_MODE)
make pipeline-legacy
```

Legacy script mode executes `scripts/run-pipeline.py` (six steps):

| Step | What happens |
|------|----------------|
| 1 | ECB MRO rates from ECB SDW REST API |
| 2 | Simulated DAX daily data from `data/sample/dax_daily_sample.csv` |
| 3 | ECB Bronze → Silver |
| 4 | DAX Bronze → Silver |
| 5 | Silver → Gold (event-study features) |
| 6 | Train XGBoost / LightGBM; log to MLflow |

## 4. Explore

| UI | URL | Notes |
|----|-----|--------|
| MinIO Console | http://localhost:9001 | Default user/password from `.env` |
| MLflow | http://localhost:5000 | Experiment `ecb_dax_impact` |
| Trino | http://localhost:8080 | `docker exec -it slh-trino trino` |
| Dagster UI | http://localhost:3000 | Asset graph, runs, schedules, sensors |
| OpenMetadata (optional) | http://localhost:8585 | Start with `make up-openmetadata` |

```sql
SHOW CATALOGS;
SHOW SCHEMAS IN hive;
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 10;
```

## 5. Stop

```bash
make down      # stop; data kept in volumes
make clean     # stop and remove volumes (destructive)
```

**More detail:** hardware, OS, ports, troubleshooting → [deployment.md](deployment.md).
