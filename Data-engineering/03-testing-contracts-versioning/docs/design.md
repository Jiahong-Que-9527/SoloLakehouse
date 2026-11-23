# Design: E03 · Testing, data contracts and versioning

**E03 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md)

Harden the E02 star schema with a four-layer dbt quality gate: built-in & custom generic tests, singular revenue-conservation tests, native `dbt` `unit_tests` (mock row inputs), enforced `contract: {enforced: true}`, and versioned marts (`fct_daily_revenue` `v1` and `v2`).

## 1. Decisions

| Topic | Decision |
|---|---|
| Test pyramid | Generic (`unique`/`not_null`/`relationships`/`accepted_values`) + custom generic + singular conservation + native `unit_tests` |
| Revenue conservation | Singular test `assert_revenue_conservation.sql` (`ABS(raw_net - mart_net) == 0.00` EUR) |
| Native unit tests | `dbt` YAML `unit_tests` testing the `int_sessions_latest` latest-event reduction (incl. tie-breaks), DST clock shifts, ECB holiday carry-forward, and refund signs without full ingestion |
| Data contracts | `config: {contract: {enforced: true}}` with explicit `data_type` + `constraints` on all `marts` models |
| Model versioning | `fct_daily_revenue` `v1` (core revenue) + `v2` (adds `wholesale_cost_eur`, `gross_margin_eur`), `latest_version: 2`, `deprecation_date` on `v1` |

## 2. Scope boundary

In scope: generic tests, custom generic tests, singular conservation tests, native dbt `unit_tests`, enforced contracts on `marts`, `fct_daily_revenue` `v1 -> v2` versioning, and contract-violation failure tests.

Out of scope: incremental `merge` & `dbt snapshot` (`E04`), `Slim CI` (`E05`), and BigQuery deployment (`E06`).

## 3. Architecture

```text
  [Native unit_tests (mock rows)] ---> verifies SQL logic (DST, FX gap, refunds)
  [Model Contracts (enforced)]   ---> blocks missing/mismatched columns at build time
  [Generic + Singular Tests]     ---> validates grain, FK integrity, 0.00 EUR conservation
  [Model Versions v1 -> v2]      ---> dual-version coexistence with deprecation metadata
```

## 4. Contracts and configuration

- Exact contracted columns and types for `fct_charging_sessions`, `fct_daily_revenue_v1`, and `fct_daily_revenue_v2` match [data-contract.md](../../docs/data-contract.md).
- Custom generic test `test_non_negative_unless_refund` lives in `dbt_project/tests/generic/`.
- Singular tests live in `dbt_project/tests/singular/`: `assert_revenue_conservation.sql` and `assert_no_session_outside_price_window.sql` (every `session_started_at` falls inside the locked SMARD price window — contract §3.8's boundary fallback must never be silently exercised).

## 5. Behaviour and edge cases

1. Changing a column type (e.g., `DECIMAL` -> `VARCHAR`) or dropping a contracted column on `fct_daily_revenue` aborts `dbt build` before replacing the existing mart table.
2. A single-cent mismatch between valid raw settlements and `fct_charging_sessions.net_amount_eur` fails `assert_revenue_conservation`.
3. `unit_tests` run deterministically in isolation against inline fixture rows in `schema.yml`.

## 6. Delivery and cost

Runs completely offline in `dbt-duckdb` (`€0`).

## 7. Acceptance criteria

1. `dbt build --target duckdb` passes all generic, custom, singular conservation, and native `unit_tests`.
2. Contract-breach negative test fails visibly and preserves the prior valid table.
3. Both `fct_daily_revenue_v1` and `fct_daily_revenue_v2` materialize and query cleanly.

## 8. Handoff

`E04` converts `fct_charging_sessions` to incremental `merge` while keeping every E03 contract and conservation test green.
