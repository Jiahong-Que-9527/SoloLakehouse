"""Shared fixture: a tiny dataset-v001-shaped source release.

Two districts (D1 with two stations, D2 with one), 50 days of hourly
demand with a strong hour/weekday pattern and mild seeded noise, a
tariff step in D2, one event, day-ahead weather forecasts following the
06:00-Berlin issue convention (05:00 UTC in this winter-only window).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from district_forecast.releases import build_file_manifest, publish_release

TS = pa.timestamp("us", tz="UTC")
DAYS = 240
START = datetime(2025, 1, 1, tzinfo=UTC)
DISTRICTS = ["D1", "D2"]
STATIONS = {"S1": "D1", "S2": "D1", "S3": "D2"}
CAPACITY = {"S1": 150.0, "S2": 200.0, "S3": 250.0}
POI = {"S1": "office", "S2": "retail", "S3": "highway"}


def _us(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)


def _write(table, data: Path, name: str) -> None:
    part = data / name / "part-0000.parquet"
    part.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, part)


def _temperature(day: int, hour: int, daily: np.ndarray) -> float:
    """Seasonal + diurnal cycle plus a per-day anomaly, so the (hour, weekday)
    median cannot absorb the weather signal."""
    seasonal = 6.0 * np.sin(2 * np.pi * day / 365)
    diurnal = 5.0 * np.sin((hour - 6) / 24 * 2 * np.pi)
    return float(seasonal + diurnal + daily[day])


def _daily() -> np.ndarray:
    """The per-day weather anomaly shared by demand and both weather tables:
    a bounded AR(1) anomaly, so the distribution stays stationary (tree
    ensembles cannot extrapolate a drifting walk)."""
    rng = np.random.default_rng(7)
    daily = np.empty(DAYS + 1)
    daily[0] = rng.normal(0.0, 1.0)
    for day in range(1, DAYS + 1):
        daily[day] = 0.8 * daily[day - 1] + rng.normal(0.0, 1.5)
    return daily


def _demand() -> pa.Table:
    rng = np.random.default_rng(7)
    daily = _daily()
    hours, sid, values, avail = [], [], [], []
    for station in STATIONS:
        for day in range(DAYS):
            for hour in range(24):
                h_us = _us(START) + (day * 24 + hour) * 3_600_000_000
                weekday = (day + 2) % 7  # 2025-01-01 is a Wednesday
                base = 40.0 + hour * (3.0 if hour < 18 else -2.0)
                weekly = 12.0 if weekday >= 5 else 0.0
                # Weather-driven variation the (hour, weekday) median cannot
                # track, so the model has signal beyond both baselines. No
                # trend: tree ensembles cannot extrapolate one, and the
                # seasonal naive would harvest it for free.
                temp = _temperature(day, hour, daily)
                value = max(0.0, base + weekly + 1.2 * temp + rng.normal(0.0, 1.5))
                hours.append(h_us)
                sid.append(station)
                values.append(round(value, 3))
                avail.append(h_us + 2 * 3_600_000_000)
    return pa.table(
        {
            "station_id": pa.array(sid, pa.string()),
            "hour_utc": pa.array(hours, TS),
            "demand_kwh": pa.array(values, pa.float64()),
            "available_at": pa.array(avail, TS),
        }
    )


@pytest.fixture()
def source_release(tmp_path: Path) -> Path:
    release = tmp_path / "dataset-v001"
    data = release / "data"
    data.mkdir(parents=True)

    stations = pa.table(
        {
            "station_id": pa.array(list(STATIONS), pa.string()),
            "district": pa.array(list(STATIONS.values()), pa.string()),
            "poi_category": pa.array(list(POI.values()), pa.string()),
            "capacity_kw": pa.array(list(CAPACITY.values()), pa.float64()),
            "active_from": pa.array([_us(START)] * 3, TS).cast(TS),
            "available_at": pa.array([_us(START)] * 3, TS).cast(TS),
        }
    )
    _write(stations, data, "stations")
    _write(_demand(), data, "demand")

    tariff_rows = {"station_id": [], "effective_from": [], "price_per_kwh": [], "available_at": []}
    for station, district in STATIONS.items():
        tariff_rows["station_id"].append(station)
        tariff_rows["effective_from"].append(_us(START))
        tariff_rows["price_per_kwh"].append(0.35 if district == "D1" else 0.30)
        tariff_rows["available_at"].append(_us(START))
        if district == "D2":  # the tariff step
            step = START + timedelta(days=31)
            tariff_rows["station_id"].append(station)
            tariff_rows["effective_from"].append(_us(step))
            tariff_rows["price_per_kwh"].append(0.45)
            tariff_rows["available_at"].append(_us(step))
    _write(pa.table(tariff_rows), data, "tariffs")

    holidays = pa.table(
        {
            "date": pa.array([START.date() + timedelta(days=d) for d in range(DAYS)]),
            "name": pa.array([""] * DAYS, pa.string()),
            "is_public_holiday": pa.array([False] * DAYS),
            "is_school_break": pa.array([False] * DAYS),
            "available_at": pa.array([_us(START)] * DAYS, TS).cast(TS),
        }
    )
    _write(holidays, data, "holidays")

    events = pa.table(
        {
            "event_id": pa.array(["E1"], pa.string()),
            "district": pa.array(["D1"], pa.string()),
            "start_utc": pa.array([_us(START + timedelta(days=40, hours=8))], TS).cast(TS),
            "end_utc": pa.array([_us(START + timedelta(days=41, hours=2))], TS).cast(TS),
            "boost": pa.array([0.2], pa.float64()),
            "available_at": pa.array([_us(START + timedelta(days=33))], TS).cast(TS),
        }
    )
    _write(events, data, "events")

    obs = {
        "district": [],
        "hour_utc": [],
        "temperature_c": [],
        "precipitation_mm": [],
        "available_at": [],
    }
    fcst = {
        "district": [],
        "issue_at": [],
        "reference_hour_utc": [],
        "temperature_c": [],
        "precipitation_mm": [],
        "available_at": [],
    }
    daily = _daily()
    for district in DISTRICTS:
        for day in range(DAYS + 1):
            for hour in range(24):
                h_us = _us(START) + (day * 24 + hour) * 3_600_000_000
                temp = _temperature(day, hour, daily)
                obs["district"].append(district)
                obs["hour_utc"].append(h_us)
                obs["temperature_c"].append(round(float(temp), 2))
                obs["precipitation_mm"].append(0.0)
                obs["available_at"].append(h_us + 3_600_000_000)
                ref_day = datetime.fromtimestamp(h_us / 1e6, tz=UTC)
                issue_local = (ref_day - timedelta(days=1)).replace(
                    hour=6, minute=0, second=0, tzinfo=ZoneInfo("Europe/Berlin")
                )
                issue_us = _us(issue_local)  # 06:00 Berlin the day before
                fcst["district"].append(district)
                fcst["issue_at"].append(issue_us)
                fcst["reference_hour_utc"].append(h_us)
                fcst["temperature_c"].append(round(float(temp), 2))
                fcst["precipitation_mm"].append(0.0)
                fcst["available_at"].append(issue_us)
    _write(pa.table({k: pa.array(v) for k, v in obs.items()}), data, "weather_obs")
    _write(pa.table({k: pa.array(v) for k, v in fcst.items()}), data, "weather_fcst")

    cfg = {
        "release_id": "dataset-v001",
        "schema_version": "charging-dataset-v1",
        "seed": 7,
        "_config_path": "fixture",
        "window": {
            "start": "2025-01-01T00:00:00+00:00",
            "end": f"{(START + timedelta(days=DAYS - 1)):%Y-%m-%dT%H:%M:%S%z}",
        },
    }
    manifest = build_file_manifest(
        release,
        release_id="dataset-v001",
        schema_version="charging-dataset-v1",
        kind="dataset",
        extra={"seed": 7, "config_sha256": "fixture", "source_commit": "fixture"},
    )
    publish_release(release, manifest)
    del cfg
    return release


@pytest.fixture()
def district_cfg(tmp_path: Path) -> dict:
    return {
        "release_id": "dataset-district-v001",
        "schema_version": "district-dataset-v1",
        "source_release_id": "dataset-v001",
        "source_release": "unused-in-tests",
        "window": {
            "start": "2025-01-01T00:00:00+00:00",
            "end": f"{(START + timedelta(days=DAYS - 1)):%Y-%m-%dT%H:%M:%S%z}",
        },
        "districts": DISTRICTS,
        "_config_path": "fixture",
    }
