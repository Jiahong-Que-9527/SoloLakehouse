# Finance-domain data expansion — design (planning only)

## Status

- **Owner Decision `2026-09-08`:** deepen the existing finance domain first.
  No new domain is opened by this document.
- **Planning only.** No code is changed by this document. Task IDs `L5`–`L7`
  are defined in [`TASKS.md`](../TASKS.md) Block `L` and are **not started**.
- **Scope boundary:** everything below stays inside the sources already named
  by Owner Decision `2026-09-03` (`D4` in [`docs/roadmap.md`](roadmap.md)) —
  ECB SDW and Alpha Vantage EWG. The Block `L` non-goal *"any domain beyond
  ECB/German-equity-proxy/crypto"* is **not** amended and **not** exercised.
  FRED, energy and aviation sources are surveyed elsewhere and each need their
  own Owner Decision before any implementation.

## Why

Two separate complaints, which earlier drafts conflated:

1. **Only one data *shape*.** Every governed finance table is a single-valued
   daily time series keyed on `observation_date`. Nothing in the warehouse is a
   panel (many entities per date), so no transformation, contract or dashboard
   in the repo has ever had to handle a second key column.
2. **Nothing *visible* changes daily.** `gold.ecb_german_equity_proxy_features`
   is event-grained — one row per ECB rate *change*, roughly eight per year.
   The Gold layer, and therefore Superset, is static for months at a time.

Complaint 2 is **not** true of Bronze and Silver. Verified 2026-09-08 against
the live API: `FM/D.U2.EUR.4F.KR.MRR_RT.LEV` publishes a value on **every
calendar day**, weekends included, holding the last decided rate constant
(2026-08-28 … 2026-09-08 all return `2.4`). `bronze.ecb_rates` and
`silver.ecb_rates_cleaned` do gain a row per day already. The daily-refresh
story is broken only at the Gold layer.

That is why this plan is not simply "add another source". It is: give the
warehouse a second data shape, and give Gold a table that moves every business
day.

## Verified source facts (2026-09-08, live)

| Fact | Evidence |
|---|---|
| ECB MRO series is daily-calendar, not event-grained | `lastNObservations=12` returns 12 consecutive calendar days including Sat/Sun |
| The whole EXR daily FX panel is retrievable in **one** request | `GET EXR/D..EUR.SP00.A?format=jsondata` → HTTP 200, 44 series |
| 29 of those 44 currencies published a rate for 2026-09-08 | AUD BRL CAD CHF CNY CZK DKK GBP HKD HUF IDR ILS INR ISK JPY KRW MXN MYR NOK NZD PHP PLN RON SEK SGD THB TRY USD ZAR |
| 15 are discontinued and must not be treated as stale rows | BGN ended 2025-12-31 (euro adoption), RUB 2022-03-01, HRK 2022-12-30, TWD/ARS/DZD/MAD 2020-10-30, LTL 2014-12-31, LVL 2013-12-31, EEK 2010-12-31, SKK 2008-12-31, CYP/MTL 2007-12-31, SIT 2006-12-29, GRD 2000-12-29 |
| EXR needs no API key and publishes no documented quota | same host and auth model as the collector already in production |
| EXR and EWG run on different calendars | EXR follows TARGET; EWG follows NYSE. 2026-09-07 was US Labor Day, so `bronze.german_equity_proxy_daily` stopped at 2026-09-04 while EXR published on 09-07 |
| The Alpha Vantage free tier is 25 requests/day | already consumed by the EWG collector; no headroom for more symbols |

## What gets added

Three workstreams. `L5` is independent and comes first; `L6` depends on an
EXR panel parse (policy-rate `L4-ecb` DFR/MLF already landed on `#85`); `L7`
depends on `L6`.

### `L5` — a freshness SLA that can actually fire

**The hole.** `governance/quality.py:36-40` implements `max_gap_days` as

```python
deltas = dates.sort_values().drop_duplicates().diff().dropna().dt.days
if not deltas.empty and int(deltas.max()) > rules.max_gap_days:
```

which measures **holes inside the observation history**, not the age of the
newest row. `ingestion/quality/bronze_checks.py:92` runs it over the full
Bronze table (ECB is fetched from `startPeriod=1999-01-01` on every run, and
`BronzeWriter.write` overwrites rather than appends, so Bronze is always a
complete snapshot of source history). When a source stops publishing, the set
of internal gaps is unchanged and `deltas.max()` does not move. **The check
passes forever, at any threshold.** Lowering `max_gap_days` from 180 to 3–5, as
earlier drafts proposed, does not fix this; on the event-grained Gold table it
would instead start failing on legitimate multi-month gaps between rate
decisions.

**The fix.** Separate two independent properties that were being conflated:

| Property | Question | Rule |
|---|---|---|
| Continuity | are there holes *inside* the history? | `max_gap_days` (existing) |
| Freshness | how old is the *newest* row? | `max_staleness_days` (new) |

Additive changes to `governance/contracts.py::QualityRules`:

```yaml
update_pattern: daily_calendar | business_day | event_driven   # default: business_day
max_staleness_days: int | null                                  # default: null
```

Validator rules:

- `max_staleness_days` requires `date_column` (same shape as the existing
  `max_gap_days` guard).
- `max_gap_days` is **rejected** when `update_pattern: event_driven` — that
  combination is the current misconfiguration and should become unexpressible.

**Enforcement point — asset check, not write gate.** Staleness is a source-health
condition, not a correctness defect in the rows being written. Failing
`validate_dataset_quality()` would abort the daily run and stop Gold from being
rebuilt at exactly the moment an operator most wants the last good state
queryable. So `max_staleness_days` is declared in the contract but enforced as
a Dagster `@asset_check` per governed table, shaped like the existing
`ecb_german_equity_proxy_features_min_rows_check`, with
`AssetCheckSeverity.WARN`. The result surfaces through the existing run-status
email in `dagster/pipeline_notifications.py`, which already reports the max
observation date per table.

Proposed per-dataset settings:

| Dataset | `update_pattern` | `max_staleness_days` | `max_gap_days` |
|---|---|---|---|
| `fin.ecb_rates_bronze` | `daily_calendar` | 3 | 2 *(was 180)* |
| `fin.ecb_rates_silver` | `daily_calendar` | 3 | 2 *(was 180)* |
| `fin.german_equity_proxy_daily_bronze` | `business_day` | 5 | 5 *(was 30)* |
| `fin.german_equity_proxy_daily_silver` | `business_day` | 5 | 5 *(was 30)* |
| `fin.ecb_german_equity_proxy_features_gold` | `event_driven` | *(none)* | **removed** |
| `fin.ecb_fx_rates_bronze` *(new, `L6`)* | `business_day` | 5 | 5 |
| `fin.ecb_fx_rates_silver` *(new, `L6`)* | `business_day` | 5 | 5 |
| `fin.eur_market_daily_gold` *(new, `L7`)* | `business_day` | 5 | 5 |

`max_gap_days: 2` on the ECB rate series is deliberate: the source publishes
seven days a week, so any hole at all is a real defect. `5` on the EWG and FX
series absorbs a normal weekend plus a public holiday; the longest routine
TARGET closure (Easter, Fri–Mon) is 4 days.

The two deprecated `fin.dax_*` contracts are left exactly as they are —
frozen historical record, no SLA.

### `L6` — ECB EXR daily FX panel (a second data shape)

Same source, same host, same auth model, new dataflow. This is **not** a new
domain and needs no non-goal amendment.

**Prerequisite status.** `L4-ecb-a`…`d` landed on `#85`: MRO/DFR/MLF are
fetched as separate series URLs with a `rate_type` column. That is enough for
policy rates, but **not** for EXR: a panel response still needs series keys
resolved against `structure.dimensions.series` so each row keeps its
`currency`. `L6` adds that panel parse (shared ECB HTTP client, new FX path or
collector) rather than redoing DFR/MLF.

**Request.** `GET /service/data/EXR/D..EUR.SP00.A?format=jsondata&startPeriod=1999-01-01`
— the empty `CURRENCY` position is an SDMX wildcard, so all currencies arrive
in a single call. Dimension order is `FREQ:CURRENCY:CURRENCY_DENOM:EXR_TYPE:EXR_SUFFIX`;
a series key of `0:0:0:0:0` resolves position 1 against the `CURRENCY`
dimension's `values` array.

**Bronze — `fin.ecb_fx_rates_bronze` → `iceberg.bronze.ecb_fx_rates`**

| Column | Type | Note |
|---|---|---|
| `observation_date` | date | |
| `currency` | string | ISO 4217, second key column — the first panel key in the warehouse |
| `fx_rate` | double | units of `currency` per 1 EUR. Named `fx_rate`, never `rate_pct`, so it cannot be confused with an interest rate |
| `_ingestion_timestamp` | timestamptz | partition source, `DayTransform`, consistent with the existing two Bronze tables |
| `_source` | string | `ECB_SDW` |

Bronze keeps **all 44 series including discontinued currencies** — Bronze is
source-shaped by definition, and the discontinuation dates are themselves a
governance fact worth retaining. Volume is ~250k rows (29 active × ~6,800
business days, plus the discontinued tails), rewritten per run under the
existing overwrite semantics.

`ingestion/bronze_writer.py::_BRONZE_TABLE_META` must gain an `ecb_fx_rates`
entry; the current fallback silently reuses `BRONZE_ECB_RATES_SCHEMA` with no
partition spec, which would write a wrong-shaped table without raising.

**Silver — `fin.ecb_fx_rates_silver` → `iceberg.silver.ecb_fx_rates_cleaned`**

Typed, deduplicated on `(observation_date, currency)`, plus a per-currency
`fx_return_pct` against that currency's previous published date. Discontinued
currencies are dropped here.

*Active-set policy (decision needed — see open questions).* Recommended:
resolve the active set **dynamically** as "currency has an observation within
10 calendar days of the panel's max date", and log the resolved set on every
run. A hardcoded allow-list would have silently carried BGN as a permanently
stale row from 2026-01-01 when Bulgaria adopted the euro — the dynamic rule
notices, an allow-list does not. **No forward-fill:** a currency that did not
publish has no row, rather than a fabricated one.

**Gold — see `L7`.**

### `L7` — `fin.eur_market_daily_gold`, a Gold table that moves every business day

**Grain:** one row per TARGET business day. Wide, denormalized, BI-shaped —
long/normalized at Silver, wide at Gold.

**Physical:** `iceberg.gold.eur_market_daily`, Dagster asset `eur_market_daily`,
full overwrite per run like the existing Gold table.

| Column | Source | Note |
|---|---|---|
| `observation_date` | EXR | TARGET business day |
| `ecb_mro_rate_pct` | `silver.ecb_rates_cleaned` | exact-date lookup; the series publishes daily so this is always present |
| `eur_usd`, `eur_gbp`, `eur_chf`, `eur_jpy`, `eur_cny` | `silver.ecb_fx_rates_cleaned` | basket is an Owner-adjustable parameter |
| `eur_usd_return_pct_1d` | derived | |
| `ewg_close_usd` | `silver.german_equity_proxy_daily_cleaned` | null when NYSE was closed |
| `ewg_close_eur` | derived | `ewg_close_usd / eur_usd` |
| `ewg_return_eur_pct_1d` | derived | EUR-denominated return |
| `ewg_price_date` | join key | the NYSE date actually used; null when unmatched |

`ewg_close_eur` is the reason this table earns its place rather than being a
row-count exercise. EWG is a USD-quoted NYSE ETF used as a proxy for German
equity; every existing return in the warehouse is therefore contaminated by
EUR/USD moves. EXR is what makes the *existing* market leg interpretable for a
euro-based analysis.

It is also the first table in the repo that has to reconcile two calendars.
Rule: **inner join on date for the FX leg, left join for the equity leg, no
forward-fill.** A TARGET day with no NYSE session yields a row with FX and the
policy rate populated and the EWG columns null, and `ewg_price_date` records
which price date was used so the join is auditable. Coverage is reported by
`run_silver_quality_report`.

The existing event-grained `fin.ecb_german_equity_proxy_features_gold` is
unchanged and is not superseded — the two answer different questions.

**Superset:** one tile on the daily table (EUR/USD line plus EWG-in-EUR) is
part of `L7`'s definition of done. Without it the new rows are invisible and
the original complaint is not actually answered.

## Explicitly out of scope

| Not doing | Why |
|---|---|
| More central-bank policy-rate tables | Same shape as `ecb_rates`; adds rows, not information |
| FRED (`DCOILBRENTEU`, `DGS10`) | A genuinely new domain under the Block `L` non-goals. Surveyed, not decided. Needs its own Owner Decision |
| SMARD / Energy-Charts electricity | New domain **and** the first intraday source; changes Bronze partitioning assumptions everywhere. Needs its own Owner Decision |
| Crypto | Already scoped as Block `L` Phase 2 — isolated, optional, deferred until Phase 1 lands. Do not conflate with this plan |
| More Alpha Vantage symbols | Shares the same 25 req/day quota the EWG collector already consumes |
| Anything aviation | Sequenced after the finance domain is stable; source selection separately deferred, and must stay clear of externally controlled ADS-B data |

## Sequencing

```text
L5  freshness SLA model           (independent; do first)
      ↓
L6  EXR panel: bronze + silver + contracts
      (L4-ecb DFR/MLF already landed; add EXR panel parse)
      ↓
L7  eur_market_daily gold table + Superset tile
```

`L5` first because it is the only workstream that needs no new data and it is
what makes "the pipeline ran today" mean something. Running `L6` before `L5`
would add a source whose staleness is as undetectable as the current ones.

Effort reference: the EWG implementation
(`ingestion/collectors/ewg_collector.py` + schema + transform + contracts +
checks + Dagster wiring) is ~400–500 lines. `L6` should be smaller because the
collector is shared; `L7` is a transform plus a contract.

## Owner defaults (resolved 2026-09-09)

1. **Currency basket for `L7`:** USD/GBP/CHF/JPY/CNY (USD required for EWG).
2. **Active-currency policy at Silver:** dynamic 10-day rule.
3. **Staleness severity:** `WARN` asset check (not a write gate).
4. **`silver.ecb_rates_cleaned` forward-fill:** drop once L5 / `max_gap_days: 2`
   is in force.

## Related documents

- [`TASKS.md`](../TASKS.md) Block `L` — authoritative task tracking, IDs `L5`–`L7`
- [`docs/roadmap.md`](roadmap.md) `D4` — the 2026-09-03 source decision
- [`docs/dataset-governance-naming.md`](dataset-governance-naming.md) — dataset ID rules and the `fin.*` mapping table
- [`docs/layer1-source-selection-criteria.md`](layer1-source-selection-criteria.md) — the gates any new source must pass
