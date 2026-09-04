# Test fixtures (not production data paths)

| File | Purpose |
|------|---------|
| `alpha_vantage_ewg_daily.json` | Compact Alpha Vantage sample (~100 days) for unit tests. |
| `ewg_historical_bootstrap.json` | Long EWG history in Alpha Vantage JSON shape (Yahoo Finance bootstrap). Used for CI `DAX_FIXTURE_PATH` and production bootstrap merge. |

Production ingestion merges `ewg_historical_bootstrap.json` with live Alpha Vantage `compact` pulls (live wins on overlap). Set `DAX_FIXTURE_PATH` to skip the live API entirely (CI).
