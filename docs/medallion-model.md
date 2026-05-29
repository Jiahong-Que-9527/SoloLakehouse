# Medallion architecture (Bronze / Silver / Gold)

The Medallion pattern tiers data by quality: raw → cleaned → analytics/ML-ready. SoloLakehouse implements all three layers with **Apache Iceberg** via pyiceberg (HiveCatalog + MinIO S3FileIO), superseding the earlier Parquet-only write path (see [ADR-020](decisions/ADR-020-iceberg-all-layers.md)).

For product entities, physical paths and Trino table names are mapped to stable
logical dataset IDs in
[dataset-governance-naming.md](dataset-governance-naming.md). Those IDs are the
governance keys that should survive bucket, catalog, and object-store changes.

## Bronze — raw

**Purpose:** Preserve data as received, with traceability.

- Immutable, append-only Iceberg table; `pyiceberg.append_table` enforces immutability
- Day-partitioned on `_ingestion_timestamp`
- Extra columns: `_ingestion_timestamp`, `_source`

**Trino table:** `iceberg.bronze.{ecb_rates,dax_daily}`

`${WAREHOUSE_URI}` is the Iceberg warehouse root; defaults to `s3://sololakehouse/warehouse` in the v2.5 reference runtime. See [object-store-abstraction.md](object-store-abstraction.md).

## Silver — cleaned

**Purpose:** Consistent types and semantics across sources.

| Source | Examples of transforms |
|--------|-------------------------|
| ECB | MRO filter, forward-fill, `rate_change_bps`, dedupe |
| DAX | Drop weekends, OHLCV types, `daily_return`, dedupe |

UTC dates; `snake_case` columns; Bronze metadata columns dropped. Quality checks run after transforms.
Full overwrite on each pipeline run (idempotent, re-runnable).

**Trino table:** `iceberg.silver.{ecb_rates_cleaned,dax_daily_cleaned}`

## Gold — features

**Purpose:** ML-ready, business-meaningful tables.

Demo table: **`iceberg.gold.ecb_dax_features`** — one row per ECB rate-change event; event-study style joins with DAX returns. Written via `pyiceberg.overwrite_table`; queryable immediately through Trino's Iceberg connector.

All three medallion layers share the same write abstraction (`ingestion/iceberg_io.py`) and are bootstrapped at startup by `scripts/init-iceberg-namespaces.py`. See [ADR-020](decisions/ADR-020-iceberg-all-layers.md).

| Column | Description |
|--------|-------------|
| `event_date` | ECB decision date |
| `rate_change_bps` | Change in basis points |
| `rate_level_pct` | Rate level on event date |
| `is_rate_hike` / `is_rate_cut` | Indicators |
| `dax_return_1d`, `dax_return_5d` | Post-event returns |
| `dax_volatility_pre_5d` | Pre-event volatility |
| `dax_pre_close` | Pre-event close |

## Why not Delta Lake (for this reference stack)?

See [ADR-003](decisions/ADR-003-parquet-vs-delta.md). For single-user, batch, append-only workloads, Parquet is enough; ACID/time travel can be reconsidered when streaming/upsert requirements appear.

## Trino examples

```sql
SELECT COUNT(*), MIN(observation_date), MAX(observation_date)
FROM iceberg.bronze.ecb_rates;

SELECT observation_date, rate_pct, rate_change_bps
FROM iceberg.silver.ecb_rates_cleaned
WHERE rate_change_bps != 0
ORDER BY observation_date;

SELECT event_date, rate_change_bps, dax_return_1d, dax_return_5d
FROM iceberg.gold.ecb_dax_features
ORDER BY event_date;
```
