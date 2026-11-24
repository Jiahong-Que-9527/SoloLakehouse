# E08 · Acceptance — Observability and DE Platform Template

**Status: accepted 2026-11-24.** dbt's native run artifacts are now parsed
into two operational audit tables with an SLO verdict per source; an injected
+71 h staleness was recorded as a `BREACH` row with a structured alert payload
and a non-zero exit; the DE platform template was extracted and proven by
onboarding a second, fully independent workload. Total cloud cost: **€0** —
everything ran locally (DuckDB, locked fixtures).

## Deliverables

| Deliverable | Location |
|---|---|
| Artifact parser + audit writer | `reference-warehouse/src/charging_commerce/observability.py` |
| CLI subcommand | `charging-commerce audit-dbt` (`src/charging_commerce/cli.py`) |
| Airflow hook | `audit_dbt_artifacts` task, `trigger_rule='all_done'` (DAG: `airflow/dags/charging_commerce_dag.py`) |
| Reusable DE template | `reference-warehouse/template/` (12 files) |
| Second workload (onboarded) | `reference-warehouse/examples/ecb_fx_mart/` |
| Tests | `tests/test_observability.py` (7), `tests/test_observability_integration.py` (2), `tests/test_template_example.py` (3) |
| Drill script + log | `evidence/e08_acceptance_drill.sh` → `evidence/e08-drill-log.txt` |

## The `ops_*` audit tables

Both live in the warehouse's `ops` schema and are **idempotent by design**:
`ops_dbt_run_audit` grain `(invocation_id, unique_id)` and
`ops_freshness_slo` grain `(invocation_id, source_unique_id)`, written with
PK-replace (`insert or replace`), so DAG task retries and operator replays
never duplicate rows.

- `ops.ops_dbt_run_audit` — one row per dbt node per invocation: status,
  `execution_time_s`, failures, execute-phase start/end, `git_sha` (from
  `GIT_SHA` env, CI-stamped), `recorded_at`.
- `ops.ops_freshness_slo` — one row per source per freshness invocation:
  dbt's `freshness_status`, `max_loaded_at` / `snapshotted_at`, computed
  `lag_hours`, the SLO thresholds used, verdict (`PASS` / `WARN` / `BREACH`)
  and the serialized alert payload.

SLO thresholds mirror the contract §1 freshness gates declared in
`dbt_project/models/staging/sources.yml` (warn > 24 h, breach > 48 h). A
source dbt itself reports as `error`/`fail` (e.g. missing relation) is a
`BREACH` even without a computable lag.

**Exit contract** (`audit-dbt`): `0` all PASS and no failed nodes · `1` any
WARN · `2` any BREACH or failed/error node. Every WARN/BREACH/failed node
emits a structured JSON alert line, e.g.:

```json
{"alert": "freshness_slo", "freshness_status": "error", "lag_hours": 71.01, "level": "BREACH", "source": "source.charging_commerce.raw.raw_ecb_fx_rates", "threshold_hours": 48.0}
```

## Acceptance drill (single session, 2026-11-24)

Fresh offline warehouse: generate → ingest ×5 (12,728 sessions, 9,699
stations, 18 tariffs, 21,313 SMARD slots, 507 ECB rates) → `dbt deps` →
freshness (5 sources PASS) → snapshots t0/t1/t2 → full `dbt run` →
`dbt build` (the E07 fresh-warehouse ordering; PASS=126/0 in the drill's
`build`). Run IDs and per-task states below are quoted verbatim from
[e08-drill-log.txt](e08-drill-log.txt).

| Phase | Result |
|---|---|
| RUN A: `audit-dbt` on the green build's artifacts | **exit 0, alerts=0**; `ops_dbt_run_audit` **126 rows** (every node of the real build), `ops_freshness_slo` **5 rows, BREACH=0 WARN=0** |
| DRILL: backdate `raw_ecb_fx_rates._ingested_at` by +71 h, re-run freshness | dbt flags `ERROR STALE` on the source (the other 4 sources stay PASS) |
| DRILL: `audit-dbt` | **BREACH alert JSON emitted (lag 71.01 h > 48 h), exit 2**; `ops_freshness_slo` 10 rows (new invocation appended, BREACH=1 recorded) |
| IDEMPOTENCY: re-run `audit-dbt` on the same artifacts | **still 126 / 10 rows, BREACH=1** — zero duplicates on replay, exit stays 2 |

## Template + second workload (acceptance criteria 2 and 3)

`reference-warehouse/template/` carries the guardrail set as a minimal
vertical slice: `pyproject.toml` (ruff + pytest baseline), `.sqlfluff` (same
taste decisions as the primary), a `dbt_project/` starter with
seed → typed staging → **contract-enforced mart**, the `non_negative`
generic test, a composite-grain singular test, and the cross-db macro pattern
(`decimal_type`, verbatim-schema `generate_schema_name`).

The second workload **`examples/ecb_fx_mart`** (ECB Daily FX Summary Mart,
grain `rate_date × currency_pair`) was instantiated from the template:

- `dbt build --target duckdb`: **PASS=9 / ERROR=0** (seed + 2 models + 6 tests)
- `sqlfluff lint models tests`: clean ("All Finished!")
- `charging_commerce` models: **zero edits** (enforced by
  `test_template_stays_self_contained`, which fails if any template/example
  config or SQL references the primary project)
- regression guard: `tests/test_template_example.py` rebuilds the example in
  CI and asserts grain preservation (507 staged == 507 mart rows, 3 pairs)

### Measured onboarding friction (the honest list)

1. Two renames in `dbt_project.yml` (`name:`, `profile:`) — trivial.
2. Seed drop works from minute one; no ingest machinery needed for a v1 mart.
3. **Nullable-column contract subtlety**: `day_over_day_change` is
   legitimately null on each pair's first observation; the enforced contract
   declares the `data_type` but must not declare a `not_null` constraint —
   dbt contracts treat undeclared constraints as nullable. (Correct on the
   first try, but it is the kind of decision the template README now flags.)
4. **Missing `generate_schema_name` ⇒ `main_stg`**: without the verbatim
   schema macro, dbt concatenates the profile schema (`main_stg`, `main_mart`).
   The macro is part of the template now; a fresh onboarder without it gets
   concatenated schema names silently. (Caught by the first build; fixed by
   copying the macro — the template carries it.)
5. **A data-property test was rewritten once**: the draft asserted a max
   observation gap of one weekend; real ECB calendars also skip public
   holidays (Easter/Christmas push gaps past three days). Replaced with a
   grain-reconciliation test (staging rows == mart rows) — the invariant
   that actually holds. Lesson recorded: pin invariants you can defend, not
   calendar assumptions.
6. **Warehouse file naming collision**: naming the audit target `ops.duckdb`
   makes DuckDB's catalog name (`ops`, from the file basename) collide with
   the `ops` schema — "Ambiguous reference to catalog or schema ops". The
   unit suite hit this and renamed its fixture; documented here as an
   operational gotcha.
7. Wire-up cost: CI needs one workflow step mirroring
   `.github/workflows/data-engineering.yml` for the new directory (template
   README checklist item 7; not exercised in CI here — the pytest guard
   covers the build).

## Test suite

- `tests/test_observability.py` — 7 unit tests on synthetic artifacts:
  node audit + idempotency, PASS/WARN/BREACH classification with thresholds,
  dbt-`error`-status breach without lag, PK-replace idempotency, exit codes
  0/1/2, missing-artifact guard, CLI end-to-end with alert lines.
- `tests/test_observability_integration.py` — 2 tests against the **real**
  artifacts of the session warehouse build (catches dbt artifact-shape
  drift on upgrades; expectations are recomputed from the artifact contents
  so negative-drill residue from sibling tests cannot flake the run).
- `tests/test_template_example.py` — 3 tests guarding the template and the
  second workload (build green, contract enforced, no primary references).
- Full main-env suite: **56 passed / 2 skipped** (was 44+2 before E08);
  Airflow-env DAG tests: **7/7** (incl. the new
  `test_audit_task_records_failed_runs` asserting `trigger_rule='all_done'`).
- `ruff check` + `ruff format --check`: clean.

## DAG wiring

`audit_dbt_artifacts` runs last in `charging_commerce_daily`
(`verify_revenue_conservation >> audit_dbt_artifacts`) with
`trigger_rule='all_done'`: a failed build or a halted freshness gate is
exactly when telemetry matters most, so the task records the failure rows and
breach alerts even on red runs. Its own exit code follows the module contract
(a BREACH or failed node fails the audit task — the alert is loud, not silent).

## Deliverables check

- [x] `audit-dbt` parses `run_results.json` + `sources.json` idempotently into `ops_*` tables (acceptance criterion 1)
- [x] Injected +71 h staleness produces a recorded `ops_freshness_slo` BREACH and an alert payload (criterion 1 / design §5.2)
- [x] Second workload passes `sqlfluff`, `pytest`, `dbt build --target duckdb` with zero `charging_commerce` edits (criterion 2)
- [x] Onboarding friction and template setup steps recorded (criterion 3, above)
- [x] Airflow DAG extended with the audit task (implementation plan step 2)
- [x] 100% local, €0
