# E07 · Acceptance — Orchestration with Apache Airflow

**Status: accepted 2026-11-24.** All four dag runs green on local Airflow 2.11.2
(scheduled, clean, injected-failure recovery, bounded backfill); the
failure-halt and clear-only-recovery drills behaved exactly as designed; the
raw layer stayed idempotent across every run (zero duplicated rows). Total
cloud cost: **€0** — everything ran locally (metadata DB in a disposable
`/tmp` home, warehouse in the repo's `data/`, DuckDB target).

## Environment

| Component | Version | Notes |
|---|---|---|
| Apache Airflow | **2.11.2** | pinned `>=2.10,<3`; classic imports, `airflow standalone`, fab provider bundled |
| dbt | 1.12.7 (`dbt-duckdb` adapter 1.11.1) | same project as E02–E06, `--target duckdb` |
| Python | 3.12 | isolated `uv` env at `reference-warehouse/airflow/` (`pyproject.toml` + `uv.lock`, 145 packages, `package = false`) |
| Executor / DB | SequentialExecutor + SQLite | metadata DB at `/tmp/slh-airflow-e07` (disposable), **WAL journal mode** |
| Scheduler | `airflow standalone` | loopback webserver :8080, port guard against stale processes |
| DAG | `charging_commerce_daily` | `ingest_raw → dbt_source_freshness → dbt_snapshot → dbt_build_marts → verify_revenue_conservation`, all `BashOperator` with explicit `env`, `cwd=REPO`, `uv run --locked` |

Static checks: DagBag import test **6/6 passed, zero import errors**
(`tests/test_airflow_dag.py`: topology, scheduling config, retry policy,
isolation; runs in the Airflow env only — skipped in the main env via
`importorskip`).

## Runs (single acceptance session, 2026-11-24)

Four dag runs were scheduled by one Airflow instance. Run IDs, states and
durations below are quoted verbatim from the run log
([e07-run-log.txt](e07-run-log.txt)) and the metadata DB.

| # | run_id | type | state | window (UTC) |
|---|---|---|---|---|
| 0 | `scheduled__2026-11-23T05:00:00+00:00` | scheduled (auto-created at unpause) | **success** | 20:03:13 → 20:03:57 |
| 1 | `manual__2026-11-24T20:03:29+00:00` | manual (clean) | **success** | 20:03:58 → 20:04:40 |
| 2 | `manual__2026-11-24T20:04:41+00:00` | manual (failure drill → recovery) | failed → **success** | 20:05:24 → 20:05:40 |
| 3 | `manual__2026-11-24T20:05:45+00:00` | manual (bounded backfill via `--conf`) | **success** | 20:05:46 → 20:06:35 |

### RUN 0 + RUN 1 — clean end-to-end (acceptance criterion 1)

Per-task state/duration (identical shape in both runs; every task `try=1`):

| task | state | duration |
|---|---|---|
| `ingest_raw` | success | 3.57 s (scheduled, initial load) / 1.00 s (RUN 1, state-dir skip) |
| `dbt_source_freshness` | success | 2.8 s |
| `dbt_snapshot` | success | 15.7 s (3 as-of replays: 2025-09-15, 2026-01-15, 2026-05-15) |
| `dbt_build_marts` | success | 12.5–12.6 s (`dbt run` PASS=15 then `dbt build` PASS=124 ERROR=0) |
| `verify_revenue_conservation` | success | 2.8 s |

`dbt build` totals **PASS=124 / ERROR=0** — DuckDB parity with the E06 result.

## RUN 2 — failure-halt + clear-only recovery (criteria 2 and 3)

**Halt (20:05:06 – 20:05:16).** One raw session row's `country_code` was
corrupted to `'XX'` (`session_id=S-CH-000004`) before triggering:

| task | state | notes |
|---|---|---|
| `ingest_raw` | success (try=1) | state-dir idempotent skip; the corrupted row stays |
| `dbt_source_freshness` | success | source freshness passes — the bad *value* is not a staleness problem |
| `dbt_snapshot` | success | snapshots untouched by the bad row |
| `dbt_build_marts` | **failed (try=1)** | `dbt run` PASS=15, then `dbt build` fails fast: `accepted_values_stg_charging_sessions_country_code__DE__CH__PL` — the quality gate halted mart publication exactly as designed |
| `verify_revenue_conservation` | **upstream_failed** | downstream never ran |

**Recovery (20:05:16 – 20:05:40).** The row was restored to `'DE'` and the
halted stage was cleared with the minimal-blast-radius operator command
(never the upstream producers):

```bash
airflow tasks clear charging_commerce_daily \
  -t '^dbt_build_marts$' -s 2026-11-20 -e 2026-12-31 --yes --downstream --only-failed
```

- `--downstream`: Airflow 2.11 clears do not cascade — `verify` would stay
  `upstream_failed` otherwise.
- `--only-failed`: succeeded builds in the other runs are never reset.

Result: `dbt_build_marts` **success (try=2, 11.1 s)**, `verify` **success
(try=1, 2.7 s)**, dag run state **success**. Upstream producers kept
`try_number=1` everywhere — ingest, freshness and snapshots were never
re-executed, and **no raw rows were re-ingested** (12728 sessions before and
after).

## RUN 3 — bounded backfill via `dag_run.conf` (criterion: backfill)

Triggered with:

```bash
airflow dags trigger charging_commerce_daily \
  --conf '{"backfill_start": "2025-10-01", "backfill_end": "2025-10-08"}'
```

All five tasks green (`dbt_build_marts` try=1, 12.7 s): the conf is rendered
into dbt `--vars` and the incremental watermark filter runs in bounded-window
mode (`incremental_lookback_filter`, contract §3.5). The golden unit test
`fct_charging_sessions_golden_refund_signs` pins the default 48-hour
watermark via a macro override, so operator-supplied window vars cannot
change what it asserts. `dbt build --vars '<window>'` alone: **PASS=124 /
ERROR=0**.

## Raw-layer idempotency (end-of-session counts)

| raw table | rows | note |
|---|---|---|
| `raw_charging_sessions` | **12 728** | identical before RUN 1 and after RUN 3 — four runs, zero duplication |
| `raw_stations_bnetza` | 9 699 | |
| `raw_tariff_plans` | 18 | |
| `raw_smard_prices` | 21 313 | |
| `raw_ecb_fx_rates` | 507 | |
| `raw_roaming_settlements` | 0 | E05 boundary: collector needs the mock API server; excluded from freshness here, exercised by E05 drills |

Ingest batch ids are per-source constants (`e06-raw-load-<source>`, E06
`bq_loader` convention): the generated payloads are a date-locked snapshot,
so per-`ds` batch ids would append duplicates on every run whose logical date
differed. With the constant id, E01's payload-hash state check turns every
post-initial run into a ~1 s skip.

## Runbook (as exercised)

1. `uv run --locked airflow standalone` from `reference-warehouse/airflow/`
   (isolated env; port guard fails loudly if 8080/8793/8794 are held).
2. Unpause the DAG (`DAGS_ARE_PAUSED_AT_CREATION=False` in this environment;
   in the UI this is the Unpause toggle). The scheduler immediately creates
   the run for the latest data interval.
3. Triage a halted run from the task log; after fixing the input, recover
   with `tasks clear -t '<failed stage>' --downstream --only-failed`.
4. Bounded backfill: `dags trigger ... --conf '{...}'` (window + `target`).
5. Logs: `/tmp/slh-airflow-e07/logs/dag_id=charging_commerce_daily/...`;
   metadata DB is disposable (WAL mode; recreate with `airflow db migrate`).

## Deliverables check

- [x] Isolated `uv` Airflow env (2.11.2, `uv.lock` committed, offline-reproducible)
- [x] `charging_commerce_daily` DAG (5 tasks, isolation, idempotent ingest, conf-driven backfill)
- [x] DagBag CI test (`tests/test_airflow_dag.py`, 6 tests, zero import errors)
- [x] Local clean run + failure-halt + clear-only recovery + bounded backfill (this document)
- [x] ADR-0003 (Airflow vs Dagster, Accepted)
- [x] Optional Docker Compose wrapper (`airflow/docker-compose.yml`, untested — no daemon in this environment)

As-built deviations from the design are recorded in
[design §9](../docs/design.md#9-as-built-deltas-recorded-at-acceptance-2026-11-24):
constant ingest batch ids, `dags trigger --conf` instead of `dags backfill`,
`--downstream --only-failed` recovery semantics, and the roaming freshness
exclusion.
