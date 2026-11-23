"""E02 acceptance tests: dbt build over E01 raw + star-schema correctness.

The session fixture runs the full offline loop on a disposable DuckDB file:
generate → ingest (E01 CLI code) → `dbt source freshness` → `dbt build --target duckdb`.
Assertions then verify grain (zero fan-out), DST-aware revenue attribution,
fixture-exact FX rates, SMARD wholesale pricing, and the dim_date calendar.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb
import pytest

from charging_commerce import ingestion
from charging_commerce.generator import generate
from charging_commerce.open_data import load_fx_table

REPO = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO / "fixtures"
DBT_PROJECT = REPO / "dbt_project"

GENERATED_SOURCES = {"bnetza", "tariffs", "sessions"}


def _dbt(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("dbt")
    assert executable, "dbt executable not found in test environment"
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(  # noqa: S603 - fixed argv, test-local
        [
            executable,
            *args,
            "--project-dir",
            str(DBT_PROJECT),
            "--profiles-dir",
            str(DBT_PROJECT),
            "--target",
            "duckdb",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=merged_env,
        timeout=600,
    )


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory) -> Path:
    """Fresh raw warehouse + full dbt build; shared by all E02 tests."""
    tmp = tmp_path_factory.mktemp("e02")
    gen_dir, db_path, state_dir = tmp / "generated", tmp / "warehouse.duckdb", tmp / "state"
    generate(gen_dir, FIXTURES_DIR)
    for source, batch in (
        ("bnetza", "bnetza-snapshots-0001"),
        ("tariffs", "tariffs-t0t1t2-0001"),
        ("sessions", "charging-sim-window-0001"),
        ("smard", "smard-2025-10-2026-05-0001"),
        ("ecb", "ecb-2025-09-2026-05-0001"),
    ):
        name = ingestion.SOURCE_PAYLOADS[source]
        payload = gen_dir / name if source in GENERATED_SOURCES else FIXTURES_DIR / name
        ingestion.ingest_file(source, payload, batch, db_path, state_dir)

    env = {"CHARGING_COMMERCE_DUCKDB": str(db_path)}
    freshness = _dbt("source", "freshness", env=env)
    assert freshness.returncode == 0, freshness.stdout[-2000:] + freshness.stderr[-2000:]

    build = _dbt("build", env=env)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-4000:]
    return db_path


def _query(db_path: Path, sql: str):
    conn = duckdb.connect(str(db_path))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Grain / fan-out
# --------------------------------------------------------------------------


def test_zero_fanout_fact_matches_raw_sessions(warehouse: Path):
    (raw_sessions,) = _query(
        warehouse, "select count(distinct session_id) from raw.raw_charging_sessions"
    )
    (int_rows,) = _query(warehouse, "select count(*) from int.int_sessions_latest")
    (fct_rows,) = _query(warehouse, "select count(*) from mart.fct_charging_sessions")
    assert raw_sessions == int_rows == fct_rows
    assert fct_rows > 0


def test_daily_revenue_reconciles_to_fact(warehouse: Path):
    (fact_net,) = _query(warehouse, "select sum(net_amount_eur) from mart.fct_charging_sessions")
    (daily_rows, daily_net) = _query(
        warehouse,
        "select count(*), sum(net_amount_eur) from mart.fct_daily_revenue",
    )[0]
    assert daily_net == fact_net
    assert daily_rows > 0


def test_fx_rates_match_fixture_carry_forward(warehouse: Path):
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


def test_wholesale_cost_matches_smard_slot(warehouse: Path):
    """Recompute the §3.8 slot price and cost for every session from the fixture."""
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
        select session_id, session_started_at, energy_kwh, wholesale_eur_mwh, wholesale_cost_eur
        from mart.fct_charging_sessions
        """,
    )
    assert rows
    mismatched = []
    for session_id, started_at, energy, _model_price, model_cost in rows:
        expected_price = slot_for(started_at.strftime("%Y-%m-%dT%H:%M:%SZ"))
        expected_cost = (Decimal(str(energy)) * expected_price / 1000).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if Decimal(str(model_cost)) != expected_cost:
            mismatched.append((session_id, str(started_at), str(model_cost), str(expected_cost)))
    assert not mismatched, f"first mismatches: {mismatched[:5]}"


def test_dst_boundary_revenue_date(warehouse: Path):
    """DST-window sessions (2025-10-25 22:00Z..) attribute to the Berlin civil date."""
    rows = _query(
        warehouse,
        """
        select session_id, session_started_at, revenue_date
        from mart.fct_charging_sessions
        where session_id like 'S-DST-20251025-%'
        """,
    )
    assert rows, "expected DST-window sessions"
    for _, started_at, revenue_date in rows:
        assert started_at.strftime("%Y-%m-%d") == "2025-10-25"
        assert revenue_date.isoformat() == "2025-10-26"


def test_dim_date_calendar(warehouse: Path):
    rows = {
        day: (bool(is_weekend), bool(is_holiday))
        for day, is_weekend, is_holiday in _query(
            warehouse,
            """
            select date_day, is_weekend, is_de_holiday
            from mart.dim_date
            where date_day in (date '2025-10-03', date '2025-10-04', date '2026-04-06', date '2026-01-02')
            """,
        )
    }
    assert rows[date(2025, 10, 3)] == (False, True)  # Tag der Deutschen Einheit, Friday
    assert rows[date(2025, 10, 4)] == (True, False)  # Saturday
    assert rows[date(2026, 4, 6)] == (True, True)  # Easter Monday
    assert rows[date(2026, 1, 2)] == (True, False)  # Friday
    (days,) = _query(warehouse, "select count(*) from mart.dim_date")
    assert days == 243  # 2025-10-01..2026-05-31 inclusive


# --------------------------------------------------------------------------
# Negative drill: stale source must fail freshness
# --------------------------------------------------------------------------


def test_stale_source_fails_freshness(warehouse: Path, tmp_path):
    stale_db = tmp_path / "stale.duckdb"
    shutil.copy(warehouse, stale_db)
    conn = duckdb.connect(str(stale_db))
    try:
        conn.execute("update raw.raw_ecb_fx_rates set _ingested_at = now() - interval 72 hours")
    finally:
        conn.close()
    result = _dbt("source", "freshness", env={"CHARGING_COMMERCE_DUCKDB": str(stale_db)})
    assert result.returncode != 0, "stale (>48h) source must fail error_after freshness SLA"
