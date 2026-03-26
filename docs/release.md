# Release Guide (v1.x)

This runbook defines the minimum steps to produce a releasable `v1.x` build with easy deployment and verification.

## 1) Local release validation

Run from repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make setup
make verify
make pipeline
make lint
make typecheck
make test-cov
```

Expected result:

- `make verify` shows all five services as `PASS`
- `make pipeline` completes without `PIPELINE FAILED`
- `make lint`, `make typecheck`, `make test-cov` all pass

## 2) Runtime checks

- MLflow UI (`http://localhost:5000`) contains experiment `ecb_dax_impact`
- Trino query succeeds:

```sql
SELECT * FROM hive.gold.ecb_dax_features LIMIT 5;
```

- Restart safety:

```bash
make down
make up
```

Data should remain available after restart.

## 3) Release metadata consistency

Before tagging:

- `docs/roadmap.md` marks `v1.0` as `Current`
- `CHANGELOG.md` includes the release entry
- `docs/V1_RELEASE_CHECKLIST.md` is fully checked

## 4) Tagging

```bash
git tag v1.0.0
git push origin v1.0.0
```

Only tag after all checks above are green.
