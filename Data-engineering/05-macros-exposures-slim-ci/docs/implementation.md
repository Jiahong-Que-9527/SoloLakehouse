# Implementation plan: E05 · Macros, exposures and Slim CI

**Status:** planned. [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md)

## First delivery

Extract reusable cross-database macros, wire `dbt_utils` and `exposures.yml`, enforce 100% mart documentation in `dbt docs`, and enable `state:modified+ --defer` Slim CI in `.github/workflows/data-engineering.yml`.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/dbt_project/packages.yml` & `package-lock.yml`
- `Data-engineering/reference-warehouse/dbt_project/macros/cross_db_helpers.sql`
- `Data-engineering/reference-warehouse/dbt_project/models/exposures.yml`
- `Data-engineering/reference-warehouse/tests/test_slim_ci.py`
- `.github/workflows/data-engineering.yml` (add `dbt deps`, doc-coverage check, and `state:modified+ --defer` Slim CI job)
- `Data-engineering/05-macros-exposures-slim-ci/evidence/e05-acceptance.md`

## Implementation sequence

1. **Install `dbt_utils` & author macros:** Add `packages.yml`, run `dbt deps`, and write `safe_divide`, `eur_currency_convert`, `incremental_lookback_filter`, and `target_partition_config` in `macros/cross_db_helpers.sql`; refactor models to call them.
2. **Add `exposures.yml` & doc-coverage check:** Declare downstream BI and ML feature exposures in `models/exposures.yml`; add a pytest/manifest check verifying every mart column has a non-empty `description` after `dbt docs generate`.
3. **Test Slim CI locally (`test_slim_ci.py`):** Build baseline state (`target/prod_manifest`), simulate (a) editing 1 downstream mart and (b) editing 1 upstream staging model, and assert exact `dbt ls --select state:modified+ --state ...` node sets.
4. **Update GitHub Actions workflow:** Configure `main` pushes to upload `manifest.json` as a build artifact and PRs to download it and run `dbt build --select state:modified+ --defer --state prod_state/` (with safe full-build fallback if no prior artifact exists).
5. **Verify BigQuery compile & record evidence:** Run `dbt compile --target bq` locally (offline SQL compilation check) and record Slim CI node-count/runtime comparison in `evidence/e05-acceptance.md`.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse
uv run --locked dbt deps --project-dir dbt_project --profiles-dir dbt_project
uv run --locked sqlfluff lint dbt_project/models dbt_project/macros
uv run --locked dbt docs generate --project-dir dbt_project --profiles-dir dbt_project --target duckdb
uv run --locked pytest tests/test_slim_ci.py -v
```

**Negative drill:** Temporarily strip a `description` from one mart column in a test copy and confirm the doc-coverage check fails cleanly.

## Acceptance evidence

Record in `05-macros-exposures-slim-ci/evidence/e05-acceptance.md`: full-build vs downstream-only Slim CI vs upstream-edit Slim CI model counts and runtimes, `dbt docs` coverage count, and `dbt compile --target bq` result.
