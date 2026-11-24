# Implementation plan: E08 · Observability and DE platform template

**Status:** accepted 2026-11-24 — `audit-dbt` parses real dbt artifacts into `ops_dbt_run_audit` / `ops_freshness_slo` idempotently; +71h injected staleness recorded a BREACH row and alert JSON (exit 2); template extracted and proven on the `ecb_fx_mart` second workload (dbt build PASS=9/ERROR=0, sqlfluff clean, zero primary edits). See [evidence](../../08-observability-template/evidence/e08-acceptance.md). [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md)

## First delivery

Implement the dbt artifact observability parser (`audit-dbt`), wire it into the E07 Airflow DAG, run a freshness SLO breach drill, extract the reusable DE project template, and onboard a second independent workload through it.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/src/charging_commerce/observability.py`
- `Data-engineering/reference-warehouse/src/charging_commerce/cli.py` (add `audit-dbt` subcommand)
- `Data-engineering/reference-warehouse/airflow/dags/charging_commerce_dag.py` (append `audit_dbt_artifacts` task)
- `Data-engineering/reference-warehouse/template/` (reusable starter scaffold)
- `Data-engineering/reference-warehouse/examples/ecb_fx_mart/` (second workload onboarded from template)
- `Data-engineering/reference-warehouse/tests/test_observability.py`
- `Data-engineering/08-observability-template/evidence/e08-acceptance.md`

## Implementation sequence

1. **Artifact parser (`observability.py`):** Parse dbt `run_results.json` and `sources.json`, compute lag hours and failure counts, and upsert idempotently into `ops_dbt_run_audit` and `ops_freshness_slo` keyed by `invocation_id`.
2. **CLI & Airflow hook:** Expose `charging-commerce audit-dbt --run-results ... --sources ...` and append it to `charging_commerce_daily` (running with `trigger_rule='all_done'` so failures are also recorded!).
3. **Freshness SLO drill:** Feed a stale `sources.json` fixture (> 48h lag), capture the `BREACH` record and alert JSON, then verify idempotent repeat parsing.
4. **Extract DE template:** Package `pyproject.toml`, `.sqlfluff`, starter `dbt_project` with cross-db macros, contract YAML pattern, and Slim CI template under `reference-warehouse/template/`.
5. **Onboard second workload:** Instantiate `examples/ecb_fx_mart/` from the template, verify `sqlfluff`, `pytest`, and `dbt build --target duckdb` pass without touching `charging_commerce`, and record onboarding notes in `evidence/e08-acceptance.md`.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse
uv run --locked pytest tests/test_observability.py -v
uv run --locked charging-commerce audit-dbt --run-results dbt_project/target/run_results.json --sources dbt_project/target/sources.json
cd examples/ecb_fx_mart && uv run --locked dbt build --target duckdb
```

**Negative drill:** Inject a failed model node in `run_results.json` and a >48h stale source in `sources.json`; verify `audit-dbt` records both `error` and `BREACH` rows and exits with the expected alert signal.

## Acceptance evidence

Record in `08-observability-template/evidence/e08-acceptance.md`: sample `ops_dbt_run_audit` and `ops_freshness_slo` outputs, SLO breach drill log, template file list, second-workload `dbt build` output, and measured onboarding friction notes.
