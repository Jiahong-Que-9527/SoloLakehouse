# Design: E07 · Orchestration with Apache Airflow

**E07 · Design specification — accepted 2026-11-24** (evidence: [e07-acceptance.md](../evidence/e07-acceptance.md); as-built deltas in §6). [Brief](../README.md) · [Implementation plan](implementation.md)

Orchestrate the end-to-end warehouse lifecycle (`ingest -> source freshness -> dbt snapshot -> dbt build -> revenue audit`) in **Apache Airflow** running locally in an isolated Python 3.12 `uv` environment (with an optional Docker Compose setup), passing Airflow logical dates (`{{ ds }}`) for idempotent backfills, and recording an ADR comparing **Airflow** against **Dagster**.

## 1. Decisions

| Topic | Decision |
|---|---|
| Environment isolation | Dedicated `reference-warehouse/airflow/pyproject.toml` (`uv`) separate from `dbt` dependencies |
| Local execution mode | `airflow standalone` (loopback web UI on `127.0.0.1:8080`, SQLite metadata, telemetry disabled) + optional `docker-compose.yml` |
| Cloud Composer | Explicitly out of scope (violates Free Tier / €0 rule in [AGENTS.md](../../../AGENTS.md)) |
| Task structure | Explicit task dependencies: `ingest_raw -> dbt_source_freshness -> dbt_snapshot -> dbt_build_staging_to_marts -> verify_conservation` |
| Parameterized backfill | DAG reads `{{ ds }}` / `dag_run.conf` (`backfill_start`, `backfill_end`, `target`) and passes `--vars` to dbt |
| Failure & recovery | `retries=1` on transient ingestion, `retries=0` on quality/contract failures; recovery clears only the failed downstream task |

## 2. Scope boundary

In scope: isolated Airflow package + DAG, optional Compose definition, DAG import/structure unit tests, scheduled/backfill local run, injected-failure stop + clear-task recovery drill, and Airflow vs Dagster ADR.

Out of scope: Cloud Composer, Kubernetes Executor, and `run_results.json` audit dashboarding (`E08`).

## 3. Architecture

```text
Airflow DAG: charging_commerce_daily (catchup=False, default_args retries)
  [ingest_raw (ds)]
        |
        v
  [dbt_source_freshness]
        |
        v
  [dbt_snapshot]
        |
        v
  [dbt_build_marts (--vars backfill window)]
        |
        v
  [verify_revenue_conservation]
```

## 4. Contracts and configuration

- Airflow invokes `uv --directory <reference-warehouse> run --locked ...` via `BashOperator` (or `astronomer-cosmos` isolated virtualenv mode) so Airflow never shares Python packages with `dbt-core`.
- DAG files must parse cleanly in pytest (`DagBag` import check with zero `import_errors`) in CI without running the Airflow daemon.

## 5. Behaviour and edge cases

1. When `dbt_source_freshness` or a dbt model contract fails, downstream `verify_revenue_conservation` and publication steps stay skipped/upstream_failed.
2. Fixing the failing fixture/input and clicking `Clear` on only the failed task completes the DAG without re-running clean `ingest_raw` partitions.
3. Triggering `airflow dags backfill -s ... -e ...` executes bounded incremental windows idempotently.

## 6. Delivery and cost

100% local execution in WSL2 (`€0`). Airflow logs, SQLite DB, and PIDs stay outside Git.

## 7. Acceptance criteria

1. `DagBag` validation test passes in CI with zero import errors.
2. Full local `charging_commerce_daily` run completes green from `ingest_raw` through `verify_revenue_conservation`.
3. Injected failure halts downstream tasks, and clearing only the failed task recovers the run idempotently; ADR comparing Airflow vs [Mlops-engineering M08 Dagster](../../../Mlops-engineering/08-orchestration-dagster/README.md) is committed.

## 8. Handoff

`E08` adds a final DAG step parsing `dbt` `run_results.json` and `sources.json` into operational observability tables.

## 9. As-built deltas (recorded at acceptance, 2026-11-24)

The accepted implementation follows this design with four recorded deviations —
each is visible in the DAG source and exercised by the acceptance drill:

1. **Ingest batch id is a per-source constant (`e06-raw-load-<source>`), not
   `{{ ds }}`.** The generated payloads are a date-locked snapshot of the whole
   window (regeneration is not byte-stable), so a per-logical-date batch id
   appended the same rows again on every run whose `ds` differed and broke the
   raw-layer unique tests. E01 keys its idempotency state file by batch id
   alone, hence the source suffix (same convention as the E06
   `bq_loader.DEFAULT_BATCH_PREFIX`). Idempotency is stronger, not weaker:
   every run after the first skips ingestion entirely (acceptance log: ingest
   durations ~1 s with 0 rows added across four consecutive runs).
2. **Backfill is passed via `dags trigger --conf`, not `dags backfill`.** The
   bounded window (`backfill_start`/`backfill_end`) reaches dbt through
   `--vars`; `dags trigger` keeps the run inside normal scheduler semantics
   (clear/retry included in the drill).
3. **Recovery clears the failed task with `--downstream --only-failed`.**
   Airflow 2.11 clears do not cascade: leaving `verify_revenue_conservation`
   upstream_failed unless it is cleared too, and a date-range clear without
   `--only-failed` would reset already-succeeded builds in other runs.
   Blast radius stays minimal: upstream producers are never re-run.
4. **`dbt source freshness` excludes `source:raw.raw_roaming_settlements`.**
   The E05 boundary keeps roaming out of this DAG (its collector needs the
   mock API server), so a fresh warehouse has no roaming relation and dbt
   reports the source as an error; roaming freshness is exercised by the E05
   drills. Additionally, the golden unit test
   `fct_charging_sessions_golden_refund_signs` pins the default 48-hour
   watermark filter via a macro override so operator-supplied backfill vars
   cannot change what it asserts.
