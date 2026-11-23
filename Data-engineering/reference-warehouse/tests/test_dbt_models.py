"""E02 acceptance tests: dbt build over E01 raw + star-schema correctness.

Assertions verify grain (zero fan-out), DST-aware revenue attribution,
fixture-exact FX rates, SMARD wholesale pricing (incl. the §2 refund sign),
and the dim_date calendar. Fixtures and helpers live in conftest.py.
"""

from __future__ import annotations

import csv
import shutil
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import duckdb
from conftest import FIXTURES_DIR, _dbt, _query, _scalar

from charging_commerce.open_data import load_fx_table


def test_zero_fanout_fact_matches_raw_sessions(warehouse):
    raw_sessions = _scalar(
        warehouse, "select count(distinct session_id) from raw.raw_charging_sessions"
    )
    int_rows = _scalar(warehouse, "select count(*) from int.int_sessions_latest")
    fct_rows = _scalar(warehouse, "select count(*) from mart.fct_charging_sessions")
    assert raw_sessions == int_rows == fct_rows
    assert fct_rows > 0


def test_daily_revenue_reconciles_to_fact(warehouse):
    fact_net = _scalar(warehouse, "select sum(net_amount_eur) from mart.fct_charging_sessions")
    daily_net = _scalar(warehouse, "select sum(net_amount_eur) from mart.fct_daily_revenue_v2")
    (daily_rows,) = _query(warehouse, "select count(*) from mart.fct_daily_revenue_v2")[0]
    assert daily_net == fact_net, "daily grain must reconcile to the fact, cent-exact"
    assert daily_rows > 0


def test_fx_rates_match_fixture_carry_forward(warehouse):
    """Every non-EUR fact row must use the fixture ECB rate in force at revenue_date."""
    fx_table = load_fx_table(FIXTURES_DIR)
    rows = _query(
        warehouse,
        """
        select session_id, currency_code, revenue_date, fx_rate_to_eur, fx_rate_status
        from mart.fct_charging_sessions
        where currency_code != 'EUR'
        """,
    )
    assert rows, "expected roaming sessions"
    mismatched = []
    for session_id, currency, revenue_date, rate, status in rows:
        pair = f"EUR/{currency}"
        observed = max(d for d in fx_table[pair] if d <= revenue_date.isoformat())
        expected_status = "observed" if observed == revenue_date.isoformat() else "carried_forward"
        expected_rate = Decimal(str(fx_table[pair][observed])).quantize(Decimal("0.000001"))
        if Decimal(str(rate)) != expected_rate or status != expected_status:
            mismatched.append((session_id, currency, str(revenue_date), rate, status))
    assert not mismatched, f"first mismatches: {mismatched[:5]}"


def test_wholesale_cost_matches_smard_slot(warehouse):
    """Recompute the §3.8 slot price and cost for every session from the fixture.

    Contract §2: wholesale_cost_eur carries the event's sign — negative for refunds.
    """
    prices = {
        row["timestamp_utc"]: Decimal(row["wholesale_eur_mwh"])
        for row in csv.DictReader((FIXTURES_DIR / "smard_prices_slice.csv").open())
    }
    slots = sorted(prices)
    first_slot = slots[0]

    def slot_for(moment: str) -> Decimal:
        candidates = [s for s in slots if s <= moment]
        return prices[candidates[-1]] if candidates else prices[first_slot]

    rows = _query(
        warehouse,
        """
        select session_id, session_started_at, energy_kwh, event_type, wholesale_cost_eur
        from int.int_sessions_wholesale_cost
        """,
    )
    assert rows
    mismatched = []
    for session_id, started_at, energy, event_type, model_cost in rows:
        expected_price = slot_for(started_at.strftime("%Y-%m-%dT%H:%M:%SZ"))
        magnitude = (Decimal(str(energy)) * expected_price / 1000).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        expected_cost = -magnitude if event_type == "refund" else magnitude
        if Decimal(str(model_cost)) != expected_cost:
            mismatched.append((session_id, str(started_at), str(model_cost), str(expected_cost)))
    assert not mismatched, f"first mismatches: {mismatched[:5]}"


def test_dst_boundary_revenue_date(warehouse):
    """DST-window sessions (2025-10-25 22:00Z..) attribute to the Berlin civil date."""
    rows = _query(
        warehouse,
        """
        select session_id, session_started_at, revenue_date
        from int.int_sessions_enriched_fx
        where session_id like 'S-DST-20251025-%'
        """,
    )
    assert rows, "expected DST-window sessions"
    for _, started_at, revenue_date in rows:
        # Window spans 2025-10-25 22:00Z .. 2025-10-26 02:00Z — the CET→CEST night.
        # DuckDB returns naive-UTC timestamps, so compare against naive bounds.
        assert started_at >= datetime(2025, 10, 25, 22, 0)
        assert started_at <= datetime(2025, 10, 26, 2, 0)
        # Every such session attributes to the Berlin civil date 2025-10-26.
        assert revenue_date.isoformat() == "2025-10-26"


def test_dim_date_calendar(warehouse):
    rows = {
        day: (bool(is_weekend), bool(is_holiday))
        for day, is_weekend, is_holiday in _query(
            warehouse,
            """
            select date_day, is_weekend, is_de_holiday
            from mart.dim_date
            where date_day in (
                date '2025-10-03', date '2025-10-04', date '2026-04-06', date '2026-01-02'
            )
            """,
        )
    }
    assert rows[date(2025, 10, 3)] == (False, True)  # Tag der Deutschen Einheit, Friday
    assert rows[date(2025, 10, 4)] == (True, False)  # Saturday
    assert rows[date(2026, 4, 6)] == (False, True)  # Easter Monday — a Monday, not a weekend
    assert rows[date(2026, 1, 2)] == (False, False)  # Friday — a weekday
    days = _scalar(warehouse, "select count(*) from mart.dim_date")
    assert days == 243  # 2025-10-01..2026-05-31 inclusive


# --------------------------------------------------------------------------
# Negative drill: stale source must fail freshness
# --------------------------------------------------------------------------


def test_stale_source_fails_freshness(warehouse, tmp_path):
    stale_db = tmp_path / "stale.duckdb"
    shutil.copy(warehouse, stale_db)
    conn = duckdb.connect(str(stale_db))
    try:
        conn.execute("update raw.raw_ecb_fx_rates set _ingested_at = now() - interval 72 hours")
    finally:
        conn.close()
    result = _dbt("source", "freshness", env={"CHARGING_COMMERCE_DUCKDB": str(stale_db)})
    assert result.returncode != 0, "stale (>48h) source must fail error_after freshness SLA"
