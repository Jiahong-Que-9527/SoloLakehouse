# E06 cloud verification · BigQuery warehouse and FinOps

**Run date (UTC):** _pending live run · **Project:** `slh-gcp-test` (`europe-west3`) ·
**Outcome:** pending

> **GCP cost gate (AGENTS.md):** the plan below touches live BigQuery only after
> the owner's explicit approval. Everything in scope is a Free-Tier SKU (dataset
> storage + query scans, bounded by `maximum_bytes_billed: 100 MiB` per query);
> expected net cost **€0**. No Cloud Composer, no NAT, no VMs, `0 destroys`.

## What landed (local, pre-approval)

- `profiles.yml` `bq` target: ADC (`method: oauth`), `location: europe-west3`,
  `maximum_bytes_billed: 104857600`, dataset `de_mart` — offline-tested by
  `tests/test_bq_loader.py::test_profiles_bq_target_has_cost_and_location_guards`.
- `generate_schema_name` macro: BigQuery datasets `de_*` (de_raw/de_stg/de_int/
  de_mart), DuckDB naming unchanged (E02 decision).
- `target_partition_config` wired onto `fct_charging_sessions` (E05) and
  `fct_daily_revenue` v1/v2: daily partition on `revenue_date`,
  `require_partition_filter: true`, clustered.
- `charging_commerce/bq_loader.py` + `charging-commerce load-bq`: idempotent
  (`WRITE_TRUNCATE`) raw load through the *unmodified* E01 ingestion pipeline,
  10 MiB upload guard, lineage columns preserved, roaming excluded (empty-table
  boundary, same as E05).
- Terraform under `infra/`: five `prevent_destroy` datasets, Authorized View +
  analyst read split, two-phase apply (datasets → build → view+IAM).

## Phase 1 · Terraform datasets (after approval)

| Item | Recorded |
|---|---|
| `terraform plan` output | pending (expect `5 to add, 0 to change, 0 to destroy`) |
| `terraform apply` output | pending |
| `gcloud bigquery datasets list --location=europe-west3` | pending |

## Phase 2 · Raw load + dbt build

```bash
uv run --locked charging-commerce load-bq --project slh-gcp-test --dataset de_raw
uv run --locked dbt snapshot --project-dir dbt_project --profiles-dir dbt_project --target bq
uv run --locked dbt build --project-dir dbt_project --profiles-dir dbt_project --target bq
```

| Item | Recorded |
|---|---|
| `load-bq` summary (tables, rows, bytes, job ids) | pending |
| `dbt snapshot --target bq` result | pending |
| `dbt build --target bq` summary (models/tests/unit) | pending |
| Incremental 48h late-arrival batch result | pending |

## Phase 3 · Guardrails & IAM isolation (negative drills)

| Drill | Command / principal | Expected | Recorded |
|---|---|---|---|
| Partition filter enforced | `bq query --use_legacy_sql=false 'SELECT * FROM de_mart.fct_charging_sessions'` | rejected (`require_partition_filter`) | pending |
| Analyst allowed on consumer view | analyst identity queries `de_consumer.v_daily_revenue` | rows returned | pending |
| Analyst denied raw | analyst identity queries `de_raw.raw_charging_sessions` | `403 Access Denied` | pending |

## Phase 4 · FinOps receipts (`INFORMATION_SCHEMA.JOBS`)

Query `region-europe-west3`.INFORMATION_SCHEMA.JOBS for this run's job IDs and
record `total_bytes_billed` per phase: full-refresh build vs partition-pruned
incremental merge vs consumer-view queries.

| Query | job_id | total_bytes_billed | Notes |
|---|---|---|---|
| full-refresh build | pending | pending | |
| incremental merge | pending | pending | measured savings vs full refresh |
| consumer view query | pending | pending | |

**Net cost:** pending — expected €0 (1 TB/month free scan allowance; every query
capped at 100 MiB).

## Deviations from design

- `de_int` dataset added for intermediate views (design §4 lists four datasets;
  intermediate views need a home; same `de_` naming family).
- Authorized View is created in Terraform phase 2 (after the dbt build) because
  BigQuery validates the view query against existing tables at CREATE time;
  phase-1/phase-2 split is documented in `infra/README.md`.
