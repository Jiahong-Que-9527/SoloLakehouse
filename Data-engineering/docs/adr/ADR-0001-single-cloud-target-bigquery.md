# ADR-0001 · Single cloud target: GCP BigQuery (Free Tier, europe-west3)

<!-- [ZCode·2026-11-23] Promote the scaffold's rationale into a formal ADR. -->

**Status:** Accepted (2026-11-23, before E01) · Supersedes: none

## Context

`Data-engineering/` needs one cloud warehouse to prove the same dbt project beyond local DuckDB. Constraints: €0 running cost, deterministic offline CI, alignment with German Data Engineer roles, and no duplication of the sibling `databricks/` track (which already covers Delta/Unity Catalog on Databricks Free Edition).

## Decision

Use **GCP BigQuery** in project `slh-gcp-test`, region `europe-west3`, as the single cloud target:

- BigQuery Free Tier only (10 GB storage, 1 TB query scan/month); `maximum_bytes_billed` caps every query (see [E06 design](../../06-bigquery-warehouse-finops/docs/design.md)).
- Local DuckDB (`dbt-duckdb`) remains the CI/default target; `--target bq` runs are explicit operator actions under the [GCP cost gate](../../../AGENTS.md).
- No Cloud Composer, Cloud NAT, always-on VMs, or paid SKUs.

## Consequences

- Models must stay cross-warehouse portable via shared dbt macros (data-contract §3.9) — no BigQuery-only SQL forks.
- Free-tier quotas (concurrency, slot throughput) are acceptable because the workload is a few MB and CI stays offline.
- Databricks lakehouse skills remain covered by the separate `databricks/` project, keeping the portfolio's two tracks complementary rather than redundant.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Databricks Free Edition | Duplicates the sibling `databricks/` track; Free Edition concurrency/quota caps make scheduled demos flaky; weaker match to German DE job descriptions than `dbt + BigQuery + Airflow`. |
| Snowflake trial | Trial account expires and converts to paid; no durable free tier for a long-running portfolio. |
| DuckDB only (no cloud) | Undersells the "same models on a managed warehouse" proof and removes the FinOps evidence (partitioning/`bytes_billed`) that E06 is built around. |
