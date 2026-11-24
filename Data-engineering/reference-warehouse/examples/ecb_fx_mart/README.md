# ECB Daily FX Summary Mart (second workload, onboarded via the E08 template)

A deliberately small second domain: a daily FX summary mart over the ECB
reference-rate slice, built **entirely from `template/`** without touching
any `charging_commerce` model. It proves the template's vertical slice:
seed → typed staging → contract-enforced mart → tests, all offline on
DuckDB.

## Provenance

- Seed: `seeds/ecb_fx_rates.csv` — a copy of the primary warehouse's locked
  fixture `fixtures/ecb_fx_slice.csv` (507 daily observations, three pairs
  `EUR/CHF`, `EUR/PLN`, `EUR/USD`, 2025-09-01 → 2026-04-30). The copy is
  deliberate: the second workload must be runnable and testable even if the
  primary's fixtures move, and a *domain owns its inputs*.
- Mart: `fct_fx_rates_daily` at grain `(rate_date, currency_pair)` with the
  rate, the previous day's rate and the day-over-day change.

## Build & verify (from `reference-warehouse/`)

```bash
uv run --locked dbt build \
    --project-dir examples/ecb_fx_mart/dbt_project \
    --profiles-dir examples/ecb_fx_mart/dbt_project \
    --target duckdb
uv run --locked sqlfluff lint examples/ecb_fx_mart/dbt_project/models \
    --config examples/ecb_fx_mart/.sqlfluff
```

The DuckDB file lands at `examples/ecb_fx_mart/dbt_project/data/` (gitignored).

## Onboarding friction notes (measured, E08 evidence)

Recorded while instantiating from `template/` — see
`08-observability-template/evidence/e08-acceptance.md` for timings and the
full list. Headlines: two renames in `dbt_project.yml`, the seed drop, one
nullable-column contract subtlety (`day_over_day_change` is legitimately
null on each pair's first observation, so the enforced contract declares the
type but not a `not_null` constraint), and one macro lesson: without
`generate_schema_name` dbt concatenates the profile schema (`main_stg`) —
the template's verbatim-schema macro must be copied or schemas read as
`main_stg` / `main_mart`.
