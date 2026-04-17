# Release Guide (v2.5+)

This runbook defines minimum checks for a releasable build on the v2.5 single-track runtime.

## 1) Local validation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dagster.txt
make clean
make up
make verify
make pipeline
make lint
make typecheck
make test-cov
make release-check
```

Expected:
- `make verify` reports all required services as `PASS` (including OpenMetadata/Superset)
- `make pipeline` completes through Dagster
- quality gates pass (`lint`, `typecheck`, `test-cov`, `release-check`)

## 2) Runtime checks

```sql
SELECT * FROM hive.gold.ecb_dax_features LIMIT 5;
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 5;
```

```bash
curl -fsS http://localhost:8585/api/v1/system/version
curl -fsS http://localhost:8088/health
```

## 3) Metadata consistency

Before tagging:
- `docs/roadmap.md` marks `v2.5` as current baseline
- `README.md` and `docs/README.md` reflect single-track runtime
- `CHANGELOG.md` has the release entry
- `docs/history/*` is updated for version-state consistency

## 4) Tagging

```bash
git tag v2.5.x
git push origin v2.5.x
```
