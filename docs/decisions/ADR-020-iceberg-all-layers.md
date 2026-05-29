# ADR-020 — Iceberg for All Medallion Layers (Bronze / Silver / Gold)

**Status:** Accepted  
**Date:** 2026-05-29  
**Supersedes:** ADR-003 (Parquet vs Delta — Bronze/Silver now also Iceberg), ADR-013 (partial — Gold no longer needs Hive staging CTAS)

---

## Context

Until v2.5, the write path was a three-layer hybrid:

| Layer | Write mechanism | Storage |
|-------|----------------|---------|
| Bronze | PyArrow `put_object` to MinIO | Hive-unregistered Parquet files |
| Silver | PyArrow `put_object` to MinIO | Hive-unregistered Parquet files |
| Gold | PyArrow `put_object` → Trino Hive external table → Trino CTAS | Parquet + Hive external + Iceberg |

Problems with this approach:
1. Bronze and Silver data was invisible to Trino and OpenMetadata (unregistered Parquet).
2. The Gold two-step (Hive staging → CTAS into Iceberg) was fragile and slow.
3. Three different write mechanisms increased maintenance surface and test complexity.
4. Schema drift between Parquet files and Iceberg table was not caught until runtime.

## Decision

Adopt **Apache Iceberg for all three medallion layers**, written directly via **pyiceberg** (HiveCatalog + MinIO S3FileIO).

- Bronze: `iceberg_io.append_table()` — immutable append; day-partitioned on `_ingestion_timestamp`.
- Silver: `iceberg_io.overwrite_table()` — full replace on each pipeline run (idempotent, re-runnable).
- Gold: `iceberg_io.overwrite_table()` — same as Silver; replaces the former Hive-staging CTAS path.

All tables are catalogued in the existing Hive Metastore (Thrift), which Trino already uses for its `iceberg` connector. Tables are bootstrapped at startup by `scripts/init-iceberg-namespaces.py` (called from `make up`).

### New table names

| Old identifier | New identifier |
|---------------|----------------|
| `bronze/ecb_rates/ingestion_date=…/*.parquet` | `iceberg.bronze.ecb_rates` |
| `bronze/dax_daily/ingestion_date=…/*.parquet` | `iceberg.bronze.dax_daily` |
| `silver/ecb_rates_cleaned/*.parquet` | `iceberg.silver.ecb_rates_cleaned` |
| `silver/dax_daily_cleaned/*.parquet` | `iceberg.silver.dax_daily_cleaned` |
| `hive.gold.ecb_dax_features` + `iceberg.gold.ecb_dax_features_iceberg` | `iceberg.gold.ecb_dax_features` |

The Hive Trino connector is retained as an escape hatch (still configured in `hive.properties`) but no longer participates in the pipeline write path.

## Consequences

**Positive:**
- All layers queryable via Trino (`SELECT * FROM iceberg.bronze.ecb_rates`).
- OpenMetadata can discover all three layers from the same Iceberg catalog.
- Single write abstraction (`iceberg_io.py`) — easier to test, mock, and evolve.
- Bronze immutability enforced by Iceberg's append-only semantics.
- Schema-on-write enforced by pyiceberg at ingest time.
- Eliminates Hive staging intermediary and the `register_gold_tables_trino` / CTAS flow.

**Negative / Trade-offs:**
- Adds `pyiceberg[hive,s3fs]` dependency (~10 MB, thrift client included).
- Cold pipeline start now requires Hive Metastore to be up before Bronze writes (was MinIO-only before).
- Historical Parquet data in `bronze/`, `silver/`, `gold/` is not automatically migrated — a `make clean && make up && make pipeline` is needed to rebuild from source data.

## Alternatives Rejected

- **Trino INSERT INTO Bronze/Silver**: Would require materialising DataFrames into temporary Hive external tables before INSERT — essentially the same two-step problem that existed for Gold.
- **Keep Parquet for Bronze/Silver, Iceberg only for Gold**: Leaves the discoverability gap for the two most frequently queried exploration layers.
- **REST catalog (ADR-017)**: Deferred — HiveCatalog is already present, REST catalog is a v3+ infrastructure upgrade.
