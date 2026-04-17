# v2.5 Release Checklist

Use before tagging any v2.5.x release.

## Core platform

- [ ] `make clean && make up` succeeds
- [ ] `make verify` passes all required services:
  - MinIO, PostgreSQL, Hive Metastore, Trino, MLflow, Dagster, OpenMetadata, Superset
- [ ] `make pipeline` succeeds end-to-end
- [ ] `make test-cov` passes (coverage threshold met)
- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] `make release-check` passes

## Data and ML checks

- [ ] `SELECT * FROM hive.gold.ecb_dax_features LIMIT 5` returns rows
- [ ] `SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 5` returns rows
- [ ] MLflow (`http://localhost:5000`) has at least one `ecb_dax_impact` run

## UI checks

- [ ] Dagster UI loads and assets are materializable
- [ ] OpenMetadata version endpoint responds
- [ ] Superset `/health` endpoint responds

## Restart safety

- [ ] `make down && make up` preserves data volumes as expected

## Documentation and metadata

- [ ] `docs/roadmap.md` marks v2.5 as current baseline
- [ ] `README.md` and `docs/README.md` match actual runtime commands
- [ ] `docs/history/timeline.md` updated when version status changes
- [ ] `CHANGELOG.md` includes release entry
