# Acceptance evidence

<!-- [Antigravity·2026-11-23] Initialize Data Engineering evidence standards. -->

All stages start as `planned`. Mark a stage `accepted` only after every listed check has run after the final edit and link the recorded evidence from the stage README.

## Record for each run

- Scenario, target behavior, exact command(s), UTC timestamp, and observed outcome.
- Git commit SHA, Python version, `uv.lock` SHA-256, and relevant tool versions (`dbt-core`, `dbt-duckdb`, `dbt-bigquery`, `sqlfluff`, `apache-airflow`).
- Input fixture/release IDs and SHA-256 checksums for every locked open-data slice and generated batch.
- Expected vs observed row counts, **revenue conservation reconciliation** (`raw_gross - quarantined == mart_confirmed_eur`, zero unexplained discrepancy), and any skipped checks with explicit reasons.

## Cloud warehouse and FinOps evidence (`E06`)

- BigQuery project (`slh-gcp-test`), region (`europe-west3`), dataset/table names, and redacted runtime identity.
- `INFORMATION_SCHEMA.JOBS` job IDs and `total_bytes_billed` comparing full-scan vs partitioned/clustered incremental runs, confirming €0 Free Tier compliance.

## Drills and failure exercises

- Record the injected fault (schema drift, contract violation, failed dbt test, upstream Airflow failure, freshness breach), first observed symptom, blocked downstream behavior, recovery command/action, and post-recovery reconciliation check.

Keep fixtures deterministic and credentials/private paths out of Git.
