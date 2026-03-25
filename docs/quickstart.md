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

`make up` starts Docker services, waits for MinIO health, and runs `minio-init` to create buckets.

Expected output ends with:

```
SoloLakehouse is ready!
  MinIO Console: http://localhost:9001
  Trino:         http://localhost:8080
  MLflow:        http://localhost:5000
```

## 2. Verify

```bash
make verify
```

Checks MinIO (and buckets), PostgreSQL, Hive Metastore (9083), Trino `/v1/info`, MLflow API.

## 3. Run the example pipeline

```bash
make pipeline
```

Runs `scripts/run-pipeline.py` (six steps):

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

```sql
SHOW CATALOGS;
SHOW SCHEMAS IN hive;
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
```

## 5. Stop

```bash
make down      # stop; data kept in volumes
make clean     # stop and remove volumes (destructive)
```

**More detail:** hardware, OS, ports, troubleshooting → [deployment.md](deployment.md).
