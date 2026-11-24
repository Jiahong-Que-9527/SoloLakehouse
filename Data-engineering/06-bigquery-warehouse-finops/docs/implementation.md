# Implementation plan: E06 · BigQuery warehouse and FinOps

**Status:** planned. [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md) · [GCP cost gate](../../../AGENTS.md)

## First delivery

Deploy the E02–E05 `dbt` models to live BigQuery (`slh-gcp-test`, `europe-west3`) with zero SQL forks, enforce daily partitioning + clustering and the 100 MiB per-query cap, verify an Authorized View permission split, and record `INFORMATION_SCHEMA.JOBS` `bytes_billed` receipts.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/pyproject.toml` & `uv.lock` (ensure `dbt-bigquery` is locked)
- `Data-engineering/reference-warehouse/dbt_project/profiles.yml` (add `bq` target with `maximum_bytes_billed`)
- `Data-engineering/reference-warehouse/src/charging_commerce/bq_loader.py` (idempotent Raw load to `de_raw` within Free Tier)
- `Data-engineering/06-bigquery-warehouse-finops/infra/` (Terraform datasets, Authorized View, scoped IAM bindings; 0 destroys)
- `Data-engineering/06-bigquery-warehouse-finops/docs/cloud-verification.md`

## Implementation sequence

1. **Cost & Terraform plan review:** Confirm [AGENTS.md](../../../AGENTS.md) compliance (BigQuery Free Tier datasets/IAM only, `0 destroys`, `europe-west3`) and apply datasets + Authorized View + analyst reader IAM.
2. **Load Raw fixture to `de_raw`:** Load the locked E01 Raw batches into `slh-gcp-test.de_raw` idempotently (`WRITE_TRUNCATE` per batch staging or guarded merge, `< 10 MB`).
3. **Run dbt against `--target bq`:** Execute `dbt deps`, `dbt snapshot --target bq`, and `dbt build --target bq` (both `--full-refresh` and incremental 48h late-arrival batch).
4. **Verify guardrails & IAM isolation:** Test (a) a query capped below the billed minimum (e.g. `--maximum_bytes_billed=1024`) fails with BigQuery's "Query exceeded limit for bytes billed" error, and (b) analyst identity succeeds on `de_consumer.v_daily_revenue` and fails with `403` on `de_raw`.
5. **Audit FinOps receipts:** Query `region-europe-west3.INFORMATION_SCHEMA.JOBS` for the run's job IDs and `total_bytes_billed`, documenting full-refresh vs incremental scan savings in `docs/cloud-verification.md`.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse
uv run --locked charging-commerce load-bq --project slh-gcp-test --dataset de_raw
uv run --locked dbt snapshot --project-dir dbt_project --profiles-dir dbt_project --target bq
uv run --locked dbt build --project-dir dbt_project --profiles-dir dbt_project --target bq
```

**Negative drills:**
- Run a partition-unfiltered `bq query` against `de_mart.fct_charging_sessions` and confirm rejection.
- Impersonate/use analyst identity to query `de_raw.raw_charging_sessions` and confirm `Access Denied`.

## Acceptance evidence

Record in `06-bigquery-warehouse-finops/docs/cloud-verification.md`: Terraform plan output (`0 destroys`), `dbt build --target bq` summary, BigQuery job IDs and `total_bytes_billed` table, partition-filter rejection message, and IAM denial output.
