# Implementation plan: E03 · Testing, data contracts and versioning

**Status:** planned. [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md)

## First delivery

Add custom generic tests, raw-to-mart revenue conservation singular tests, native dbt `unit_tests`, enforced `contract` definitions on all marts, and `fct_daily_revenue` `v1`/`v2` model versioning, verified by automated negative tests.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/dbt_project/tests/generic/test_non_negative_unless_refund.sql`
- `Data-engineering/reference-warehouse/dbt_project/tests/singular/assert_revenue_conservation.sql`
- `Data-engineering/reference-warehouse/dbt_project/models/marts/fct_daily_revenue_v1.sql`
- `Data-engineering/reference-warehouse/dbt_project/models/marts/fct_daily_revenue_v2.sql`
- `Data-engineering/reference-warehouse/dbt_project/models/marts/schema.yml` (enforced contracts, constraints, versions, `unit_tests`)
- `Data-engineering/reference-warehouse/tests/test_contracts.py`
- `Data-engineering/03-testing-contracts-versioning/evidence/e03-acceptance.md`

## Implementation sequence

1. **Custom generic & conservation tests:** Implement `test_non_negative_unless_refund.sql` and `assert_revenue_conservation.sql` verifying `SUM(valid_raw_eur) == SUM(fct_charging_sessions.net_amount_eur)` (`0.00` tolerance).
2. **Native dbt `unit_tests`:** Add inline mock-row `unit_tests` in `schema.yml` covering (a) CET/CEST DST date attribution, (b) weekend/holiday ECB FX carry-forward, and (c) refund net-margin computation.
3. **Enforced contracts:** Add `config: {contract: {enforced: true}}` plus explicit column `data_type` and `not_null` constraints on `dim_date`, `dim_stations`, `dim_tariffs`, `fct_charging_sessions`, and `fct_daily_revenue`.
4. **Model versioning (`v1 -> v2`):** Split `fct_daily_revenue` into `_v1.sql` and `_v2.sql` (adding wholesale cost & gross margin in `v2`), configure `versions:` and `deprecation_date` on `v1`, and verify both relations build.
5. **Contract-breach negative test (`test_contracts.py`):** Automate a temporary copy/override drill proving that dropping or retyping a contracted column fails `dbt build` without replacing the previous table.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse
uv run --locked sqlfluff lint dbt_project/models dbt_project/tests
uv run --locked dbt test --select test_type:unit --project-dir dbt_project --profiles-dir dbt_project --target duckdb
uv run --locked dbt build --project-dir dbt_project --profiles-dir dbt_project --target duckdb
uv run --locked pytest tests/test_contracts.py -v
```

**Negative drills:**
- Drop a contracted column in a disposable dbt test directory and verify `dbt build` fails at contract enforcement.
- Inject a 0.01 EUR drift in a disposable fixture and verify `assert_revenue_conservation` fails.

## Acceptance evidence

Record in `03-testing-contracts-versioning/evidence/e03-acceptance.md`: test counts by category (unit, generic, custom, singular), exact contract-failure error output, conservation query result (`0.00` difference), and `v1` vs `v2` schema diff.
