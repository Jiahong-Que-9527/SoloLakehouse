# E06 · BigQuery warehouse and FinOps

**Status:** planned · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [GCP cost gate](../../AGENTS.md)

Run the exact same `dbt` project against live **GCP BigQuery** (`slh-gcp-test`, `europe-west3`) using `--target bq`, apply BigQuery partitioning and clustering, publish an authorized consumer view, and measure query scan cost.

## Deliverables

- `profiles.yml` `bq` target using ADC / WIF authentication in `europe-west3` with explicit `maximum_bytes_billed` safety guard.
- BigQuery daily partitioning (`partition_by` + `require_partition_filter: true`) and clustering (`station_id`, `country_code`) on `fct_charging_sessions` and `fct_daily_revenue`.
- Terraform or scoped IAM setup exposing one read-only BigQuery Authorized View to an analyst identity without granting raw/staging read access, plus `docs/cloud-verification.md`.

## Acceptance

1. `dbt build --target bq` succeeds end-to-end on `slh-gcp-test` (`europe-west3`) with zero code forks from the DuckDB CI models.
2. `INFORMATION_SCHEMA.JOBS` receipts compare full-table vs partition-pruned incremental/consumer queries, showing measured `total_bytes_billed` and €0 net cost inside Free Tier.
3. A partition-unfiltered query against `fct_charging_sessions` is rejected by `require_partition_filter`, and the analyst identity is denied direct access to raw/staging datasets.
