# Architecture Decision Records

<!-- [ZCode·2026-11-23] Establish the ADR directory for Data-engineering/. -->

Short-lived, numbered records for decisions that shape the whole track. Each ADR is immutable once accepted; a reversed decision gets a new ADR that supersedes the old one, and the old file stays.

| ADR | Title | Status |
|---|---|---|
| [ADR-0001](ADR-0001-single-cloud-target-bigquery.md) | Single cloud target: GCP BigQuery (Free Tier, europe-west3) | Accepted |
| [ADR-0002](ADR-0002-scd2-via-dbt-snapshot.md) | SCD Type 2 history via `dbt snapshot` (not hand-rolled macros) | Accepted |
| ADR-0003 | Orchestration: Airflow vs Dagster | Planned — deliverable of stage `E07` (see [delivery plan](../delivery-plan.md)) |

New ADRs take the next free number. Stage designs may reference ADRs but do not duplicate their content.
