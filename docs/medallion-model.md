# Medallion architecture (Bronze / Silver / Gold)

The Medallion pattern tiers data by quality: raw → cleaned → analytics/ML-ready. SoloLakehouse implements it with **Parquet** on **MinIO** (see [ADR-003](decisions/ADR-003-parquet-vs-delta.md)).

## Bronze — raw

**Purpose:** Preserve data as received, with traceability.

- Immutable, append-only partitions; idempotent runs via `ingestion_date` partitions
- Extra columns: `_ingestion_timestamp`, `_source`

**Path pattern:**

```
sololakehouse/bronze/{source}/ingestion_date={YYYY-MM-DD}/{source}.parquet
```

## Silver — cleaned

**Purpose:** Consistent types and semantics across sources.

| Source | Examples of transforms |
|--------|-------------------------|
| ECB | MRO filter, forward-fill, `rate_change_bps`, dedupe |
| DAX | Drop weekends, OHLCV types, `daily_return`, dedupe |

UTC dates; `snake_case` columns; Bronze metadata columns dropped. Quality checks run after transforms.

**Path pattern:**

```
sololakehouse/silver/{source}_cleaned/{source}_cleaned.parquet
```

## Gold — features

**Purpose:** ML-ready, business-meaningful tables.

Demo table: **`ecb_dax_features`** — one row per ECB rate-change event; event-study style joins with DAX returns.

**Path:**

```
sololakehouse/gold/rate_impact_features/ecb_dax_features.parquet
```

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
FROM hive.bronze.ecb_rates;

SELECT observation_date, rate_pct, rate_change_bps
FROM hive.silver.ecb_rates_cleaned
WHERE rate_change_bps != 0
ORDER BY observation_date;

SELECT event_date, rate_change_bps, dax_return_1d, dax_return_5d
FROM hive.gold.ecb_dax_features
ORDER BY event_date;
```

Schema names may match your Hive registration — adjust `hive.*` if your catalog differs.
