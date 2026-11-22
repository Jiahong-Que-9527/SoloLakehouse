"""Feature content tests: identity, lag math, joins and schedules (M02)."""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest
import yaml

from charging_forecast.contract import issue_time_utc, load_config
from charging_forecast.features import US_HOUR, FeatureBuilder
from charging_forecast.generator import ChargingGenerator
from charging_forecast.validation import read_table
from conftest import TINY_CONFIG, publish_manifest, write_config

ISSUE = date(2025, 3, 15)  # inside the tiny window, all lags readable


def _issue_time_us(day: date) -> int:
    return int(issue_time_utc(day).timestamp() * 1_000_000)


def _station_rows(table, station_id):
    return table.filter(pc.equal(table["station_id"], station_id)).sort_by("hour_utc")


def _demand_at(release, sid, hour_us):
    table = read_table(release, "demand")
    rows = table.filter(
        pc.and_(
            pc.equal(table["station_id"], sid),
            pc.equal(table["hour_utc"].cast(pa.int64()), pa.scalar(hour_us, type=pa.int64())),
        )
    )
    assert rows.num_rows == 1
    return float(rows["demand_kwh"][0].as_py())


def _release_for(tmp_path, overrides: dict | None = None):
    config_path = write_config(tmp_path / "config.yaml", overrides=overrides)
    cfg = load_config(config_path)
    release = tmp_path / "release"
    ChargingGenerator(cfg).generate(release)
    publish_manifest(release, cfg)
    return release, cfg


def test_issue_rows_keyed_and_stamped(tiny_release):
    release, cfg = tiny_release
    table = FeatureBuilder(release, cfg).build_issue(ISSUE)

    assert table.num_rows == 6 * 24
    assert table.num_rows == len(
        set(zip(table["station_id"].to_pylist(), table["hour_utc"].to_pylist(), strict=False))
    )
    t_us = _issue_time_us(ISSUE)
    assert set(table["available_at"].to_pylist()) == {
        datetime.fromtimestamp(t_us / 1_000_000, tz=UTC)
    }
    hours = np.sort(table["hour_utc"].cast(pa.int64()).to_numpy())
    b_us = t_us + 19 * US_HOUR  # next UTC midnight after T (05:00Z in March)
    assert hours[0] == b_us and hours[-1] == b_us + 23 * US_HOUR
    assert hours.min() > t_us  # targets strictly in the future


def test_lag_features_match_source(tiny_release):
    release, cfg = tiny_release
    table = _station_rows(FeatureBuilder(release, cfg).build_issue(ISSUE), "S001")

    t_us = _issue_time_us(ISSUE)
    assert table["demand_lag_24h"][0].as_py() == pytest.approx(
        _demand_at(release, "S001", t_us - 24 * US_HOUR)
    )
    assert table["demand_lag_168h"][0].as_py() == pytest.approx(
        _demand_at(release, "S001", t_us - 168 * US_HOUR)
    )
    assert table["demand_latest"][0].as_py() == pytest.approx(
        _demand_at(release, "S001", t_us - 2 * US_HOUR)
    )
    window = np.arange(t_us - 168 * US_HOUR, t_us - 2 * US_HOUR + US_HOUR, US_HOUR)
    expected = float(np.mean([_demand_at(release, "S001", int(h)) for h in window]))
    assert table["demand_rolling_7d_mean"][0].as_py() == pytest.approx(expected)


def test_forecast_joined_by_reference(tiny_release):
    release, cfg = tiny_release
    table = _station_rows(FeatureBuilder(release, cfg).build_issue(ISSUE), "S001")

    fcst = read_table(release, "weather_fcst")
    t_us = _issue_time_us(ISSUE)
    district = table["district"][0].as_py()
    for row_hours, row_temp in zip(
        table["hour_utc"].cast(pa.int64()).to_pylist(),
        table["fcst_temperature_c"].to_pylist(),
        strict=False,
    ):
        rows = fcst.filter(
            pc.and_(
                pc.equal(fcst["district"], district),
                pc.and_(
                    pc.equal(fcst["reference_hour_utc"].cast(pa.int64()), pa.scalar(row_hours)),
                    pc.less_equal(fcst["available_at"].cast(pa.int64()), pa.scalar(t_us)),
                ),
            )
        )
        assert rows.num_rows == 1
        assert row_temp == pytest.approx(rows["temperature_c"][0].as_py())


def test_calendar_flags_come_from_the_published_calendar(tmp_path):
    release, cfg = _release_for(
        tmp_path,
        overrides={"window": {"start": "2025-04-14T00:00:00Z", "end": "2025-04-20T23:00:00Z"}},
    )
    table = FeatureBuilder(release, cfg).build_issue(date(2025, 4, 17))  # target: Karfreitag

    by_day = {}
    for hour, pub, school in zip(
        table["hour_utc"].to_pylist(),
        table["is_public_holiday"].to_pylist(),
        table["is_school_break"].to_pylist(),
        strict=False,
    ):
        by_day[hour.date()] = (pub, school)
    assert by_day == {date(2025, 4, 18): (True, True)}  # one target day, holiday + break


def test_tariff_schedule_known_ahead_of_target_day(tiny_release):
    release, cfg = tiny_release
    table = FeatureBuilder(release, cfg).build_issue(date(2025, 3, 9))  # target day: the step

    d2 = table.filter(pc.equal(table["district"], "D2"))
    d1 = table.filter(pc.equal(table["district"], "D1"))
    assert set(d2["price_current"].to_pylist()) == {0.33}  # base still in force at T
    assert set(d2["price_at_target"].to_pylist()) == {0.48}  # step lands on the target day
    assert set(d1["price_current"].to_pylist()) == {0.35}
    assert set(d1["price_at_target"].to_pylist()) == {0.35}


def test_late_station_enters_at_active_from(tmp_path):
    cfg_dict = copy.deepcopy(TINY_CONFIG)
    cfg_dict["stations"]["active_from_late"] = {"2025-03-12": ["S001"]}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg_dict), encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")
    release = tmp_path / "release"
    ChargingGenerator(cfg).generate(release)
    publish_manifest(release, cfg)
    builder = FeatureBuilder(release, cfg)

    early = builder.build_issue(date(2025, 3, 10))
    assert "S001" not in set(early["station_id"].to_pylist())  # not readable yet
    assert early.num_rows == 5 * 24

    late = _station_rows(builder.build_issue(date(2025, 3, 15)), "S001")
    assert late.num_rows == 24
    assert late["days_active"][0].as_py() == pytest.approx(3 + 5 / 24, abs=1e-4)


def test_issue_beyond_forecast_coverage_is_refused(tiny_release):
    release, cfg = tiny_release
    with pytest.raises(ValueError, match="beyond forecast coverage"):
        FeatureBuilder(release, cfg).build_issue(date(2025, 3, 21))  # target 03-22: no forecast
