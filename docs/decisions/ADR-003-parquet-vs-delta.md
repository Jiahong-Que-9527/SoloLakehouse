# ADR-003: Why v1 Uses Parquet Instead of Delta Lake

**Status:** Accepted
**Date:** 2024-01

## Context

Modern Lakehouse architectures typically use an open table format (Delta Lake, Apache Iceberg, or Apache Hudi) on top of Parquet files. These formats add ACID transactions, time travel, schema evolution, and efficient upserts to the otherwise immutable Parquet layer. v1 needs to decide whether to use plain Parquet or a table format.

## Decision

v1 uses plain Parquet files without a table format layer.

## Rationale

**1. v1's ingestion pattern is append-only — ACID transactions are not required.**
Delta Lake's primary value proposition is handling concurrent writes safely. In v1, there is exactly one writer (the ingestion script), running in a sequential batch process. There are no concurrent writes to protect against.

**2. Time travel is already implemented via Medallion partitioning.**
Delta Lake's time travel feature allows querying data as of a specific transaction ID or timestamp. In v1's Bronze layer, every ingestion creates a new `ingestion_date=YYYY-MM-DD` partition. This provides equivalent point-in-time traceability for the raw data layer.

**3. Delta Lake adds Docker image complexity and version compatibility risk.**
Using Delta Lake in Python requires `delta-rs` (if using DuckDB/Polars) or `delta-spark` (if using PySpark). Both add significant dependencies. The Trino Delta Lake connector also has version compatibility constraints that require careful version pinning. For v1, this complexity has no offsetting benefit.

**4. Parquet is universally readable.**
Any tool that can read Parquet can read v1's data without any additional driver or library. This maximises interoperability and simplifies the `verify-setup.py` health checks.

## Upgrade Path

v2 will introduce Delta Lake via `delta-rs` (Python binding). The trigger conditions are:
- **Streaming ingestion**: Kafka or API streaming will require idempotent upserts, where ACID is a genuine requirement
- **Schema evolution**: As the ECB or DAX data schema changes over time, Delta Lake's schema evolution tracking becomes valuable
- **Incremental processing**: delta-rs enables efficient CDC (Change Data Capture) patterns

The existing Parquet data can be converted to Delta format with `delta-rs` without data loss.

## Considered Alternatives

**Apache Iceberg:** Also an excellent choice. Chosen not to use in v1 for the same reasons as Delta Lake (adds complexity, no clear v1 benefit). Will re-evaluate at v2/v3.

**Apache Hudi:** Less adoption in the Python ecosystem; skipped.
