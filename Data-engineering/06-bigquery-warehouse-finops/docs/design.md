# Design: E06 · BigQuery warehouse and FinOps

**E06 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md) · [GCP cost gate](../../../AGENTS.md)

<!-- [ZCode·2026-11-23] Unify dataset name (de_consumer) and raw-upload size bound (< 10 MB); add per-query cap vs monthly free-tier allowance math. -->

Run the identical E02–E05 `dbt` project against live **Google BigQuery** in `slh-gcp-test` (`europe-west3`) using `--target bq`, enforce daily partitioning and clustering on fact tables, expose one read-only Authorized View, and measure scan cost savings in `INFORMATION_SCHEMA.JOBS`.

## 1. Decisions

| Topic | Decision |
|---|---|
| GCP project & region | `slh-gcp-test`, `europe-west3` (Frankfurt), matching existing `gcp/` and `Frankfurt Airport` infrastructure |
| Authentication | Application Default Credentials (ADC) locally; Workload Identity Federation (WIF) if triggered via CI |
| Safety budget | `maximum_bytes_billed: 104857600` (100 MiB per query) in `profiles.yml` `bq` target — *the* enforced per-query cost guard |
| Partitioning & clustering | Daily partition on `revenue_date`; `cluster_by: ['country_code', 'station_sk']`. *(Revised 2026-11-24: `require_partition_filter` was evaluated live and withdrawn — it is incompatible with dbt's data tests, which legitimately full-scan tables and cannot carry a partition predicate, and it also blocks the incremental watermark subquery. The enforced guard is the 100 MiB `maximum_bytes_billed` cap; partition pruning itself is verified via `INFORMATION_SCHEMA.JOBS` bytes-billed deltas.)* |
| Consumer governance | Separate `de_consumer` dataset holding an Authorized View (`v_daily_revenue`) for an analyst identity; raw/staging denied |
| Cost ceiling | **€0** inside BigQuery Free Tier (10 GB storage, 1 TB query/month); zero paid VMs, Cloud Composer, or NAT. The 100 MiB `maximum_bytes_billed` cap bounds every query, so even ~10,000 full-cap queries per month stay inside the 1 TB free scan allowance. |

## 2. Scope boundary

In scope: BigQuery dataset provisioning (0 destroys), `dbt snapshot` & `dbt build --target bq`, partition-pruning verification, Authorized View access split, and `INFORMATION_SCHEMA.JOBS` `bytes_billed` audit.

Out of scope: changing business SQL for BigQuery (parity rule), paid BigQuery BI Engine / reservations, and Airflow (`E07`).

## 3. Architecture

```text
E01 Parquet/CSV fixtures
        |  (upload to de_raw dataset in europe-west3, < 10 MB)
        v
BigQuery: de_raw.* ---> dbt snapshot & dbt build --target bq
        |
        +--> de_mart.fct_charging_sessions (partitioned by revenue_date, clustered)
        +--> de_mart.fct_daily_revenue_v2
        '--> de_consumer.v_daily_revenue (Authorized View -> analyst read-only; raw/stg denied)
```

## 4. Contracts and configuration

- `profiles.yml` defines a `bq` target (`method: oauth`, `location: europe-west3`, `maximum_bytes_billed: 104857600`, `threads: 4`).
- Terraform or IaC under `06-bigquery-warehouse-finops/infra/` creates datasets `de_raw`, `de_stg`, `de_mart`, `de_consumer` and scoped IAM bindings with `0 destroys`.

## 5. Behaviour and edge cases

1. A query capped below the table's billed minimum (e.g. `--maximum_bytes_billed=1024`) fails immediately with BigQuery's "Query exceeded limit for bytes billed" error — the enforced per-query guard.
2. A partition-pruned 2-day incremental `merge` scans dramatically fewer bytes than `--full-refresh`, recorded from `INFORMATION_SCHEMA.JOBS`.
3. The analyst identity can query `de_consumer.v_daily_revenue` and receives `403 Access Denied` on `de_raw.*` and `de_stg.*`.

## 6. Delivery and cost

Total test dataset size is a few MBs (`< 0.01%` of BigQuery's 10 GB/month Free Tier storage and 1 TB/month scan allowance). Every cloud plan must obey [AGENTS.md](../../../AGENTS.md): verify `0 destroys` and Free Tier SKUs before applying.

## 7. Acceptance criteria

1. `dbt snapshot --target bq` and `dbt build --target bq` complete green on `slh-gcp-test` (`europe-west3`).
2. `INFORMATION_SCHEMA.JOBS` query receipts record exact job IDs and `total_bytes_billed` for full-refresh vs incremental vs consumer queries (€0 cost).
3. Both negative checks pass: a query whose `maximum_bytes_billed` cap is below the billed minimum is rejected, and raw dataset query denied for the analyst principal.

## 8. Handoff

`E07` can parameterize Airflow to target `--target duckdb` (default local) or `--target bq` (explicit cloud dispatch) and `E08` parses BigQuery `bytes_billed` metrics from `run_results.json`.
