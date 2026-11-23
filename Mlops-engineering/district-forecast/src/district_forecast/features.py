"""The district feature contract as code (M09 domain contract).

The availability table freezes what a model issued at T = 06:00
Europe/Berlin may read on the district grain. It mirrors the station-level
contract (docs/feature-contract.md v1) with district semantics: demand
lags use the same fixed clock windows, published schedules join by
schedule semantics, realized weather and same-day demand are never
readable. Feature rows are keyed (district, target hour), stamped
available_at = T, and the build is deterministic: no wall-clock input
affects the bytes.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .evaluation import HourlySeries
from .releases import (
    US_DAY,
    US_HOUR,
    git_commit,
    issue_time_us,
    sha256_file,
    target_hours_us,
)

INGESTION_DELAY_HOURS = 1
LAG_HOURS = (24, 168)
ROLLING_HOURS = 168

SCHEMA_VERSION = "district-features-v1"

AVAILABILITY_TABLE: dict[str, dict] = {
    "calendar": {
        "readable_at_issue": True,
        "readability_bound": False,
        "rule": "Published calendar and event schedules, readable ahead of their stamps.",
    },
    "district_attributes": {
        "readable_at_issue": True,
        "readability_bound": True,
        "rule": "Static per derived dataset release.",
    },
    "demand_lags": {
        "readable_at_issue": True,
        "readability_bound": True,
        "rule": "Fixed clock windows anchored at T; a lagged hour counts only "
        "if its row is stamped available_at <= T.",
    },
    "weather_forecasts": {
        "readable_at_issue": True,
        "readability_bound": True,
        "rule": "Only forecasts with available_at <= T, joined by reference hour; "
        "the latest such issue wins.",
    },
    "tariff_schedule": {
        "readable_at_issue": True,
        "readability_bound": False,
        "rule": "Published schedule; joined by effectiveness at the target hour.",
    },
    "weather_realized": {
        "readable_at_issue": False,
        "readability_bound": True,
        "rule": "Never readable at issue time.",
    },
    "same_day_demand": {
        "readable_at_issue": False,
        "readability_bound": True,
        "rule": "The prediction target is never readable at issue time.",
    },
}


def valid_issue_range(cfg: dict) -> tuple[date, date]:
    start = date.fromisoformat(cfg["window"]["start"][:10])
    end = date.fromisoformat(cfg["window"]["end"][:10]) - timedelta(days=1)
    return start, end


def feature_release_id(cfg: dict) -> str:
    return f"feat-d1-{cfg['release_id']}"


def _load(release_dir: Path, name: str) -> pa.Table:
    parts = sorted((Path(release_dir) / "data" / name).rglob("*.parquet"))
    if not parts:
        raise ValueError(f"no parquet parts under {name}")
    return pa.concat_tables([pq.read_table(p) for p in parts])


class DistrictDemand(HourlySeries):
    """District-hour demand sorted by hour, extending the template's
    entity-generic series with rolling-window reads."""

    def __init__(self, demand: pa.Table):
        dist = np.asarray(demand["district"].to_pylist())
        hours = demand["hour_utc"].cast(pa.int64()).to_numpy()
        values = demand["demand_kwh"].to_numpy()
        avail = demand["available_at"].cast(pa.int64()).to_numpy()
        entities: list[str] = []
        self.hours = {}
        self.values = {}
        self.avail = {}
        self.prefix: dict[str, np.ndarray] = {}
        for district in sorted(set(dist.tolist())):
            idx = np.flatnonzero(dist == district)
            order = np.argsort(hours[idx], kind="stable")
            h, v, a = hours[idx][order], values[idx][order], avail[idx][order]
            entities.append(district)
            self.hours[district] = h
            self.values[district] = v
            self.avail[district] = a
            self.prefix[district] = np.concatenate(([0.0], np.cumsum(v)))
        super().__init__(entities, self.hours, self.values, self.avail)

    def readable(self, district: str, hour_us: int, t_us: int) -> float:
        """The realized value for one hour, only if stamped available_at <= t_us."""
        hours, values, avail = self.hours[district], self.values[district], self.avail[district]
        idx = int(np.searchsorted(hours, hour_us))
        if idx < len(hours) and hours[idx] == hour_us and avail[idx] <= t_us:
            return float(values[idx])
        return float("nan")

    def lag(self, district: str, t_us: int, lag_hours: int) -> float:
        """The M02 lag anchored at the issue time T: one value per issue day,
        readable only if the lagged row is stamped available_at <= T."""
        return self.readable(district, t_us - lag_hours * US_HOUR, t_us)

    def rolling_mean(self, district: str, t_us: int) -> float:
        """Mean readable demand over [T − 168 h, T − 2 h], the M02 window
        anchored at the issue time T (one value per issue day and district).
        A missing or late-stamped hour in the window blocks the value."""
        lo = t_us - ROLLING_HOURS * US_HOUR
        hi = t_us - (INGESTION_DELAY_HOURS + 1) * US_HOUR
        hours, prefix, avail = self.hours[district], self.prefix[district], self.avail[district]
        left = int(np.searchsorted(hours, lo, side="left"))
        right = int(np.searchsorted(hours, hi, side="right"))
        expected_count = (hi - lo) // US_HOUR + 1
        if right - left != expected_count or not bool((avail[left:right] <= t_us).all()):
            return float("nan")
        return round(float(prefix[right] - prefix[left]) / expected_count, 6)


class WeatherForecasts:
    """Index over the forecast table: latest issue readable at T per
    (district, reference hour)."""

    def __init__(self, forecasts: pa.Table):
        dist = np.asarray(forecasts["district"].to_pylist())
        ref = forecasts["reference_hour_utc"].cast(pa.int64()).to_numpy()
        issue = forecasts["issue_at"].cast(pa.int64()).to_numpy()
        avail = forecasts["available_at"].cast(pa.int64()).to_numpy()
        temp = forecasts["temperature_c"].to_numpy()
        precip = forecasts["precipitation_mm"].to_numpy()
        self.by_key: dict[tuple[str, int], list[tuple[int, int, float, float]]] = {}
        for i in range(len(dist)):
            self.by_key.setdefault((str(dist[i]), int(ref[i])), []).append(
                (int(issue[i]), int(avail[i]), float(temp[i]), float(precip[i]))
            )

    def at(self, district: str, reference_hour_us: int, t_us: int) -> tuple[float, float]:
        rows = [row for row in self.by_key.get((district, reference_hour_us), ()) if row[1] <= t_us]
        if not rows:
            return float("nan"), float("nan")
        latest = max(rows, key=lambda row: row[0])
        return latest[2], latest[3]


class TariffSchedule:
    """Published district tariff schedule, effective at the target hour."""

    def __init__(self, tariffs: pa.Table):
        dist = np.asarray(tariffs["district"].to_pylist())
        eff = tariffs["effective_from"].cast(pa.int64()).to_numpy()
        price = tariffs["price_per_kwh"].to_numpy()
        self.by_district: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for district in sorted(set(dist.tolist())):
            idx = np.flatnonzero(dist == district)
            order = np.argsort(eff[idx], kind="stable")
            self.by_district[district] = (eff[idx][order], price[idx][order])

    def at(self, district: str, hour_us: int) -> float:
        eff, price = self.by_district[district]
        idx = int(np.searchsorted(eff, hour_us, side="right")) - 1
        return float(price[idx]) if idx >= 0 else float("nan")


def build_features(cfg: dict, release_dir: Path, out_dir: Path) -> dict:
    """Materialize one row per (district, target hour) for every issue day,
    partitioned by issue month with a checksummed manifest."""
    release_dir, out_dir = Path(release_dir), Path(out_dir)
    districts_table = _load(release_dir, "districts")
    demand = DistrictDemand(_load(release_dir, "demand"))
    tariffs = TariffSchedule(_load(release_dir, "tariffs"))
    holidays = _load(release_dir, "holidays")
    events = _load(release_dir, "events")
    forecasts = WeatherForecasts(_load(release_dir, "weather_fcst"))

    station_count = dict(
        zip(
            districts_table["district"].to_pylist(),
            districts_table["station_count"].to_pylist(),
            strict=True,
        )
    )
    capacity = dict(
        zip(
            districts_table["district"].to_pylist(),
            districts_table["capacity_kw_total"].to_pylist(),
            strict=True,
        )
    )
    holiday_days = {
        d
        for d, is_public in zip(
            holidays["date"].to_pylist(),
            holidays["is_public_holiday"].to_pylist(),
            strict=True,
        )
        if is_public
    }
    ev_dist = np.asarray(events["district"].to_pylist())
    ev_start = events["start_utc"].cast(pa.int64()).to_numpy()
    ev_end = events["end_utc"].cast(pa.int64()).to_numpy()
    ev_boost = events["boost"].to_numpy()

    first, last = valid_issue_range(cfg)
    columns: dict[str, list] = {
        name: []
        for name in (
            "issue_date",
            "district",
            "target_hour_utc",
            "hour_of_day",
            "day_of_week",
            "is_public_holiday",
            "event_boost",
            "station_count",
            "capacity_kw_total",
            "tariff_price",
            "forecast_temperature_c",
            "forecast_precipitation_mm",
            "days_since_start",
            "demand_lag_24h",
            "demand_lag_168h",
            "demand_rolling_7d",
            "demand_kwh",
        )
    }

    issue = first
    while issue <= last:
        t_us = issue_time_us(issue)
        days_since_start = (issue - first).days
        rolling = {d: demand.rolling_mean(d, t_us) for d in cfg["districts"]}
        for district in cfg["districts"]:
            targets = target_hours_us(issue)
            lags = {lag: demand.lag(district, t_us, lag) for lag in LAG_HOURS}
            weather = [forecasts.at(district, int(h), t_us) for h in targets.tolist()]
            district_events = ev_dist == district
            for pos, hour_us in enumerate(targets.tolist()):
                hod = (hour_us // US_HOUR) % 24
                dow = ((hour_us // US_DAY) + 3) % 7
                target_date = datetime.fromtimestamp(hour_us / 1e6, tz=UTC).date()
                boost = float(
                    ev_boost[district_events & (ev_start <= hour_us) & (hour_us < ev_end)].sum()
                )
                columns["issue_date"].append(issue.isoformat())
                columns["district"].append(district)
                columns["target_hour_utc"].append(hour_us)
                columns["hour_of_day"].append(int(hod))
                columns["day_of_week"].append(int(dow))
                columns["is_public_holiday"].append(target_date in holiday_days)
                columns["event_boost"].append(boost)
                columns["station_count"].append(int(station_count[district]))
                columns["capacity_kw_total"].append(float(capacity[district]))
                columns["tariff_price"].append(tariffs.at(district, hour_us))
                columns["forecast_temperature_c"].append(weather[pos][0])
                columns["forecast_precipitation_mm"].append(weather[pos][1])
                columns["demand_lag_24h"].append(lags[24])
                columns["demand_lag_168h"].append(lags[168])
                columns["days_since_start"].append(days_since_start)
                columns["demand_rolling_7d"].append(rolling[district])
                # The label column: the realized aggregate, read without the
                # issue-time bound (labels join in the evaluator instead).
                columns["demand_kwh"].append(demand.readable(district, hour_us, 1 << 62))
        issue += timedelta(days=1)

    table = pa.table({k: pa.array(v) for k, v in columns.items()})
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for month in sorted({d[:7] for d in columns["issue_date"]}):
        part = out_dir / f"issue_month={month}/part-0000.parquet"
        part.parent.mkdir(parents=True, exist_ok=True)
        mask = pa.array([d.startswith(month) for d in columns["issue_date"]])
        pq.write_table(table.filter(mask), part)
        written.append(part)

    manifest = {
        "feature_release_id": feature_release_id(cfg),
        "schema_version": SCHEMA_VERSION,
        "kind": "features",
        "issues": len(set(columns["issue_date"])),
        "issue_start": first.isoformat(),
        "issue_end": last.isoformat(),
        "rows": table.num_rows,
        "columns": list(columns.keys()),
        "availability_table": AVAILABILITY_TABLE,
        "source_manifest_sha256": sha256_file(release_dir / "manifest.json"),
        "source_release_id": json.loads((release_dir / "manifest.json").read_text())["release_id"],
        "source_commit": git_commit(out_dir),
        "files": [
            {
                "path": part.relative_to(out_dir).as_posix(),
                "rows": pq.read_metadata(part).num_rows,
                "size_bytes": part.stat().st_size,
                "sha256": sha256_file(part),
            }
            for part in sorted(written)
        ],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
