"""Acceptance check 2: the suite fails on each seeded corruption case."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from charging_forecast.validation import US_HOUR, validate_release

US = 1_000_000


def _check(results, name):
    return next(r for r in results if r.name == name)


def _ts(micros):
    return pa.scalar(micros, type=pa.timestamp("us", tz="UTC"))


def _shift_column(table, column, position, micros):
    """Shift one timestamp column by microseconds (int64 arithmetic)."""
    ints = table[column].cast(pa.int64())
    shifted = pc.add(ints, pa.scalar(micros, type=pa.int64())).cast(pa.timestamp("us", tz="UTC"))
    return table.set_column(position, column, shifted)


def test_clean_release_passes(tiny_release):
    release, cfg = tiny_release
    results = validate_release(release, cfg)
    failed = [r for r in results if not r.passed]
    assert not failed, [f"{r.name}: {r.detail}" for r in failed]


def test_mutated_tariff_step_date_fails(tiny_release):
    release, cfg = tiny_release
    path = release / "data" / "tariffs" / "part-0000.parquet"
    table = pq.read_table(path)
    s3 = table.filter(pc.equal(table["station_id"], "S003"))
    step_ts = pc.max(s3["effective_from"])  # the step row is the later one
    is_step = pc.and_(
        pc.equal(table["station_id"], "S003"),
        pc.equal(table["effective_from"], step_ts),
    )
    keep = pc.invert(is_step).to_pylist()
    ints = table["effective_from"].cast(pa.int64()).to_pylist()
    shifted = [v + US_HOUR if not k else v for k, v in zip(keep, ints, strict=False)]
    table = table.set_column(
        1,
        "effective_from",
        pa.array(shifted, type=pa.timestamp("us", tz="UTC")),
    )
    pq.write_table(table, path)

    results = validate_release(release, cfg)
    assert not _check(results, "regime_tariff_step").passed


def test_shifted_forecast_reference_fails(tiny_release):
    release, cfg = tiny_release
    path = sorted((release / "data" / "weather_fcst").rglob("*.parquet"))[0]
    table = pq.read_table(path)
    table = _shift_column(table, "reference_hour_utc", 2, 2 * US_HOUR)
    pq.write_table(table, path)

    results = validate_release(release, cfg)
    assert not _check(results, "forecast_integrity").passed


def test_dropped_station_hours_fail(tiny_release):
    release, cfg = tiny_release
    path = release / "data" / "demand" / "year=2025" / "part-0000.parquet"
    table = pq.read_table(path)
    start = pc.min(table["hour_utc"]).cast(pa.int64()).as_py()
    in_window = pc.and_(
        pc.greater(table["hour_utc"], _ts(start + 3 * US_HOUR)),
        pc.less(table["hour_utc"], _ts(start + 6 * US_HOUR)),
    )
    drop = pc.and_(pc.equal(table["station_id"], "S001"), in_window)
    pq.write_table(table.filter(pc.invert(drop)), path)

    results = validate_release(release, cfg)
    assert not _check(results, "continuity_demand").passed
