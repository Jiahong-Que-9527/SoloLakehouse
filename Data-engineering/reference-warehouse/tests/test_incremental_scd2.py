"""E04 acceptance tests: SCD2 history, point-in-time joins, incremental merge.

Covers the E04 acceptance criteria: SCD2 interval history across t0/t1/t2,
point-in-time station/tariff joins, incremental idempotence, late-settlement
whole-row replacement, exact incremental vs --full-refresh parity, and the
bounded backfill vars.
"""

from __future__ import annotations

import shutil
from decimal import Decimal

import duckdb
from conftest import _dbt, _query, _scalar

T0, T1, T2 = "2025-09-15", "2026-01-15", "2026-05-15"

LATE_EVENT_SQL = """
insert into raw.raw_charging_sessions
select session_id, 2, station_id, tariff_id, country_code, currency_code,
       session_started_at, session_ended_at, now(),
       energy_kwh * 0.5, gross_amount_local * 0.5, 'late_adjustment',
       'late-0001', now(), 'charging_sim', 'hash-late-e04'
from raw.raw_charging_sessions
where event_seq = 1 and event_type = 'charge'
"""


def test_scd2_history_and_intervals(warehouse):
    """Changed stations/tariffs have multiple versions chained by snapshot-date
    intervals; every dbt_valid_from is a raw snapshot date."""
    (station_versions,) = _query(warehouse, "select count(*) from mart.dim_stations_scd2")[0]
    (current_stations,) = _query(warehouse, "select count(*) from mart.dim_stations")[0]
    assert current_stations == 3233
    assert station_versions > current_stations, "expected upgraded stations to gain versions"

    multi = _query(
        warehouse,
        """
        select station_id
        from mart.dim_stations_scd2
        group by station_id
        having count(*) > 1
        limit 3
        """,
    )
    assert multi, "expected at least one station with version history"

    for (station_id,) in multi:
        intervals = _query(
            warehouse,
            f"""
            select dbt_valid_from, dbt_valid_to
            from mart.dim_stations_scd2
            where station_id = '{station_id}'
            order by dbt_valid_from
            """,
        )
        # intervals chain: each version's valid_to equals the next version's valid_from
        for (_, end_a), (start_b, _) in zip(intervals, intervals[1:], strict=False):
            assert end_a == start_b, f"gap/overlap for {station_id}: {end_a} vs {start_b}"
        starts = {start.isoformat() for start, _ in intervals}
        assert starts <= {T0, T1, T2}, f"unexpected dbt_valid_from for {station_id}: {starts}"


def test_point_in_time_station_join(warehouse):
    """Sessions before a t1 upgrade join to the old (lower-power) version."""
    upgraded = _query(
        warehouse,
        f"""
        select d.station_id,
            min(case when d.dbt_valid_from = date '{T0}' then d.nominal_power_kw end) as power_old,
            min(case when d.dbt_valid_from = date '{T1}' then d.nominal_power_kw end) as power_new
        from mart.dim_stations_scd2 as d
        where d.station_id in (
            select station_id from int.int_sessions_enriched_fx
            where session_started_at < date '{T1}'
        )
        group by d.station_id
        having count(*) > 1
            and min(case when d.dbt_valid_from = date '{T0}' then d.nominal_power_kw end)
                < min(case when d.dbt_valid_from = date '{T1}' then d.nominal_power_kw end)
        limit 1
        """,
    )
    assert upgraded, "expected at least one power-upgraded station"
    station_id, power_old, power_new = upgraded[0]

    before = _query(
        warehouse,
        f"""
        select d.nominal_power_kw
        from mart.fct_charging_sessions as f
        join int.int_sessions_enriched_fx as e
            on e.session_id = f.session_id
        join mart.dim_stations_scd2 as d
            on d.dbt_scd_id = f.station_sk
        where d.station_id = '{station_id}'
          and e.session_started_at < date '{T1}'
        limit 1
        """,
    )
    assert before, "expected a pre-t1 session for the upgraded station"
    assert Decimal(str(before[0][0])) == power_old, "pre-t1 session must join the old version"

    after = _query(
        warehouse,
        f"""
        select d.nominal_power_kw
        from mart.fct_charging_sessions as f
        join int.int_sessions_enriched_fx as e
            on e.session_id = f.session_id
        join mart.dim_stations_scd2 as d
            on d.dbt_scd_id = f.station_sk
        where d.station_id = '{station_id}'
          and e.session_started_at >= date '{T1}'
        limit 1
        """,
    )
    assert after, "expected a post-t1 session for the upgraded station"
    assert Decimal(str(after[0][0])) == power_new, "post-t1 session must join the new version"


def test_incremental_rerun_is_idempotent(warehouse):
    """Re-running the incremental merge with no new data changes nothing."""
    before_count = _scalar(warehouse, "select count(*) from mart.fct_charging_sessions")
    before_net = _scalar(warehouse, "select sum(net_amount_eur) from mart.fct_charging_sessions")

    result = _dbt(
        "run",
        "--select",
        "fct_charging_sessions",
        env={"CHARGING_COMMERCE_DUCKDB": str(warehouse)},
    )
    assert result.returncode == 0, result.stdout[-2000:]

    after_count = _scalar(warehouse, "select count(*) from mart.fct_charging_sessions")
    after_net = _scalar(warehouse, "select sum(net_amount_eur) from mart.fct_charging_sessions")
    assert (after_count, after_net) == (before_count, before_net)


def test_late_settlement_replaces_session_row(warehouse, tmp_path):
    """A late event_seq=2 settlement (settled now, caught by the 48h lookback)
    replaces the session's stored row wholesale — count unchanged, values updated."""
    db_inc = tmp_path / "late.duckdb"
    shutil.copy(warehouse, db_inc)
    victim = _scalar(
        db_inc,
        "select session_id from mart.fct_charging_sessions where event_type = 'charge' limit 1",
    )
    conn = duckdb.connect(str(db_inc))
    try:
        conn.execute(LATE_EVENT_SQL + " and session_id = ?", [victim])
    finally:
        conn.close()

    run = _dbt(
        "run",
        "--select",
        "fct_charging_sessions",
        env={"CHARGING_COMMERCE_DUCKDB": str(db_inc)},
    )
    assert run.returncode == 0, run.stdout[-2000:]

    after_count = _scalar(db_inc, "select count(*) from mart.fct_charging_sessions")
    base_count = _scalar(warehouse, "select count(*) from mart.fct_charging_sessions")
    assert after_count == base_count, "merge must replace the session row, never add one"
    updated = _query(
        db_inc,
        f"select event_type, extract(year from settled_at) from mart.fct_charging_sessions"
        f" where session_id = '{victim}'",
    )[0]
    assert updated[0] == "late_adjustment"
    assert int(updated[1]) >= 2026, "stored row now reflects the late event's settled_at"


def test_full_refresh_parity(warehouse, tmp_path):
    """After a late arrival, the incremental result matches a clean --full-refresh
    run row-for-row (contract §3.5)."""
    late_state = tmp_path / "inc.duckdb"
    shutil.copy(warehouse, late_state)
    conn = duckdb.connect(str(late_state))
    try:
        conn.execute(LATE_EVENT_SQL + " limit 1")
    finally:
        conn.close()

    run_inc = _dbt(
        "run",
        "--select",
        "fct_charging_sessions",
        env={"CHARGING_COMMERCE_DUCKDB": str(late_state)},
    )
    assert run_inc.returncode == 0, run_inc.stdout[-2000:]

    full_state = tmp_path / "full.duckdb"
    shutil.copy(late_state, full_state)
    run_full = _dbt(
        "run",
        "--full-refresh",
        "--select",
        "fct_charging_sessions",
        env={"CHARGING_COMMERCE_DUCKDB": str(full_state)},
    )
    assert run_full.returncode == 0, run_full.stdout[-2000:]

    conn = duckdb.connect(str(late_state))
    try:
        conn.execute(f"attach '{full_state}' as full_db")
        diff = conn.execute(
            """
            (select * from mart.fct_charging_sessions
             except all
             select * from full_db.mart.fct_charging_sessions)
            union all
            (select * from full_db.mart.fct_charging_sessions
             except all
             select * from mart.fct_charging_sessions)
            """
        ).fetchall()
    finally:
        conn.close()
    assert diff == [], f"incremental and full-refresh diverged: {diff[:5]}"


def test_backfill_bounded_range(warehouse, tmp_path):
    """Deleting a settled_at range and re-running with bounded backfill vars
    restores the exact rows (design §5.4)."""
    db_bf = tmp_path / "backfill.duckdb"
    shutil.copy(warehouse, db_bf)
    before_count = _scalar(db_bf, "select count(*) from mart.fct_charging_sessions")
    before_sum = _scalar(db_bf, "select sum(net_amount_eur) from mart.fct_charging_sessions")

    conn = duckdb.connect(str(db_bf))
    try:
        conn.execute(
            "delete from mart.fct_charging_sessions where settled_at < timestamp '2025-11-01'"
        )
    finally:
        conn.close()
    deleted = before_count - _scalar(db_bf, "select count(*) from mart.fct_charging_sessions")
    assert deleted > 0, "expected the drill to delete a non-empty range"

    run = _dbt(
        "run",
        "--select",
        "fct_charging_sessions",
        "--vars",
        '{"backfill_start": "2025-01-01", "backfill_end": "2025-11-01"}',
        env={"CHARGING_COMMERCE_DUCKDB": str(db_bf)},
    )
    assert run.returncode == 0, run.stdout[-2000:]

    after_count = _scalar(db_bf, "select count(*) from mart.fct_charging_sessions")
    after_sum = _scalar(db_bf, "select sum(net_amount_eur) from mart.fct_charging_sessions")
    assert after_count == before_count, "backfill must restore the deleted rows"
    assert after_sum == before_sum, "backfill must restore identical revenue"
