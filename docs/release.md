# Release Guide (v2.x)

This runbook defines the minimum steps to produce a releasable `v2.x` build with orchestration compatibility (v2 default + v1 legacy path).

## 1) Local release validation

Run from repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dagster.txt
make setup
make verify
make verify-openmetadata   # optional, when `make up-openmetadata` is enabled
make verify-superset       # optional, when `make up-superset` is enabled
make pipeline
make pipeline PIPELINE_MODE=v1
make lint
make typecheck
make test-cov
make release-check
```

Expected result:

- `make verify` shows the six default runtime checks as `PASS` (`MinIO`, `PostgreSQL`, `Hive Metastore`, `Trino`, `MLflow`, `Dagster`)
- `make verify-openmetadata` also passes when the optional OpenMetadata profile is running
- `make verify-superset` also passes when the optional Superset profile is running
- `make pipeline` (Dagster default path) completes successfully
- `make pipeline PIPELINE_MODE=v1` (legacy compatibility path) completes without `PIPELINE FAILED`
- `make lint`, `make typecheck`, `make test-cov`, and `make release-check` all pass

## 2) Runtime checks

- MLflow UI (`http://localhost:5000`) contains experiment `ecb_dax_impact`
- Trino query succeeds:

```sql
SELECT * FROM hive.gold.ecb_dax_features LIMIT 5;
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 5;
```

- OpenMetadata version endpoint responds when enabled:

```bash
curl -fsS http://localhost:8585/api/v1/system/version
```

- Superset health endpoint responds when enabled:

```bash
curl -fsS http://localhost:8088/health
```

- Restart safety:

```bash
make down
make up
```

Data should remain available after restart.

## 3) Release metadata consistency

Before tagging:

- `docs/roadmap.md` marks `v2.0` as `Current`
- `docs/roadmap.md` and `README.md` still describe v2.5 as the delivered reference extension, not the default platform baseline
- `CHANGELOG.md` includes the release entry
- history/decision docs are aligned with release scope (`docs/history/*`, `docs/decisions/*`)

## 4) Tagging

```bash
git tag v2.0.0
git push origin v2.0.0
```

Only tag after all checks above are green.
