# SoloLakehouse Demo Runbook (English, with Acceptance Checklist)

This runbook is a full clone-to-demo execution guide for first-time users.  
The goal is deterministic execution: copy commands step by step and produce a final PASS/FAIL conclusion with evidence.

---

## 0. Demo Objective and Deliverables

By the end of this runbook, you should produce:

1. A running local SoloLakehouse v2.5 stack
2. One successful `make pipeline` execution
3. A completed acceptance checklist
4. A final conclusion statement (ready for PR/report/email)

Assumptions:

- OS: Linux / macOS (Windows users should use WSL2)
- Recommended branch: `main`
- Working directory: any local path

---

## 1. Prerequisites (Must Pass First)

### 1.1 Required tools

- `git`
- Docker + Docker Compose plugin
- Python 3.13+
- `make`

### 1.2 Verification commands

```bash
git --version
docker --version
docker compose version
python3 --version
make --version
```

Success criteria:

- Every command returns a version
- Docker daemon is running

If something fails here, stop and fix local environment first.

---

## 2. Clone Repository and Enter Root Directory

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
```

Sanity check:

```bash
pwd
ls
```

You should see at least:

- `Makefile`
- `docker/`
- `docs/`
- `scripts/`
- `requirements.txt`

---

## 3. Initialize Local Python Environment

Even though core components run in Docker, local helper scripts (for example health checks) run in your local Python environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional confirmation:

```bash
which python
python --version
```

Success criteria:

- `which python` points to `.../SoloLakehouse/.venv/bin/python`
- `pip install` completes without fatal errors

---

## 4. Prepare Environment Variables

```bash
cp .env.example .env
```

For first-time local demo, default values are usually enough.  
If you have old Docker volumes from previous runs, credential mismatch may require fixes (see troubleshooting section).

---

## 5. Start Full Stack (Use setup for first run)

```bash
make setup
```

This command handles:

1. Docker daemon check
2. `.env` bootstrap
3. Image pull
4. Full startup + readiness waiting

First startup can take several minutes, especially for OpenMetadata/Superset/Elasticsearch-related containers.

Success criteria:

- Command exits with code 0
- No fatal dependency startup errors

---

## 6. Health Gate (Mandatory)

```bash
make verify
```

Expected: all services show `PASS`

- MinIO
- PostgreSQL
- Hive Metastore
- Trino
- MLflow
- Dagster
- OpenMetadata
- Superset

If one service is still warming up, wait 10-30 seconds and rerun `make verify`.

---

## 7. Execute Main Demo Flow (Pipeline)

```bash
make pipeline
```

This executes Dagster `full_pipeline_job`, the canonical v2.5 execution path.

Success criteria:

- Command exits with code 0
- No unhandled exception in output

Then run a post-run health check:

```bash
make verify
```

---

## 8. UI Validation

Open each endpoint and verify expected behavior:

| Service | URL | Expected Result |
|---------|-----|-----------------|
| MinIO Console | `http://localhost:9001` | Page opens, buckets include `sololakehouse` and `mlflow-artifacts` |
| Trino UI | `http://localhost:8080` | Page opens, service healthy |
| MLflow UI | `http://localhost:5000` | Page opens without invalid host header error |
| Dagster UI | `http://localhost:3000` | Latest pipeline run visible |
| OpenMetadata | `http://localhost:8585` | Page opens |
| Superset | `http://localhost:8088` | Login works (`admin / admin` by default) |

---

## 9. Data Output Validation (Strongly Recommended)

### 9.1 Verify Gold tables through Trino

Run at least one (preferably both):

```sql
SELECT count(*) AS total_rows
FROM hive.gold.ecb_dax_features;
```

```sql
SELECT count(*) AS total_rows
FROM iceberg.gold.ecb_dax_features_iceberg;
```

Success criteria:

- Query execution succeeds
- Returned row count > 0

### 9.2 Verify MLflow run records

In MLflow UI, confirm:

- At least one run exists
- Run has timestamp/status/metrics (as applicable)

### 9.3 Verify Dagster orchestration result

In Dagster UI, confirm:

- Latest `full_pipeline_job` status is success
- No unresolved failed steps

---

## 10. Acceptance Checklist (Use as Sign-off Gate)

Mark each item during execution:

- [ ] Prerequisite tools verified (`git`, `docker`, `python`, `make`)
- [ ] Repository cloned and root directory entered
- [ ] `.venv` created and dependencies installed
- [ ] `.env` created
- [ ] `make setup` completed successfully
- [ ] Initial `make verify` is all PASS
- [ ] `make pipeline` completed successfully
- [ ] Post-run `make verify` is all PASS
- [ ] MinIO UI accessible and buckets present
- [ ] Trino UI accessible
- [ ] MLflow UI accessible without host header error
- [ ] Dagster UI shows successful run
- [ ] OpenMetadata UI accessible
- [ ] Superset UI login successful
- [ ] `hive.gold.ecb_dax_features` query succeeds with data
- [ ] `iceberg.gold.ecb_dax_features_iceberg` query succeeds with data
- [ ] MLflow run record visible

Acceptance rule:

- All required items PASS => Final result = **PASS**
- Any critical failure (`verify`, `pipeline`, Gold query) => Final result = **FAIL**

---

## 11. Final Conclusion Template (Copy-Paste)

```text
[SoloLakehouse v2.5 Demo Conclusion]
Execution time: <YYYY-MM-DD HH:MM>
Executed by: <name>
Environment: <OS + Docker + Python version>

Result: PASS / FAIL

Acceptance summary:
- Service health checks: <PASS/FAIL>
- Pipeline execution: <PASS/FAIL>
- Gold data query checks: <PASS/FAIL>
- MLflow run visibility: <PASS/FAIL>
- UI accessibility (6 items): <PASS/FAIL>

Notes:
<If failed, include failed step, observed error, and mitigation plan>
```

---

## 12. Fast Troubleshooting for Live Demo

### 12.1 Hive Metastore PostgreSQL authentication failure

Symptom:

- `hive-metastore` logs show `password authentication failed for user "postgres"`

Fix:

```bash
docker exec slh-postgres psql -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
make up
make verify
```

### 12.2 MLflow `Invalid Host header`

Symptom:

- Opening `http://localhost:5000` shows DNS rebinding warning

Fix:

```bash
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml up -d --build mlflow
make verify
```

### 12.3 First startup is slow

OpenMetadata/Elasticsearch/Superset can be slower on first boot.

```bash
make verify
```

Wait and retry until all checks pass.

---

## 13. Demo Teardown

### Stop while keeping data (recommended)

```bash
make down
```

### Full reset (destructive)

```bash
make clean
docker image prune -f
docker volume prune -f
```

---

## 14. Minimal Copy-Paste Path

If you only want the shortest deterministic demo path:

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make setup
make verify
make pipeline
make verify
```

Then complete the checklist (Section 10) and output final conclusion (Section 11).
