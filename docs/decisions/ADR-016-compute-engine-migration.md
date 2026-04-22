# ADR-016: Compute engine migration — move Silver/Gold transformations off pandas

**Status:** Proposed
**Date:** 2026-04
**Supersedes (partially):** computational aspects of [ADR-013](ADR-013-iceberg-gold-trino.md)
**Related:** [ADR-002](ADR-002-trino-vs-duckdb.md), [ADR-003](ADR-003-parquet-vs-delta.md), [ADR-006](ADR-006-v2-dagster-orchestration.md)

## Context

In the v2.5 baseline, Bronze → Silver and Silver → Gold transformations run as **in-process pandas** inside Dagster asset functions (`transformations/*.py`). Trino is then used for:

- Registering a Hive external table on the Gold Parquet folder
- Recreating the Iceberg Gold table via `DROP + CTAS`
- Serving BI (Superset) and ML (`ml/evaluate.py`) reads

This works for the reference scope but has three structural issues:

1. **Engine conflation.** Trino is asked to do both *transformation* (the CTAS rebuild) and *query*. BI latency and ETL latency share the same coordinator and workers.
2. **No real use of Iceberg semantics.** The `DROP + CTAS` pattern rebuilds the table on every run and discards snapshot history, invalidating most of the reason to pick Iceberg (cf. [ASSESSMENT_LAKEHOUSE_DAX_ECB.md §3.2 P2](../ASSESSMENT_LAKEHOUSE_DAX_ECB.md)).
3. **Scaling ceiling.** pandas in a single Dagster process is acceptable for a CSV-sized demo but is not a Lakehouse compute pattern readers can generalize to a real platform.

The ask is therefore: **move transformations to a proper compute engine, and restrict Trino to the query role**.

## Decision

Adopt a **two-phase migration** that ends with **Option C: `dbt-spark` on Apache Spark writing Iceberg, with Trino as the query-only engine**.

Phased, so existing v2.5 contracts (Dagster assets, OpenMetadata, Superset, MLflow) keep working during the transition.

### Phase 1 — Introduce Spark + Iceberg writes (Silver kept in Python initially)

1. Add a Spark service to `docker/docker-compose.yml` (single-node Spark master + 1 worker, with Iceberg 1.5+ Spark runtime jar and the shared Hive Metastore).
2. Replace `transformations/silver_to_gold_features.py` with a PySpark job that:
   - reads Silver Parquet from MinIO
   - writes Gold as an **Iceberg** table (`iceberg.gold.ecb_dax_features`) using `MERGE INTO` keyed on `event_date`, with `partitioning = ARRAY['year(event_date)']`.
3. Delete `ingestion/trino_sql.py::refresh_iceberg_gold_from_hive` and its Hive staging table. Trino no longer writes anything.
4. `ml/evaluate.py` keeps reading `iceberg.gold.ecb_dax_features` via Trino — **unchanged**.
5. Dagster asset `gold_features` changes its body from pandas to a Spark submission (via `dagster-pyspark` or `PySparkResource`).

Exit criteria for Phase 1:
- Trino is read-only (no write DDL/DML executed by the pipeline).
- Iceberg Gold has real snapshot history (`SELECT * FROM iceberg.gold.ecb_dax_features$snapshots` grows on every run).
- Superset, OpenMetadata, MLflow continue to work without changes.

### Phase 2 — Introduce dbt-spark for Silver/Gold

1. Add `transformations/dbt/` as a dbt project using `dbt-spark` with Thrift server / Spark Connect.
2. Convert:
   - `transformations/ecb_bronze_to_silver.py` → `models/silver/ecb_rates_cleaned.sql` (Iceberg incremental, `unique_key='observation_date'`)
   - `transformations/dax_bronze_to_silver.py` → `models/silver/dax_daily_cleaned.sql` (same pattern)
   - the Phase 1 PySpark Gold job → `models/gold/ecb_dax_features.sql`
3. Use `dagster-dbt` to reflect each dbt model as a Dagster asset, preserving the existing asset graph shape (`ecb_bronze → ecb_silver → gold_features` etc.).
4. Add dbt tests (`not_null`, `unique`, `accepted_values`, and a custom freshness test on `event_date`) — these close most of the asset-check gap called out in [ASSESSMENT §4 P4](../ASSESSMENT_LAKEHOUSE_DAX_ECB.md).
5. Enable OpenMetadata's dbt manifest ingestion to surface model lineage and tests in the catalog.

Exit criteria for Phase 2:
- All Silver/Gold logic is declarative SQL under `transformations/dbt/models/`.
- `transformations/*.py` contains only glue/helpers or is removed.
- dbt manifest lineage is visible in OpenMetadata.
- CI runs `dbt build` as part of `make test` equivalents.

### Bronze stays Python

Bronze remains collector-driven Python (Pydantic validation, rejected-record handling). Collector logic is not SQL-shaped and belongs outside dbt; this keeps `ingestion/collectors/*.py` as the stable seam between external sources and the Lakehouse.

## Alternatives considered

### Alternative A — `dbt-trino` (rejected)

- Transformation: dbt emits SQL → **Trino executes** → writes Iceberg via the Trino Iceberg connector.
- Query: same Trino for Superset/ML.
- Rejected because:
  - Violates the explicit constraint that **Trino should only serve queries** — ETL and BI would share the same Trino resources.
  - Trino's Iceberg write support is less mature than Spark's (MERGE semantics, V2 delete files, compaction, snapshot management).
  - Single-engine coupling increases blast radius of any Trino outage.

### Alternative B — PySpark only, no dbt (viable fallback)

- Equivalent to stopping at Phase 1.
- Pros: smallest new surface; authentic Lakehouse pattern (Spark writes Iceberg, Trino reads).
- Cons: no declarative SQL layer; lineage, tests, and documentation remain hand-rolled; misses dbt's native integration with OpenMetadata and Dagster.
- Kept as the **graceful stopping point** if Phase 2 is deferred or scope-trimmed.

### Alternative C — Flink / Kafka streaming path (deferred)

- Out of scope for v2.5/v3. ECB/DAX are batch-natural. Reconsider when a streaming source is introduced.

### Alternative D — Status quo (pandas in Dagster + Trino CTAS)

- Acceptable for demo scale only.
- Does not fix the "Iceberg in name only" problem from ADR-013.
- Does not scale pedagogically: readers see "Lakehouse", but transformation actually runs in a single Python process.

## Rationale

1. **Meets the hard constraint.** Under Option C, Trino never issues DDL/DML from the pipeline — it is a query engine only. Spark owns all writes to Iceberg.
2. **Actually uses Iceberg.** Spark's Iceberg runtime provides `MERGE INTO`, hidden partitioning, snapshot expiration, compaction, schema evolution — the features that justify picking Iceberg in the first place.
3. **SQL-first transformation with governance wins.** dbt's model graph and tests fold neatly into both Dagster (via `dagster-dbt`) and OpenMetadata (via dbt manifest ingestion), materially improving the governance posture tracked by `TASKS.md` Block A.
4. **Unchanged consumer contracts.** Superset dashboards, MLflow experiments, and OpenMetadata Trino ingestion continue to read `iceberg.gold.*` via Trino — no downstream changes in Phase 1 or Phase 2.
5. **Phased = reversible.** Phase 1 alone already delivers most of the win (real Iceberg, Trino read-only). Phase 2 is an additive improvement that can slip without invalidating Phase 1.

## Consequences

### Positive

- Clean separation of compute (Spark) and query (Trino).
- Iceberg gains real meaning (snapshots, time travel, MERGE, compaction).
- Transformation logic becomes SQL-reviewable and testable with dbt.
- Dataset lineage and tests automatically surface in OpenMetadata.
- Removes the fragile `register_gold_tables_trino` retry/backoff code path.

### Negative

- Docker footprint grows: Spark master + worker + Thrift/Connect endpoint.
- Local cold-start time increases (Spark JVM warm-up).
- New operational knowledge required: Spark configs, Iceberg table properties, dbt-spark adapter behavior.
- Two new components to version and test in CI.

### Neutral

- Bronze Parquet layout is unchanged.
- Collector code (`ingestion/collectors/*.py`) is unchanged.
- ML code (`ml/*.py`) is unchanged.
- Trino catalog configuration is unchanged; only the *caller* of Trino changes.

## Migration notes

- **Credentials/S3 config:** Spark needs `spark.hadoop.fs.s3a.endpoint` + MinIO keys; wire these from the same `.env` vars that Trino already uses (`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `MLFLOW_S3_ENDPOINT_URL`).
- **Hive Metastore sharing:** Spark uses the same HMS as Trino. Both engines see the same tables; no dual-catalog bookkeeping.
- **Iceberg table properties** (recommended): `write.format.default=parquet`, `write.parquet.compression-codec=snappy`, `history.expire.max-snapshot-age-ms=604800000` (7 days) to cap snapshot growth in a demo.
- **Local resource budget:** target Spark worker with 2 cores / 2 GB for a laptop-friendly reference footprint.
- **Rollback:** Phase 1 is revertable by reinstating `silver_to_gold_features.py` and the deleted `refresh_iceberg_gold_from_hive`. Phase 2 is revertable by re-pointing Dagster assets at the Phase 1 PySpark job.

## Related work

- [ASSESSMENT_LAKEHOUSE_DAX_ECB.md](../ASSESSMENT_LAKEHOUSE_DAX_ECB.md) — items P2, P4, P5 are largely resolved by this ADR.
- `TASKS.md` Block A (governance contracts) — directly benefits from dbt tests and dbt manifest lineage.
- [ADR-013](ADR-013-iceberg-gold-trino.md) — this ADR supersedes its compute-path portion; the Iceberg-for-Gold decision itself still stands.
