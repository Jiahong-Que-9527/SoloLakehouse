# Design: E08 · Observability and DE platform template

**E08 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md)

Close the DataOps loop by ingesting dbt's `run_results.json` and `sources.json` artifacts into operational audit tables (`ops_dbt_run_audit`, `ops_freshness_slo`), exercising a freshness SLO breach drill, and extracting a reusable Data Engineering starter template verified by onboarding a second lightweight workload.

## 1. Decisions

| Topic | Decision |
|---|---|
| Telemetry source | dbt native `target/run_results.json` + `target/sources.json` (plus `bytes_billed` when `--target bq`) |
| Audit tables | `ops_dbt_run_audit` (run ID, invocation time, node ID, status, execution_time_s) & `ops_freshness_slo` (source, max_loaded_at, snapshotted_at, slo_status) |
| SLO alerting | Local threshold check emitting structured JSON alert when freshness lag > 24h warn / 48h error or model failure occurs |
| Template scope | `reference-warehouse/template/` holding `pyproject.toml`, `.sqlfluff`, `dbt_project` starter, macros, Slim CI workflow, and contract/test skeleton |
| Second workload | Lightweight **ECB Daily FX Summary Mart** (independent `dbt_project` / schema) onboarded via template without editing `charging_commerce` |

## 2. Scope boundary

In scope: dbt artifact parser (`observability.py`), `ops_*` tables + freshness SLO drill, reusable DE template under `template/`, and onboarding + testing the second domain.

Out of scope: paid monitoring SaaS (Datadog, Monte Carlo, Grafana Cloud) and altering primary EV charging models.

## 3. Architecture

```text
dbt source freshness / dbt build
        |  writes target/sources.json + target/run_results.json
        v
charging-commerce audit-dbt
        |
        +--> ops_dbt_run_audit (per-node status, timing, git_sha)
        '--> ops_freshness_slo (lag check -> PASS / WARN / BREACH alert JSON)

reference-warehouse/template/ ---> onboard 2nd workload (ecb_fx_mart) ---> isolated dbt build + pytest + sqlfluff
```

## 4. Contracts and configuration

- `ops_dbt_run_audit` grain: `(invocation_id, unique_id)`. Re-ingesting the same `invocation_id` is idempotent.
- The template enforces the same E02–E05 guardrails (SQLFluff, generic/singular tests, `contract: {enforced: true}`, cross-db macros) while keeping each workload's domain contracts isolated.

## 5. Behaviour and edge cases

1. Re-running `charging-commerce audit-dbt` on the same `run_results.json` produces zero duplicate rows.
2. Injecting a 50-hour-old `_ingested_at` source timestamp writes a `BREACH` row in `ops_freshness_slo` and exits non-zero / emits alert payload.
3. Both `charging_commerce` and the second template-onboarded workload pass their tests independently in the same repository without schema or macro collisions.

## 6. Delivery and cost

100% local execution (`€0`).

## 7. Acceptance criteria

1. `audit-dbt` parses `run_results.json` and `sources.json` idempotently into `ops_*` tables.
2. Injected freshness delay produces a recorded `ops_freshness_slo` breach and alert payload.
3. The second onboarded workload passes `sqlfluff`, `pytest`, and `dbt build --target duckdb` with zero edits to `charging_commerce` models, and onboarding friction is documented.

## 8. Handoff

Completing `E08` closes the entire `Data-engineering/` portfolio track (`E01–E08`).
