# v1.0 Release Checklist

- [x] `make clean && make up` completes without errors
- [x] `make verify` shows all 5 services as PASS
- [x] `make pipeline` runs end-to-end without errors
- [x] `make test` passes with coverage >= 70%
- [x] `make lint` passes with zero violations
- [x] `make typecheck` passes with zero errors
- [x] MLflow UI at http://localhost:5000 shows experiment `ecb_dax_impact`
- [x] Trino query `SELECT * FROM hive.gold.ecb_dax_features LIMIT 5` returns rows
- [x] `make down && make up` (restart) preserves all data in volumes
- [x] CI (GitHub Actions) passes on clean branch push
