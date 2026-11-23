# Acceptance evidence

<!-- [Antigravity·2026-11-23] Initialize Data Engineering evidence standards. -->
<!-- [ZCode·2026-11-23] Align conservation reconciliation with data-contract §3.1 canonical form; require dbt artifact schema versions from E05. -->

All stages start as `planned`. Mark a stage `accepted` only after every listed check has run after the final edit and link the recorded evidence from the stage README.

## Record for each run

- Scenario, target behavior, exact command(s), UTC timestamp, and observed outcome.
- Git commit SHA, Python version, `uv.lock` SHA-256, and relevant tool versions (`dbt-core`, `dbt-duckdb`, `dbt-bigquery`, `sqlfluff`, `apache-airflow`).
- Input fixture/release IDs and SHA-256 checksums for every locked open-data slice and generated batch.
- From `E05` onward: dbt artifact schema versions (`manifest.json` → `metadata.dbt_schema_version`) for every artifact stored/compared by Slim CI, so `--state` comparisons stay version-compatible.
- Expected vs observed row counts, **revenue conservation reconciliation** in the canonical form of [data-contract.md §3.1](data-contract.md) (`SUM(net_amount_eur recomputed from valid raw events, latest event per session) == SUM(fct_charging_sessions.net_amount_eur)`, tolerance `0.00` EUR, quarantined rows reported separately by count and amount), and any skipped checks with explicit reasons.

## Cloud warehouse and FinOps evidence (`E06`)

- BigQuery project (`slh-gcp-test`), region (`europe-west3`), dataset/table names, and redacted runtime identity.
- `INFORMATION_SCHEMA.JOBS` job IDs and `total_bytes_billed` comparing full-scan vs partitioned/clustered incremental runs, confirming €0 Free Tier compliance.

## Drills and failure exercises

- Record the injected fault (schema drift, contract violation, failed dbt test, upstream Airflow failure, freshness breach), first observed symptom, blocked downstream behavior, recovery command/action, and post-recovery reconciliation check.

Keep fixtures deterministic and credentials/private paths out of Git.
