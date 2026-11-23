# E03 · Testing, data contracts and versioning

**Status:** implemented (acceptance evidence recorded, pending owner review) · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [Data contract](../docs/data-contract.md) · [Evidence](evidence/e03-acceptance.md)

Implement a complete `dbt` testing pyramid and enforced data contracts so breaking schema changes and subtle SQL regressions are caught at build time before downstream consumers see them.

## Deliverables

- Schema generic tests (`unique`, `not_null`, `relationships`, `accepted_values`) + custom generic test (e.g., `positive_monetary_or_refund`) + singular revenue-conservation test reconciling Raw totals against `fct_charging_sessions` + `raw_quarantine`.
- Native `dbt` `unit_tests` (mock row inputs) verifying DST boundary timestamps, multi-currency EUR conversion across missing holiday FX dates, and refund sign handling.
- Enforced `contract: {enforced: true}` on `marts` models plus model versioning (`fct_daily_revenue` `v1 → v2` non-breaking/deprecation drill).

## Acceptance

1. All generic, custom, singular conservation, and native `unit_tests` pass under `dbt build`.
2. Intentionally removing a contracted column or changing a column data type fails `dbt build` immediately at the contract boundary without overwriting the target table.
3. Both `fct_daily_revenue_v1` and `fct_daily_revenue_v2` coexist cleanly with documented deprecation metadata.
