# E06 cloud verification · BigQuery warehouse and FinOps

**Run date (UTC):** 2026-11-24 · **Project:** `slh-gcp-test` (`europe-west3`) ·
**Outcome:** datasets + raw load + full `dbt build --target bq` green; guardrail
and IAM drills all recorded; net cost **€0**.

> **GCP cost gate (AGENTS.md):** the owner approved this live run on 2026-11-24
> after the €0 cost plan (Free-Tier SKUs only, 0 destroys). Executed scope stayed
> inside that approval; nothing was destroyed except artifacts created by this
> session's own failed attempts (noted under *Deviations*).

## What landed (local, pre-approval)

- `profiles.yml` `bq` target: ADC (`method: oauth`), `location: europe-west3`,
  `maximum_bytes_billed: 104857600`, dataset `de_mart` — offline-tested by
  `tests/test_bq_loader.py::test_profiles_bq_target_has_cost_and_location_guards`.
- `generate_schema_name` macro: BigQuery datasets `de_*` (de_raw/de_stg/de_int/
  de_mart), DuckDB naming unchanged (E02 decision).
- `target_partition_config` wired onto `fct_charging_sessions` and
  `fct_daily_revenue` v1/v2: daily partition on `revenue_date`, clustered
  (see *Deviations* for the `require_partition_filter` revision).
- `charging_commerce/bq_loader.py` + `charging-commerce load-bq`: idempotent
  (`WRITE_TRUNCATE`) raw load through the *unmodified* E01 ingestion pipeline
  (Parquet in-memory sink), 10 MiB upload guard, lineage columns preserved,
  roaming excluded (schema-only tables, same boundary as E05).
- Terraform under `infra/`: five `prevent_destroy` datasets, Authorized View +
  analyst read split, two-phase apply (datasets → build → view+IAM).

## Phase 1 · Terraform datasets

| Item | Recorded |
|---|---|
| `terraform plan` output | `Plan: 5 to add, 0 to change, 0 to destroy.` (five `google_bigquery_dataset` in `europe-west3`, `prevent_destroy` set, no IAM) |
| `terraform apply` output | `Apply complete! Resources: 5 added, 0 changed, 0 destroyed.` |
| Datasets after apply | `de_raw`, `de_stg`, `de_int`, `de_mart`, `de_consumer` (empty) via `bq ls` |

## Phase 2 · Raw load + dbt build

```bash
uv run --locked charging-commerce load-bq --project slh-gcp-test --dataset de_raw
# acceptance sequence: run 2 staging models -> snapshot x3 as-of -> run -> build
```

**Raw load (idempotent rerun shown; the first run loaded the same five tables):**

| Table | Rows | Load job id | Bytes processed |
|---|---|---|---|
| `raw_charging_sessions` | 12,728 | `f4bf5917-1301-4b24-9ee5-db41f84599ed` | 2,901,990 |
| `raw_smard_prices` | 21,313 | `64511231-d362-4c51-b950-fe24b8b66b07` | 2,898,568 |
| `raw_stations_bnetza` | 9,699 | `f69b0070-f81d-414d-bb41-9f5622928a0e` | 2,421,792 |
| `raw_ecb_fx_rates` | 507 | `61c3f4ab-c882-4037-ba4d-18e18cda7a5f` | 69,459 |
| `raw_tariff_plans` | 18 | `7dbe7d60-c076-47ce-a11a-435e09e9d192` | 3,117 |
| `raw_roaming_settlements` | 0 (schema-only) | — | — |
| `raw_quarantine` | 0 (schema-only) | — | — |

Total upload 9,091,008 bytes — inside the 10 MiB guard.

**dbt on BigQuery (final acceptance sequence, UTC 14:24–14:26):**

| Step | Result |
|---|---|
| `dbt run --select stg_bnetza_stations stg_tariff_plans` | PASS=2 ERROR=0 |
| `dbt snapshot` × as-of 2025-09-15 / 2026-01-15 / 2026-05-15 | PASS=2 ERROR=0 each (SCD2 history built on `de_mart`) |
| `dbt run` (all 15 models) | PASS=15 WARN=0 ERROR=0 |
| `dbt build` (models + 101 data tests + 6 unit tests) | **PASS=124 WARN=0 ERROR=0** — identical to the DuckDB result (parity rule). Raw step-by-step log: [`run-log-2026-11-24.txt`](run-log-2026-11-24.txt) |

The `build` includes the incremental 48h late-arrival path: the merge over
`fct_charging_sessions` ran through the watermark subquery with the
partition-elimination predicate (see macro note in `cross_db_helpers.sql`).

## Phase 3 · Guardrail drills

| Drill | Command | Expected | Recorded |
|---|---|---|---|
| Per-query byte cap enforced | `bq query --maximum_bytes_billed=1024 'select * from de_mart.fct_charging_sessions limit 1000'` | rejected | ✅ `Query exceeded limit for bytes billed: 1024. 10485760 or higher required.` |
| Partition pruning real | filtered vs unfiltered scan, `INFORMATION_SCHEMA.JOBS_BY_PROJECT` | fewer bytes processed when filtered | ✅ filtered: **54,568 B processed** / unfiltered dbt scans: **1,529,719–1,913,719 B processed** (≈28× pruned); `total_bytes_billed` floors at the 10 MiB minimum-billing unit |
| Load-job receipts | `INFORMATION_SCHEMA.JOBS_BY_PROJECT` `job_type='LOAD'` | all DONE | ✅ 10/10 load jobs `DONE` (two idempotent runs × five tables) |
| Analyst allowed on consumer view | analyst (`de-analyst@` SA) queries `de_consumer.v_daily_revenue` | rows returned | ✅ **7,732 rows** via impersonation |
| Analyst denied raw | analyst queries `de_raw.raw_charging_sessions` | `403 Access Denied` | ✅ `Forbidden: 403 Access Denied: Table slh-gcp-test:de_raw.raw_charging_sessions` |
| Analyst denied mart (bonus) | analyst queries `de_mart.fct_charging_sessions` directly | `403 Access Denied` | ✅ the Authorized View is the *only* read surface — direct mart access is denied too |

## Phase 4 · Authorized View + analyst IAM (Terraform phase 2)

The analyst identity is a dedicated service account,
`de-analyst@slh-gcp-test.iam.gserviceaccount.com` (created key-free; drills run
through credential impersonation with the owner as
`roles/iam.serviceAccountTokenCreator`). Terraform plan: `4 to add, 0 to
change, 0 to destroy` → `Apply complete! Resources: 4 added, 0 changed,
0 destroyed` (view + authorized-view binding in `de_mart` +
`dataViewer` on `de_consumer` + `jobUser` project-wide).

```bash
cd 06-bigquery-warehouse-finops/infra   # analyst_principal = serviceAccount:de-analyst@...
terraform plan && terraform apply       # 4 added / 0 destroyed
```

## FinOps receipts

**Storage footprint (2026-11-24, after the green build):**

| Dataset | Tables | Bytes |
|---|---|---|
| `de_raw` | 7 (5 loaded + 2 schema-only) | 8,294,926 |
| `de_stg` / `de_int` | views only | 0 |
| `de_mart` | 3 dims + 2 snapshot tables + 3 facts | 5,344,135 |
| **Total** | | **13,639,061 B ≈ 13.0 MiB** — 0.13 % of the 10 GB Free-Tier allowance |

**Query scans:** every query ran under the profile cap `maximum_bytes_billed:
104857600`; the day's total billed bytes are orders of magnitude below the
1 TB/month Free-Tier scan allowance.

**Net cost: €0.00.**

## Deviations from design (all recorded in `design.md` §1)

1. **`require_partition_filter` withdrawn (2026-11-24, live finding).** It is
   incompatible with dbt's data tests (they full-scan and cannot carry a
   partition predicate) and with the incremental watermark subquery. The
   enforced cost guard is the profile-level 100 MiB cap (drill 1) plus
   partition pruning (drill 2). Partitioning + clustering stay.
2. **`de_int` dataset added** for intermediate views (design §4 listed four
   datasets; the `de_` naming family is preserved).
3. **Two-phase apply** for the Authorized View (BigQuery validates the view
   query at CREATE time; phase 2 runs after the dbt build).
4. **Roaming excluded from the raw load** (mock paginated API server needed);
   `raw_roaming_settlements` created schema-only — the same boundary as E05.
5. **BigQuery dialect gaps fixed inside macros** (contract §3.9 — business SQL
   stays engine-agnostic; the deltas live in `cross_db*.sql`):
   - `sources.yml`: source `schema` branches to `de_raw` on BigQuery (sources
     bypass `generate_schema_name`).
   - Snapshots: `target_schema` branches to `de_mart` (snapshots bypass the
     naming macro).
   - `bq_contract_type` + dispatched `bigquery__get_empty_schema_sql` /
     `get_table_columns_and_constraints` / `format_column`: BigQuery has no
     `varchar` and rejects parameterized CAST targets; the E03 contract types
     are translated for the two engine-side probe queries (DuckDB path strict).
   - `decimal_type(p, s)` / `as_timestamp(expr)`: BigQuery rejects parameterized
     CASTs in value casts and has no implicit TIMESTAMP/DATE(TIME) comparison.
   - `incremental_lookback_filter`: constant partition predicate on the
     watermark subquery so incremental merges satisfy the partition guard.
6. **Cleanup of this session's own failed attempts:** the dbt-created `mart`
   dataset (stale snapshot copies from the pre-fix runs) and two
   `fct_charging_sessions__dbt_tmp*` leftovers were deleted. These were created
   by this session, not by the approved plan; Terraform state was never
   involved (`0 destroys` refers to Terraform-managed resources, all five
   intact and `prevent_destroy`-guarded).
