# Glossary

<!-- [ZCode·2026-11-23] Domain and tooling vocabulary for reviewers outside the EV-charging industry. -->

Domain terms used across the specs, with the German source terms where the open data uses them.

## Domain (EV charging & energy markets)

| Term | Meaning |
|---|---|
| **BNetzA** | Bundesnetzagentur — the German Federal Network Agency; publishes the charging-station registry and the SMARD market data. |
| **Ladesäulenregister** | BNetzA's public register of charging stations (`Ladesäule` = charging point): operator, location, power, commissioning date. Licensed `CC BY 4.0`. |
| **SMARD** | BNetzA's electricity market data platform: day-ahead wholesale prices and grid load for the `DE-LU` bidding zone. |
| **DE-LU** | The German–Luxembourg electricity bidding zone used by SMARD price data. |
| **ECB Data Portal** | European Central Bank reference rates; quotes `1 EUR` as base (e.g. `EUR/CHF = 0.941` means `1 EUR = 0.941 CHF`). No publication on weekends/TARGET2 holidays. |
| **TARGET2** | The Eurosystem's settlement system; its holiday calendar is why ECB FX rates have gaps. |
| **CPO** | Charge Point Operator — runs the physical charging stations (`Betreiber`). |
| **eMSP** | e-Mobility Service Provider — sells charging to end customers; their customers roam onto foreign CPO networks. |
| **e-roaming / clearing hub** | The arrangement letting an eMSP's customer charge on another operator's station; a clearing hub brokers and settles these sessions. |
| **Roaming surcharge / settlement fee** | The fixed fee billed with a roaming session; the tariff table holds the list price, the settlement record holds the billed amount (see [data contract §1.5](data-contract.md)). |
| **Billing market** | The `country_code`/`currency_code` pair of a session (`DE`→`EUR`, `CH`→`CHF`, `PL`→`PLN`) — the market the customer is billed in, not the station's location. |

## Modeling & DataOps

| Term | Meaning |
|---|---|
| **Kimball star schema** | Dimensional model with fact tables (events, e.g. charging sessions) joined to denormalized dimension tables (stations, tariffs, date). |
| **SCD Type 2** | Slowly Changing Dimension strategy keeping full attribute history via validity intervals (`dbt_valid_from`/`dbt_valid_to`). |
| **Point-in-time join** | Joining an event to the dimension row whose validity interval contains the event time, so history never shifts retroactively. |
| **dbt** | SQL-first transformation tool: `staging → intermediate → marts` models, tests, docs, and contracts as code. |
| **Data contract** | Enforced column-level schema (types, nullability, constraints) that fails the build before bad data replaces a good table. |
| **Model versioning** | dbt feature letting `fct_daily_revenue` `v1` and `v2` coexist with a deprecation date on the old version. |
| **Slim CI** | Running only `state:modified+` models (plus tests) in CI by comparing against a baseline `manifest.json`, deferring unchanged models to production state. |
| **Source freshness** | dbt check comparing `_ingested_at` age against warn/error SLAs (here 24h/48h, exercised by injected timestamps on the offline track). |
| **Quarantine** | The `raw_quarantine` table routing malformed/drifted records instead of letting them corrupt raw tables (see [data contract §1.7](data-contract.md)). |
| **Revenue conservation** | The invariant that mart net revenue equals the recomputation from valid raw events, cent-exact, with quarantined rows accounted separately (see [data contract §3.1](data-contract.md)). |
| **FinOps** | Cloud cost engineering; here, recording `INFORMATION_SCHEMA.JOBS` `bytes_billed` receipts to prove partitioning savings and €0 Free-Tier compliance. |
| **Authorized view** | A BigQuery view in a separate dataset that queries protected data on the consumer's behalf, so analysts never get raw/staging access. |
| **`require_partition_filter`** | BigQuery table flag forcing queries to prune partitions — unfiltered scans fail fast instead of silently burning quota. |
| **CET/CEST (DST)** | Central European time and its summer clock shifts; the generator injects sessions across transition nights to catch timezone-attribution bugs. |
