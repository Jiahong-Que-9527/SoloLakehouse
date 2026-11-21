# M01 · EDA report — dataset-v001

**Release:** `dataset-v001` (seed 20261121, window 2025-01-01T00:00Z → 2026-12-31T23:00Z)
**Manifest:** `releases/dataset/v001/manifest.json`, digest `e0c8096c…741e6bfa0`
**Generated:** 2026-11-21, WSL2 Ubuntu, Python 3.13.14 / numpy 2.5.5 / pyarrow 26.0.1
**Source commit:** `c769b71` (branch `feat/full-run-m4-tooling` at generation time)

Every number below is reproducible from the release ID: regenerate with
`uv run charging-forecast generate --config configs/dataset-v001.yaml --out <dir>`
(two runs produce identical SHA-256 per partition, see the acceptance record).

## Shape of the release

| Table | Rows | Grain |
|---|---|---|
| demand | 654,864 (37 stations in 2025, 40 in 2026) | station × hour |
| weather_obs | 105,120 | district × hour |
| weather_fcst | 104,976 (4,374 district-issues × 24 h) | district × issue × reference hour |
| stations / tariffs / holidays / events | 40 / 52 / 730 / 62 | per grain |

Fleet mean 88.1 kWh per station-hour; 57.7 GWh over two years. Mean
utilization 0.37–0.55 of installed capacity; 2.5 % of station-hours sit at
the capacity clip (peak saturation — physical, intended).

## Seasonality (what M03 baselines will assume)

- **Daily + weekly cycles by POI.** Office weekday demand peaks at the
  commute shoulders (170.3 kWh at 08 h and 18 h) and collapses on weekends
  (weekday mean 91.6 vs weekend 66.0). Retail peaks midday/afternoon and is
  the only POI busier on weekends (99.5 → 105.2). Residential peaks in the
  evening (87.6 kWh at 18 h). Highway is flat and high (130–183 kWh all
  day, weekend 137.0).
- **Annual cycle.** Mild summer shape through the annual factor; visible in
  the month-level rollups of the demand table.
- **Weather sensitivity.** Hours above 25 °C average 111.5 kWh/h vs 80.8
  kWh/h at 10–15 °C. Cold-hour means are lower only because cold hours are
  nights (composition, not physics) — segment by hour before fitting
  temperature response.

## Regime signatures (what M07 monitoring must detect)

- **Tariff step, 2026-04-01 (+0.15 €/kWh on 12 stations of D2+D5).**
  Naive before/after (4-week windows): stepped −4.74 % raw, control
  −3.70 % — window DiD only −1.08 % against a nominal full-ramp effect of
  −4.2 %. A same-seed paired regeneration with the surcharge removed
  confirms the generator applies the elasticity exactly (+4.24 % demand
  when the surcharge is absent, control +0.0000 %). The window DiD is
  attenuated by the 14-day ramp, group POI composition and event chance —
  naive before/after comparisons are biased here, which is why M03 fixes a
  paired-comparison protocol before any model is trained.
- **Heatwave, 2026-07-14→20 (+9.4 °C vs adjacent weeks).** Demand timing
  shifts as designed: 06–11 h ratio 0.875 vs adjacent weeks (mask 0.85),
  17–23 h ratio 1.175 (mask 1.15); the level is roughly conserved — the
  regime moves demand, it does not add it.
- **Cold start, 2026-10-01.** S038–S040 have their first row exactly on
  2026-10-01T00:00Z and average 58.9 kWh/h in their first 30 days vs fleet
  90.2 (smaller capacity draws) — the cold-start regime is present.

## Forecast side (for the point-in-time contract)

Day-ahead temperature forecasts: MAE 0.96 °C, bias +0.008 °C, sd 1.20 °C —
matching the designed AR(1) error (ρ = 0.6, σ = 1.2 °C). Realized weather
exists only for backtesting and monitoring; it is never readable at issue
time per the [feature contract](../../docs/feature-contract.md).
