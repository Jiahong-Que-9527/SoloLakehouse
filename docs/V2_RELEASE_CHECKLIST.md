# v2.x Release Checklist

Covers v2.0 (Dagster orchestration) and v2.5 (Iceberg + optional services). Use this before tagging any `v2.x` release.

## Core platform

- [ ] `make clean && make up` completes without errors
- [ ] `make verify` shows all six default services as PASS (`MinIO`, `PostgreSQL`, `Hive Metastore`, `Trino`, `MLflow`, `Dagster`)
- [ ] `make pipeline` (Dagster default path) runs end-to-end without errors
- [ ] `make pipeline PIPELINE_MODE=v1` (legacy fallback) completes without `PIPELINE FAILED`
- [ ] `make test-cov` passes with coverage ≥ 70%
- [ ] `make lint` passes with zero violations
- [ ] `make typecheck` passes with zero errors
- [ ] `make release-check` passes

## Dagster orchestration

- [ ] Dagster UI (`http://localhost:3000`) loads and shows `full_pipeline_job`
- [ ] All six Dagster software-defined assets are visible and materializable
- [ ] Dagster schedule (`daily_pipeline_schedule`) is present and enabled
- [ ] Dagster freshness sensor (`ecb_data_freshness_sensor`) is active

## Data layer (Hive + Iceberg)

- [ ] Trino query returns rows: `SELECT * FROM hive.gold.ecb_dax_features LIMIT 5`
- [ ] Trino query returns rows: `SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 5`
- [ ] MLflow UI (`http://localhost:5000`) shows experiment `ecb_dax_impact` with at least one run

## Optional services (when profiles are enabled)

- [ ] `make up-openmetadata` starts without errors
- [ ] `make verify-openmetadata` passes
- [ ] OpenMetadata version endpoint responds: `curl -fsS http://localhost:8585/api/v1/system/version`
- [ ] `make up-superset` starts without errors
- [ ] `make verify-superset` passes
- [ ] Superset health endpoint responds: `curl -fsS http://localhost:8088/health`

## Restart safety

- [ ] `make down && make up` preserves all data in volumes (Parquet, MLflow runs, Trino metadata)

## Documentation and metadata consistency

- [ ] `docs/roadmap.md` marks `v2.0` as `Current`
- [ ] `CHANGELOG.md` includes the release entry with date
- [ ] `docs/history/timeline.md` updated with milestone status
- [ ] `docs/history/architecture-evolution.md` updated if any architecture decisions changed
- [ ] Version references in `CLAUDE.md` tech stack table are accurate
- [ ] CI (GitHub Actions) passes on clean branch push

## Tagging

```bash
git tag v2.x.y
git push origin v2.x.y
```

Only tag after all applicable checks above are green.
