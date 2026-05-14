# Dataset ID and Governance Naming Convention

This document defines stable logical dataset IDs for SoloLakehouse-derived
product entities before FinLakehouse and Aviation Lakehouse start producing
long-lived data assets.

It complements the [Product Entity Contract](product-entity-contract.md):

- `PRODUCT_ID` identifies the product entity.
- `DATASET_NAMESPACE` identifies the logical dataset namespace.
- dataset IDs identify governed data assets and must survive physical storage,
  catalog, and runtime migrations.
- [Object Store Abstraction and MinIO Deferral](object-store-abstraction.md)
  defines which object-store values may change without changing dataset IDs.

## Status

- Applies to: v2.5 entity-template preparation.
- Related task: Phase 1, "Prepare Dataset Identity and Governance Naming".
- Related issue: #8.
- Future consumer: v2.6+ dataset contracts and lineage evidence.

## Goals

1. Define stable `fin.*` IDs for the current financial medallion flow.
2. Define stable `aviation.*` naming rules and placeholders before aviation
   sources are selected.
3. Describe how each logical ID maps to object-store paths, Trino tables,
   OpenMetadata entities, Dagster assets, and future governance contracts.
4. Make storage-provider replacement non-disruptive to logical dataset
   identity.

## Naming model

Use this form:

```text
<dataset_namespace>.<domain_subject>_<grain_or_role>_<medallion_layer>
```

Where:

| Part | Rule | Examples |
|---|---|---|
| `dataset_namespace` | Stable namespace from the product entity contract. | `fin`, `aviation` |
| `domain_subject` | Business/source subject in lowercase `snake_case`. | `ecb_rates`, `dax_daily`, `flight_events` |
| `grain_or_role` | Optional qualifier when the subject alone is ambiguous. | `daily`, `airport_route`, `delay_features` |
| `medallion_layer` | Required governed layer suffix. | `bronze`, `silver`, `gold`, `iceberg` |

Rules:

- Use lowercase ASCII.
- Use dots only between namespace and dataset name.
- Use underscores inside dataset names.
- Do not include bucket names, host names, storage providers, dates, or
  environment names.
- Do not encode implementation details such as `parquet`, `minio`, or `s3a`
  unless the dataset itself is an implementation-facing governance asset.
- Use singular stable concepts when possible (`ecb_rates`, not
  `ecb_rates_2026`).
- Add a new logical dataset ID when semantics change materially. Do not reuse an
  existing ID for incompatible schema or meaning changes.

## Layer suffixes

| Suffix | Meaning | Governance expectation |
|---|---|---|
| `bronze` | Raw source-shaped records with ingestion metadata. | Source, owner, retention, rejected-record handling, and freshness expectation are known. |
| `silver` | Cleaned, typed, deduplicated records with stable semantics. | Transformation owner, quality checks, and key columns are known. |
| `gold` | Business, BI, or ML-ready product output. | Consumers, SLA, quality class, and lineage inputs are known. |
| `iceberg` | Iceberg-published form of a governed Gold dataset. | Links back to the canonical Gold logical ID and records current Trino/Iceberg table mapping. |

The `iceberg` suffix is reserved for the current v2.5 pattern where Gold Parquet
is staged first and then exposed through Trino-managed Iceberg. If future
versions make Iceberg the canonical write target, update the mapping while
preserving the logical business dataset identity.

## FinLakehouse dataset IDs

The current financial reference flow maps to the `fin` namespace.
The object paths below use future entity-level target variables for governance
clarity. In the current v2.5 runtime, `${DATA_BUCKET}` is still represented by
`BUCKET_NAME` / the default `sololakehouse` bucket until storage
parameterization is implemented.

| Logical dataset ID | Layer | Current physical object path | Trino mapping | Current Dagster asset | Notes |
|---|---|---|---|---|---|
| `fin.ecb_rates_bronze` | Bronze | `s3a://${DATA_BUCKET}/bronze/ecb_rates/ingestion_date=<date>/ecb_rates.parquet` | Reserved as `hive.bronze.ecb_rates` if Bronze is registered | `ecb_bronze` | Raw ECB interest-rate observations. |
| `fin.dax_daily_bronze` | Bronze | `s3a://${DATA_BUCKET}/bronze/dax_daily/ingestion_date=<date>/dax_daily.parquet` | Reserved as `hive.bronze.dax_daily` if Bronze is registered | `dax_bronze` | Raw DAX daily OHLCV records. |
| `fin.ecb_rates_silver` | Silver | `s3a://${DATA_BUCKET}/silver/ecb_rates_cleaned/ecb_rates_cleaned.parquet` | Reserved as `hive.silver.ecb_rates_cleaned` if Silver is registered | `ecb_silver` | Typed ECB rate series with derived `rate_change_bps`. |
| `fin.dax_daily_silver` | Silver | `s3a://${DATA_BUCKET}/silver/dax_daily_cleaned/dax_daily_cleaned.parquet` | Reserved as `hive.silver.dax_daily_cleaned` if Silver is registered | `dax_silver` | Cleaned business-day DAX series with `daily_return`. |
| `fin.ecb_dax_features_gold` | Gold | `s3a://${DATA_BUCKET}/gold/rate_impact_features/ecb_dax_features.parquet` | `hive.gold.ecb_dax_features` | `gold_features` | Event-study feature table for ECB rate-change events and DAX returns. |
| `fin.ecb_dax_features_iceberg` | Iceberg publication | `${WAREHOUSE_URI}` plus Trino-managed Iceberg table metadata | `iceberg.gold.ecb_dax_features_iceberg` | `trino_gold_tables` registration path | Iceberg-published form of `fin.ecb_dax_features_gold`. |

Notes:

- `${DATA_BUCKET}` and `${WAREHOUSE_URI}` are deployment details from the product
  entity contract.
- The logical `fin.*` IDs stay unchanged if the entity moves from MinIO to
  another S3-compatible object store.
- v2.5 registers Gold in Trino by default. Bronze/Silver table names above are
  reserved names for future registration or governance contracts.
- If Trino schema or table names change during migration, update the mapping
  rows and OpenMetadata service configuration; do not rename the logical IDs.

## Aviation Lakehouse dataset ID placeholders

Aviation source systems are not selected yet, so the namespace and naming rules
are defined first. Replace placeholders only after the domain contract names the
source, grain, and first Gold product.

| Placeholder logical dataset ID | Layer | Intended meaning | Required before implementation |
|---|---|---|---|
| `aviation.<source>_bronze` | Bronze | Raw records from one authoritative aviation source. | Source name, raw schema, ingestion frequency, rejected-record handling. |
| `aviation.<source>_silver` | Silver | Cleaned and typed records derived from the Bronze source. | Silver schema, dedupe key, time-zone policy, quality checks. |
| `aviation.<domain_subject>_gold` | Gold | First aviation business or analytical output. | Business question, consumers, SLA, quality class, lineage inputs. |
| `aviation.<domain_subject>_features_gold` | Gold | ML or feature-oriented aviation output if needed. | Feature definition, training/evaluation use, MLflow requirement. |

Candidate concrete IDs, depending on the first selected domain question:

```text
aviation.flight_events_bronze
aviation.flight_events_silver
aviation.flight_delay_features_gold

aviation.airport_operations_bronze
aviation.airport_operations_silver
aviation.airport_route_performance_gold

aviation.aircraft_utilization_bronze
aviation.aircraft_utilization_silver
aviation.aircraft_utilization_gold
```

Do not create aviation IDs by renaming financial datasets. Each aviation ID must
come from a real or realistic aviation source and a domain-specific Gold output.

## Mapping to physical assets

Every governed dataset should have a mapping record with these fields. The
record can later become the basis for `governance/datasets/*.yaml` in v2.6.

```yaml
dataset_id: fin.ecb_dax_features_gold
product_id: finlakehouse
dataset_namespace: fin
domain: financial_markets
layer: gold
owner: Jiahong Que
quality_class: demo_critical
freshness_sla: business_day
logical_description: ECB rate-change event features joined to DAX returns.
physical_locations:
  object_store:
    provider: minio
    bucket_env: DATA_BUCKET
    path: gold/rate_impact_features/ecb_dax_features.parquet
  trino:
    hive_table: hive.gold.ecb_dax_features
    iceberg_table: iceberg.gold.ecb_dax_features_iceberg
  openmetadata:
    service_name_env: OPENMETADATA_TRINO_SERVICE_NAME
    table_fqn: <service>.gold.ecb_dax_features
dagster:
  asset_key: gold_features
lineage:
  upstream_dataset_ids:
    - fin.ecb_rates_silver
    - fin.dax_daily_silver
upgrade_policy:
  preserve_dataset_id: true
  storage_migration_action: update_physical_locations
```

Minimum mapping fields:

- `dataset_id`
- `product_id`
- `dataset_namespace`
- `domain`
- `layer`
- `owner`
- `physical_locations.object_store`
- Trino table mapping if queryable through Trino
- OpenMetadata service/table mapping if cataloged
- Dagster asset key if produced by Dagster
- upstream logical dataset IDs for Silver/Gold outputs

## v2.6 lineage evidence compatibility

v2.6 governance evidence should use `dataset_id` as the primary stable join key.

Recommended evidence tuple:

```text
dataset_id
product_id
runtime_version
environment
dagster_run_id
asset_key
trino_catalog
trino_schema
trino_table
object_store_provider
bucket
object_path
iceberg_snapshot_id  # when available
evidence_timestamp
```

The fields after `asset_key` are physical evidence for the current deployment.
They may change after side-by-side migration. `dataset_id` and `product_id`
should not change unless the governed product or dataset semantics change.

## Rename and migration rules

Use these rules during entity split, v2.6 upgrade, and object-store migration:

| Change | Dataset ID action | Physical mapping action |
|---|---|---|
| Move from local reference bucket to entity bucket | Preserve | Update bucket and path prefix. |
| Replace MinIO with another S3-compatible object store | Preserve | Update provider, endpoint, bucket, and validation evidence. |
| Rename Trino schema/table for entity-specific labeling | Preserve | Update Trino and OpenMetadata mapping. |
| Rebuild Silver or Gold deterministically from same semantics | Preserve | Record rebuild run/evidence. |
| Change schema compatibly by adding nullable/derived columns | Preserve | Update contract/schema version. |
| Change business meaning, grain, source authority, or incompatible schema | Create new ID | Link old and new IDs in migration notes. |
| Split one dataset into multiple governed outputs | Create new IDs for new outputs | Preserve old ID only if its semantics remain intact. |

## Acceptance checklist

The naming convention is ready when:

- `fin.*` examples cover the current ECB/DAX Bronze, Silver, Gold, and Iceberg
  outputs;
- `aviation.*` placeholders define how aviation IDs will be chosen without
  copying financial semantics;
- each logical ID can map to object-store paths, Trino tables, OpenMetadata
  entities, and Dagster asset keys;
- v2.6 dataset contracts and lineage evidence can use `dataset_id` directly;
- storage provider, bucket, warehouse, and service renames do not require
  logical dataset ID changes.
