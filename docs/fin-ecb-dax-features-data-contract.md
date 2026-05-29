# Data Contract: fin.ecb_dax_features_gold

Minimum dataset contract for the first governed Gold output in FinLakehouse.
This record satisfies the Phase 2 deployment readiness requirement.

## Identity

| Field | Value |
|---|---|
| Logical dataset ID | `fin.ecb_dax_features_gold` |
| Product ID | `finlakehouse` |
| Dataset namespace | `fin` |
| Domain | `financial_markets` |
| Layer | `gold` |
| Trino table | `iceberg.gold.ecb_dax_features` |
| Dagster asset key | `gold_features` |

## Ownership

| Field | Value |
|---|---|
| Owner | Jiahong Que |
| Quality class | `demo_critical` |
| On-call | Owner |

## SLA

| Field | Value |
|---|---|
| Freshness expectation | Complete by end of business day (UTC) on each business day the pipeline runs |
| Minimum row count | 1 |
| Pipeline entry point | `full_pipeline_job` → `gold_features` asset |
| Asset check | `gold_features_min_rows_check` (Dagster) — fails if row count = 0 |

## Schema

| Column | Type | Description |
|---|---|---|
| `event_date` | date | ECB rate-change decision date |
| `rate_change_bps` | float | Change in basis points on the event date |
| `rate_level_pct` | float | Absolute MRO rate on the event date |
| `is_rate_hike` | bool | True when `rate_change_bps > 0` |
| `is_rate_cut` | bool | True when `rate_change_bps < 0` |
| `dax_pre_close` | float | DAX closing price on the business day before the event |
| `dax_return_1d` | float | DAX 1-day return after the event |
| `dax_return_5d` | float | DAX 5-day return after the event |
| `dax_volatility_pre_5d` | float | Std dev of DAX daily returns over the 5 business days before the event |

## Lineage

| Upstream dataset ID | Notes |
|---|---|
| `fin.ecb_rates_silver` | Typed ECB rate series; provides `event_date`, `rate_change_bps`, `rate_level_pct` |
| `fin.dax_daily_silver` | Cleaned DAX series; provides `dax_pre_close`, `dax_return_*`, `dax_volatility_*` |

## Physical mapping

```yaml
physical_locations:
  iceberg:
    warehouse_env: WAREHOUSE_URI
    catalog: hive
    namespace: gold
    table: ecb_dax_features
  trino:
    iceberg_table: iceberg.gold.ecb_dax_features
  openmetadata:
    service_name_env: OPENMETADATA_TRINO_SERVICE_NAME
    table_fqn: <service>.gold.ecb_dax_features
```

## Upgrade policy

| Rule | Value |
|---|---|
| Preserve dataset ID | Yes |
| Compatible schema change | Add nullable columns; preserve existing column names and types |
| Breaking schema change | Create new logical ID; document migration |
| Storage migration | Update `physical_locations`; preserve dataset ID |

## Acceptance criteria

This contract is satisfied when:

- `make pipeline` produces at least one row in `iceberg.gold.ecb_dax_features`.
- Dagster `gold_features_min_rows_check` passes.
- OpenMetadata ingestion discovers `iceberg.gold.ecb_dax_features` under the
  configured Trino service.
- At least one MLflow `ecb_dax_impact` run exists with accuracy metrics.
