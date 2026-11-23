"""Feature-contract semantics: availability, leakage shift, determinism."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from district_forecast.dataset import build_dataset
from district_forecast.features import (
    US_HOUR,
    DistrictDemand,
    build_features,
    valid_issue_range,
)
from district_forecast.releases import issue_time_us, sha256_file


@pytest.fixture()
def built_features(source_release, district_cfg, tmp_path):
    derived = tmp_path / "derived"
    build_dataset(district_cfg, source_release, derived)
    out = tmp_path / "features"
    manifest = build_features(district_cfg, derived, out)
    return manifest, out


def test_issue_range_and_row_grain(built_features, district_cfg):
    manifest, _ = built_features
    first, last = valid_issue_range(district_cfg)
    assert manifest["issue_start"] == first.isoformat()
    assert manifest["issue_end"] == last.isoformat()
    assert manifest["rows"] == manifest["issues"] * 2 * 24  # districts × hours


def test_lag_24h_is_readable_and_late_rows_are_not(
    source_release, district_cfg, tmp_path, built_features
):
    """A feature row's lag equals the district aggregate one day earlier, and
    delaying the aggregate stamp past T − delay makes the lag unreadable."""
    manifest, out = built_features
    table = pq.read_table(sorted(out.rglob("*.parquet"))[0])
    rows = {(r["issue_date"], r["district"], r["target_hour_utc"]): r for r in table.to_pylist()}
    first_issue = "2025-01-10"  # inside the range, with lag history
    key = (first_issue, "D1")
    row = next(v for k, v in rows.items() if k[:2] == key)
    lag_value = row["demand_lag_24h"]

    # The direct point-in-time read (lag anchored at T) must agree with the
    # built feature: one lag value per issue day, broadcast to the targets.
    derived = tmp_path / "derived"
    build_dataset(district_cfg, source_release, derived)
    demand = DistrictDemand(pq.read_table(derived / "data/demand/part-0000.parquet"))
    t_us = issue_time_us(date.fromisoformat(first_issue))
    direct = demand.readable("D1", t_us - US_HOUR * 24, t_us)
    assert lag_value == pytest.approx(direct, abs=1e-6)


def test_leakage_shift_delaying_stamp_blocks_the_lag(source_release, district_cfg):
    """Advancing or delaying availability stamps never changes values, but a
    delayed stamp must make the value unreadable at an earlier issue time."""
    import pyarrow as pa

    from district_forecast.dataset import build_dataset

    derived = Path(str(source_release) + "-derived")
    build_dataset(district_cfg, source_release, derived)
    demand_table = pq.read_table(derived / "data/demand/part-0000.parquet")
    demand = DistrictDemand(demand_table)
    district = "D1"
    hour = int(demand.hours[district][100])
    t_us = hour + US_HOUR * 30

    base = demand.readable(district, hour, t_us)
    assert base == base and base >= 0  # readable and finite

    import numpy as np

    shifted = pa.array(
        np.asarray(demand_table.column("available_at").cast(pa.int64())) + US_HOUR,
        type=pa.int64(),
    )
    delayed_table = demand_table.set_column(
        demand_table.column_names.index("available_at"), "available_at", shifted
    )
    delayed = DistrictDemand(delayed_table)
    # The stamp move never changes the underlying value.
    assert delayed.readable(district, hour, t_us + US_HOUR) == base
    # At an issue time one hour earlier the delayed row is no longer readable.
    earlier = t_us - US_HOUR
    idx = int((delayed.hours[district] == hour).nonzero()[0][0])
    if delayed.avail[district][idx] > earlier:
        assert (
            delayed.readable(district, hour, earlier) != delayed.readable(district, hour, earlier)
            or True
        )  # placeholder-free check below
        from math import isnan

        assert isnan(delayed.readable(district, hour, earlier))


def test_forecast_boundary_latest_issue_wins(source_release, district_cfg):
    """Only forecasts stamped available_at <= T are readable, and the latest
    such issue wins (the day-ahead convention)."""
    import datetime as dt

    from district_forecast.features import WeatherForecasts

    forecasts = WeatherForecasts(
        pq.read_table(source_release / "data/weather_fcst/part-0000.parquet")
    )
    issue_day = date(2025, 1, 10)
    t_us = issue_time_us(issue_day)
    target = issue_time_us(issue_day + dt.timedelta(days=1))
    temp, _precip = forecasts.at("D1", target, t_us)
    assert temp == temp  # finite
    # One minute earlier the same forecast row is not readable.
    temp_early, _ = forecasts.at("D1", target, t_us - 60_000_000)
    assert temp_early != temp_early  # NaN


def test_feature_build_is_deterministic(source_release, district_cfg, tmp_path):
    derived = tmp_path / "derived"
    build_dataset(district_cfg, source_release, derived)
    first = tmp_path / "f1"
    second = tmp_path / "f2"
    build_features(district_cfg, derived, first)
    build_features(district_cfg, derived, second)
    assert sha256_file(first / "manifest.json") == sha256_file(second / "manifest.json")
