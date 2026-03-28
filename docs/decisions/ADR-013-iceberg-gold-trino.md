# ADR-013: Apache Iceberg for Gold (Hive Metastore catalog)

**Status:** Accepted  
**Date:** 2026-03

## Context

v1–v2 stored Gold features as Parquet files in MinIO and registered a Hive external table for Trino. ADR-003 deferred open table formats until a clear benefit.

## Decision

Introduce **Apache Iceberg** for the **Gold** feature table (`ecb_dax_features`), using:

- Trino **Iceberg** connector with `iceberg.catalog.type=hive_metastore` (same Hive Metastore as the Hive catalog)
- **Staging**: Parquet remains written to `gold/rate_impact_features/` by the existing Python transform
- **Registration**: After each write, Trino runs `CREATE TABLE iceberg.gold.ecb_dax_features AS SELECT * FROM hive.gold.ecb_dax_features` (after ensuring the Hive external table points at the Parquet location)

Bronze and Silver remain **Parquet-on-MinIO** with Hive-style paths; only Gold is promoted to Iceberg for this reference scope.

## Rationale

- Demonstrates table-format evolution without replacing the entire medallion
- Keeps a single metastore and object store story
- Aligns with ADR-012 “upgrade-ready” catalog posture

## Consequences

- ML training reads Gold via Trino (`iceberg.gold.ecb_dax_features`) when `TRINO_URL` is set; without Trino, evaluation falls back to reading the staging Parquet file
- Extra Trino DDL steps on each Gold refresh (acceptable for batch demo scale)

## Related

- [ADR-003](ADR-003-parquet-vs-delta.md)  
- [ADR-012](ADR-012-v3-data-governance-catalog-strategy.md)
