"""Seeded synthetic generator for the EV charging network (M01).

Determinism contract: the same seed and config produce byte-identical
Parquet. All randomness comes from one numpy PCG64 Generator consumed in a
fixed order (stations, events, weather, forecasts, demand); loops iterate
sorted keys only; no wall-clock, locale or hash-order value enters the
output. Parquet is written with fixed writer settings. Timestamps are
handled as int64 microseconds since the epoch, never parsed from tz-aware
ISO strings.

The anomaly mode (stale/missing forecast files) is a generator option for
M07 monitoring drills only — it is never part of a dataset release.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .contract import ISSUE_TIMEZONE, issue_time_utc

EPOCH_US = np.datetime64("1970-01-01T00:00:00", "us")
TS_TYPE = pa.timestamp("us", tz="UTC")

# German public holidays 2025-2026 (statutory, nationwide).
PUBLIC_HOLIDAYS: dict[str, str] = {
    "2025-01-01": "Neujahr",
    "2025-04-18": "Karfreitag",
    "2025-04-21": "Ostermontag",
    "2025-05-01": "Tag der Arbeit",
    "2025-05-29": "Christi Himmelfahrt",
    "2025-06-09": "Pfingstmontag",
    "2025-10-03": "Tag der Deutschen Einheit",
    "2025-12-25": "1. Weihnachtstag",
    "2025-12-26": "2. Weihnachtstag",
    "2026-01-01": "Neujahr",
    "2026-04-03": "Karfreitag",
    "2026-04-06": "Ostermontag",
    "2026-05-01": "Tag der Arbeit",
    "2026-05-14": "Christi Himmelfahrt",
    "2026-05-25": "Pfingstmontag",
    "2026-10-03": "Tag der Deutschen Einheit",
    "2026-12-25": "1. Weihnachtstag",
    "2026-12-26": "2. Weihnachtstag",
}

# Hessen school breaks, frozen from the published 2025/26 calendar for
# reproducibility (the demand shape, not calendar scholarship, is the point).
SCHOOL_BREAKS: list[tuple[str, str, str]] = [
    ("2025-04-14", "2025-04-25", "Osterferien 2025"),
    ("2025-07-07", "2025-08-15", "Sommerferien 2025"),
    ("2025-10-13", "2025-10-24", "Herbstferien 2025"),
    ("2025-12-22", "2026-01-06", "Weihnachtsferien 2025/26"),
    ("2026-03-30", "2026-04-10", "Osterferien 2026"),
    ("2026-06-29", "2026-08-07", "Sommerferien 2026"),
    ("2026-10-12", "2026-10-23", "Herbstferien 2026"),
    ("2026-12-21", "2026-12-31", "Weihnachtsferien 2026/27"),
]

# Mean-shape hourly profiles per POI category (multiples of mean utilization).
# Applied at 0.5 capacity utilization so the physical clip at capacity binds
# only at coincident highs (peak x weather x noise), not on half the hours.
UTILIZATION = 0.5
POI_PROFILE: dict[str, np.ndarray] = {
    "office": np.array(
        [
            0.20,
            0.15,
            0.12,
            0.12,
            0.15,
            0.30,
            0.70,
            1.40,
            1.80,
            1.70,
            1.30,
            1.10,
            1.20,
            1.20,
            1.15,
            1.20,
            1.50,
            1.90,
            1.80,
            1.50,
            1.10,
            0.70,
            0.45,
            0.30,
        ]
    ),
    "retail": np.array(
        [
            0.30,
            0.25,
            0.20,
            0.20,
            0.25,
            0.40,
            0.70,
            1.00,
            1.20,
            1.30,
            1.40,
            1.45,
            1.40,
            1.40,
            1.40,
            1.45,
            1.50,
            1.55,
            1.40,
            1.20,
            0.90,
            0.65,
            0.50,
            0.40,
        ]
    ),
    "residential": np.array(
        [
            0.60,
            0.55,
            0.50,
            0.45,
            0.45,
            0.50,
            0.60,
            0.70,
            0.75,
            0.75,
            0.75,
            0.80,
            0.80,
            0.80,
            0.85,
            0.90,
            1.05,
            1.30,
            1.60,
            1.80,
            1.75,
            1.50,
            1.10,
            0.80,
        ]
    ),
    "highway": np.array(
        [
            0.50,
            0.45,
            0.45,
            0.45,
            0.50,
            0.60,
            0.80,
            1.00,
            1.15,
            1.25,
            1.30,
            1.30,
            1.30,
            1.30,
            1.30,
            1.30,
            1.35,
            1.40,
            1.40,
            1.30,
            1.15,
            0.95,
            0.75,
            0.60,
        ]
    ),
}

WEEKEND_FACTOR: dict[str, float] = {
    "office": 0.25,
    "retail": 1.25,
    "residential": 1.10,
    "highway": 1.20,
}

HOLIDAY_FACTOR: dict[str, float] = {
    "office": 0.55,
    "retail": 0.95,
    "residential": 1.10,
    "highway": 1.20,
}

SCHOOL_FACTOR: dict[str, float] = {
    "office": 0.90,
    "retail": 1.00,
    "residential": 1.08,
    "highway": 1.00,
}


def _hours(start: str, end: str) -> np.ndarray:
    """Inclusive hourly UTC range from ISO start to ISO end."""
    h0 = np.datetime64(start.replace("Z", ""), "h")
    h1 = np.datetime64(end.replace("Z", ""), "h")
    return np.arange(h0, h1 + np.timedelta64(1, "h"), dtype="datetime64[h]")


def _us(hours: np.ndarray) -> np.ndarray:
    """datetime64 hours -> int64 microseconds since the epoch."""
    return (hours.astype("datetime64[us]") - EPOCH_US).astype("int64")


def _us_scalar(hours: np.ndarray) -> int:
    return int(_us(np.array([hours]))[0])


def _ts(values: np.ndarray) -> pa.Array:
    """int64 microseconds -> pyarrow timestamp[us, tz=UTC] column."""
    return pa.array(_us(values), type=TS_TYPE)


class ChargingGenerator:
    """Generate one dataset release from a frozen config."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg["seed"])
        self.hours = _hours(cfg["window"]["start"], cfg["window"]["end"])
        self.n_hours = len(self.hours)
        self.hour_of_day = np.arange(self.n_hours) % 24
        day_index = (self.hours - self.hours[0]).astype("timedelta64[h]").astype(int) // 24
        self.day_of_hours = day_index  # hours -> day number within the window
        self.days = np.arange(
            self.hours[0].astype("datetime64[D]"),
            self.hours[-1].astype("datetime64[D]") + np.timedelta64(1, "D"),
            dtype="datetime64[D]",
        )
        self.n_days = len(self.days)
        self.weekday = (
            (self.hours.astype("datetime64[D]") - np.datetime64("1970-01-01", "D")).astype(int) + 3
        ) % 7  # 1970-01-01 was a Thursday (Monday=0 convention)
        self.is_weekend = np.isin(self.weekday, (5, 6))

    # -- stations ---------------------------------------------------------

    def build_stations(self) -> tuple[list[dict], list[tuple[str, str]]]:
        """Station rows plus the (station, district) assignment list."""
        scfg = self.cfg["stations"]
        districts = scfg["districts"]
        poi_mix = scfg["poi_mix"]
        pool: list[str] = []
        for poi in sorted(poi_mix):
            pool.extend([poi] * poi_mix[poi])
        stations: list[dict] = []
        pairs: list[tuple[str, str]] = []
        idx = 0
        for district in sorted(districts):
            for _ in range(districts[district]):
                sid = f"S{idx + 1:03d}"
                poi = pool[(idx * 11) % len(pool)]  # 11 coprime with the mix totals
                lo, hi = scfg["capacity_kw"][poi]
                capacity = float(round(self.rng.uniform(lo, hi) / 5.0) * 5.0)
                active_from = scfg["active_from_default"]
                for day, sids in sorted(scfg.get("active_from_late", {}).items()):
                    if sid in sids:
                        active_from = day
                stations.append(
                    {
                        "station_id": sid,
                        "district": district,
                        "poi_category": poi,
                        "capacity_kw": capacity,
                        "active_from": active_from,
                    }
                )
                pairs.append((sid, district))
                idx += 1
        return stations, pairs

    # -- weather ----------------------------------------------------------

    def build_weather(self, districts: list[str]) -> tuple[dict[str, dict], dict[str, list]]:
        """Realized hourly weather and day-ahead forecasts, per district."""

        heatwave = self.cfg.get("heatwave") or {}
        hw_mask = np.zeros(self.n_days, dtype=bool)
        hw_offset = np.zeros(self.n_days)
        if heatwave:
            hw_start = np.datetime64(heatwave["start"], "D")
            hw_end = np.datetime64(heatwave["end"], "D")
            for i, day in enumerate(self.days):
                if hw_start <= day <= hw_end:
                    hw_mask[i] = True
                    hw_offset[i] = self.rng.uniform(*heatwave["temp_offset_c"])

        diurnal = 4.2 * np.sin(2 * np.pi * (self.hour_of_day - 9) / 24)
        realized: dict[str, dict] = {}
        offsets = {d: self.rng.uniform(-0.8, 0.8) for d in districts}
        for district in districts:
            anomaly = np.zeros(self.n_days)
            sigma, rho = 1.8, 0.8
            z = self.rng.standard_normal(self.n_days)
            for i in range(1, self.n_days):
                anomaly[i] = rho * anomaly[i - 1] + np.sqrt(1 - rho**2) * sigma * z[i]
            clim = 10.5 + 11.0 * np.sin(2 * np.pi * (np.arange(self.n_days) - 105) / 365.25)
            daily_temp = clim + anomaly + offsets[district] + hw_offset * hw_mask

            # Precipitation: Markov wet/dry per day, amounts spread over hours.
            precip = np.zeros(self.n_hours)
            state = False
            for i in range(self.n_days):
                p_wet = 0.55 if state else 0.25
                state = bool(self.rng.random() < p_wet)
                if not state:
                    continue
                total = float(self.rng.exponential(1.6))
                k = int(self.rng.integers(3, 9))
                picks = np.sort(self.rng.choice(24, size=k, replace=False))
                weights = self.rng.random(k)
                weights /= weights.sum()
                for j, hour_idx in enumerate(picks):
                    precip[i * 24 + hour_idx] = round(total * weights[j], 2)

            realized[district] = {
                "temperature_c": np.round(daily_temp[self.day_of_hours] + diurnal, 2),
                "precipitation_mm": precip,
            }

        # Day-ahead forecasts: issued 06:00 Europe/Berlin for the next day.
        forecasts: dict[str, list] = {d: [] for d in districts}
        rho_f = self.cfg.get("forecast_error_rho", 0.6)
        sigma_f = self.cfg.get("forecast_temp_sigma_c", 1.2)
        issue_days = self.days[:-1]  # forecast for day d+1 issued on day d
        for district in districts:
            err = 0.0
            skip: set[int] = set()
            if self.cfg.get("anomaly_mode"):
                skip = set(self.rng.choice(len(issue_days), size=5, replace=False).tolist())
            for i, day in enumerate(issue_days):
                # issue_time_utc returns an aware datetime; convert via timestamp().
                issue_us = int(issue_time_utc(date.fromisoformat(str(day))).timestamp() * 1_000_000)
                if i in skip:
                    continue  # anomaly drill: the forecast issue is missing
                ref_day = day + np.timedelta64(1, "D")
                z = self.rng.standard_normal(24)
                temps, precs = [], []
                for h in range(24):
                    err = rho_f * err + np.sqrt(1 - rho_f**2) * sigma_f * z[h]
                    hour_idx = i * 24 + 24 + h  # hours are aligned to window start
                    realized_t = realized[district]["temperature_c"][hour_idx]
                    realized_p = realized[district]["precipitation_mm"][hour_idx]
                    temps.append(round(realized_t + err, 2))
                    p = realized_p * float(self.rng.uniform(0.4, 1.2))
                    if realized_p == 0.0 and self.rng.random() < 0.12:
                        p = round(self.rng.uniform(0.1, 0.5), 2)
                    precs.append(round(p, 2))
                forecasts[district].append(
                    {
                        "issue_us": issue_us,
                        "ref_day": ref_day,
                        "temperature_c": temps,
                        "precipitation_mm": precs,
                    }
                )
        return realized, forecasts

    # -- events -----------------------------------------------------------

    def build_events(self, districts: list[str]) -> list[dict]:
        events: list[dict] = []
        seq = 0
        first_day = self.hours[0].astype("datetime64[D]")
        last_day = self.hours[-1].astype("datetime64[D]")
        n_weeks = int((last_day - first_day).astype(int) // 7)
        for district in districts:
            for w in range(n_weeks):
                if self.rng.random() >= 0.12:
                    continue
                saturday = first_day + np.timedelta64(7 * w + 5, "D")
                if saturday + np.timedelta64(1, "D") > last_day:
                    continue
                start = saturday.astype("datetime64[h]") + np.timedelta64(10, "h")
                end = (saturday + np.timedelta64(1, "D")).astype("datetime64[h]") + np.timedelta64(
                    22, "h"
                )
                events.append(
                    {
                        "event_id": f"E{seq:04d}",
                        "district": district,
                        "start_utc": start,
                        "end_utc": end,
                        "boost": float(round(self.rng.uniform(1.15, 1.4), 3)),
                    }
                )
                seq += 1
        return events

    # -- demand -----------------------------------------------------------

    def build_demand(
        self,
        stations: list[dict],
        pairs: list[tuple[str, str]],
        weather: dict[str, dict],
        events: list[dict],
    ) -> dict[str, np.ndarray]:
        tcfg = self.cfg["tariff"]
        step = tcfg["step"]
        step_day = np.datetime64(step["date"], "D")
        stepped = {sid for sid, d in pairs if d in set(step["districts"])}
        base_price = tcfg["base_price_by_district"]

        event_boost = {d: np.ones(self.n_hours) for d in sorted({p[1] for p in pairs})}
        for ev in events:
            mask = (self.hours >= ev["start_utc"]) & (self.hours <= ev["end_utc"])
            event_boost[ev["district"]][mask] = ev["boost"]

        heat_mask = np.ones(self.n_hours)
        heatwave = self.cfg.get("heatwave") or {}
        if heatwave:
            hw_start = np.datetime64(heatwave["start"], "h")
            hw_end = np.datetime64(heatwave["end"], "h") + np.timedelta64(23, "h")
            window = (self.hours >= hw_start) & (self.hours <= hw_end)
            heat_mask[window & (self.hour_of_day >= 6) & (self.hour_of_day < 11)] = 0.85
            heat_mask[window & (self.hour_of_day >= 17) & (self.hour_of_day < 23)] = 1.15

        annual = 1 + 0.06 * np.sin(2 * np.pi * (np.arange(self.n_hours) - 190 * 24) / (365.25 * 24))
        holiday_days = {np.datetime64(d, "D") for d in PUBLIC_HOLIDAYS}
        is_holiday = np.isin(self.hours.astype("datetime64[D]"), list(holiday_days))
        school_days: set[np.datetime64] = set()
        for start, end, _ in SCHOOL_BREAKS:
            school_days |= set(
                np.arange(
                    np.datetime64(start, "D"),
                    np.datetime64(end, "D") + np.timedelta64(1, "D"),
                    dtype="datetime64[D]",
                ).tolist()
            )
        is_school = np.isin(self.hours.astype("datetime64[D]"), list(school_days))

        demand: dict[str, np.ndarray] = {}
        for station in stations:
            sid, district, poi = (
                station["station_id"],
                station["district"],
                station["poi_category"],
            )
            capacity = station["capacity_kw"]
            visible = self.hours >= np.datetime64(station["active_from"], "h")

            price_ratio = np.ones(self.n_hours)
            if sid in stepped:
                day_index = (self.hours.astype("datetime64[D]") - step_day).astype(int)
                ramp = np.clip(day_index / step["ramp_days"], 0.0, 1.0)
                price = np.where(
                    day_index >= 0,
                    base_price[district] + step["surcharge_eur_kwh"],
                    base_price[district],
                )
                effect = np.exp(step["elasticity"] * np.log(price / base_price[district]))
                price_ratio = 1 + ramp * (effect - 1)

            shape = UTILIZATION * POI_PROFILE[poi][self.hour_of_day]
            shape = shape * np.where(self.is_weekend, WEEKEND_FACTOR[poi], 1.0)
            shape = shape * np.where(is_holiday, HOLIDAY_FACTOR[poi], 1.0)
            shape = shape * np.where(is_school, SCHOOL_FACTOR[poi], 1.0)

            temp = weather[district]["temperature_c"]
            precip = weather[district]["precipitation_mm"]
            weather_factor = (
                1
                + 0.004 * np.maximum(0.0, 15.0 - temp)
                + 0.006 * np.maximum(0.0, temp - 24.0)
                + 0.05 * (precip > 0)
            )

            noise = self.rng.lognormal(0.0, 0.08, self.n_hours)
            fixed_effect = self.rng.normal(1.0, 0.05)

            values = (
                capacity
                * fixed_effect
                * shape
                * annual
                * weather_factor
                * event_boost[district]
                * heat_mask
                * price_ratio
                * noise
            )
            values = np.clip(np.round(values, 3), 0.0, capacity)
            values[~visible] = np.nan
            demand[sid] = values
        return demand

    # -- output -----------------------------------------------------------

    def generate(self, out_dir: Path) -> list[Path]:
        """Write the release data partitions; return the file list."""
        out_dir = Path(out_dir)
        stations, pairs = self.build_stations()
        districts = sorted({p[1] for p in pairs})
        weather, forecasts = self.build_weather(districts)
        events = self.build_events(districts)
        demand = self.build_demand(stations, pairs, weather, events)

        written: list[Path] = []

        def emit(table: pa.Table, rel_path: Path) -> None:
            path = out_dir / "data" / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(table, path, compression="zstd", version="2.6")
            written.append(path)

        emit(
            pa.table(
                {
                    "station_id": [s["station_id"] for s in stations],
                    "district": [s["district"] for s in stations],
                    "poi_category": [s["poi_category"] for s in stations],
                    "capacity_kw": [s["capacity_kw"] for s in stations],
                    "active_from": pa.array(
                        [_us_scalar(np.datetime64(s["active_from"], "h")) for s in stations],
                        type=TS_TYPE,
                    ),
                    "available_at": pa.array(
                        [_us_scalar(np.datetime64(s["active_from"], "h")) for s in stations],
                        type=TS_TYPE,
                    ),
                }
            ),
            Path("stations/part-0000.parquet"),
        )

        tcfg = self.cfg["tariff"]
        step = tcfg["step"]
        tariff_rows: list[tuple[str, int, float]] = []
        base_start = _us_scalar(np.datetime64(self.cfg["stations"]["active_from_default"], "h"))
        for station, district in pairs:
            base = tcfg["base_price_by_district"][district]
            tariff_rows.append((station, base_start, base))
            if district in set(step["districts"]):
                tariff_rows.append(
                    (
                        station,
                        _us_scalar(np.datetime64(step["date"], "h")),
                        round(base + step["surcharge_eur_kwh"], 4),
                    )
                )
        tariff_rows.sort(key=lambda r: (r[0], r[1]))
        emit(
            pa.table(
                {
                    "station_id": [r[0] for r in tariff_rows],
                    "effective_from": pa.array([r[1] for r in tariff_rows], type=TS_TYPE),
                    "price_per_kwh": [r[2] for r in tariff_rows],
                    "available_at": pa.array([r[1] for r in tariff_rows], type=TS_TYPE),
                }
            ),
            Path("tariffs/part-0000.parquet"),
        )

        holiday_names = [PUBLIC_HOLIDAYS.get(str(d)) for d in self.days]
        school = np.zeros(self.n_days, dtype=bool)
        for start, end, _ in SCHOOL_BREAKS:
            school |= (self.days >= np.datetime64(start, "D")) & (
                self.days <= np.datetime64(end, "D")
            )
        calendar_available = pa.array(
            [
                int(
                    datetime.combine(
                        date.fromisoformat(str(d)),
                        datetime.min.time(),
                        tzinfo=ISSUE_TIMEZONE,
                    ).timestamp()
                    * 1_000_000
                )
                for d in self.days
            ],
            type=TS_TYPE,
        )
        emit(
            pa.table(
                {
                    "date": pa.array(
                        [date.fromisoformat(str(d)) for d in self.days], type=pa.date32()
                    ),
                    "name": pa.array(holiday_names, type=pa.string()),
                    "is_public_holiday": pa.array(
                        [n is not None for n in holiday_names], type=pa.bool_()
                    ),
                    "is_school_break": pa.array(school, type=pa.bool_()),
                    "available_at": calendar_available,
                }
            ),
            Path("holidays/part-0000.parquet"),
        )

        emit(
            pa.table(
                {
                    "event_id": [e["event_id"] for e in events],
                    "district": [e["district"] for e in events],
                    "start_utc": pa.array(
                        [_us_scalar(e["start_utc"]) for e in events], type=TS_TYPE
                    ),
                    "end_utc": pa.array([_us_scalar(e["end_utc"]) for e in events], type=TS_TYPE),
                    "boost": [e["boost"] for e in events],
                    "available_at": pa.array(
                        [_us_scalar(e["start_utc"] - np.timedelta64(7, "D")) for e in events],
                        type=TS_TYPE,
                    ),
                }
            ),
            Path("events/part-0000.parquet"),
        )

        for year in sorted({int(str(h)[:4]) for h in self.hours}):
            mask = (self.hours.astype("datetime64[Y]").astype(int) + 1970) == year
            tables = []
            for district in districts:
                tables.append(
                    pa.table(
                        {
                            "district": [district] * int(mask.sum()),
                            "hour_utc": _ts(self.hours[mask]),
                            "temperature_c": weather[district]["temperature_c"][mask],
                            "precipitation_mm": weather[district]["precipitation_mm"][mask],
                            "available_at": _ts(self.hours[mask] + np.timedelta64(1, "h")),
                        }
                    )
                )
            emit(
                pa.concat_tables(tables),
                Path(f"weather_obs/year={year}/part-0000.parquet"),
            )

        fcst_tables: dict[str, list[pa.Table]] = {}
        for district in districts:
            for fc in forecasts[district]:
                month = str(fc["ref_day"])[:7]
                ref_hours = _us(
                    fc["ref_day"].astype("datetime64[h]") + np.arange(24).astype("timedelta64[h]")
                )
                fcst_tables.setdefault(month, []).append(
                    pa.table(
                        {
                            "district": [district] * 24,
                            "issue_at": pa.array([fc["issue_us"]] * 24, type=TS_TYPE),
                            "reference_hour_utc": pa.array(ref_hours, type=TS_TYPE),
                            "temperature_c": fc["temperature_c"],
                            "precipitation_mm": fc["precipitation_mm"],
                            "available_at": pa.array([fc["issue_us"]] * 24, type=TS_TYPE),
                        }
                    )
                )
        for month in sorted(fcst_tables):
            emit(
                pa.concat_tables(fcst_tables[month]),
                Path(f"weather_fcst/issue_month={month}/part-0000.parquet"),
            )

        for year in sorted({int(str(h)[:4]) for h in self.hours}):
            mask = (self.hours.astype("datetime64[Y]").astype(int) + 1970) == year
            tables = []
            for station in stations:
                values = demand[station["station_id"]][mask]
                keep = ~np.isnan(values)
                if not keep.any():
                    continue  # late stations have no rows before active_from
                tables.append(
                    pa.table(
                        {
                            "station_id": pa.array(
                                [station["station_id"]] * int(keep.sum()), type=pa.string()
                            ),
                            "hour_utc": _ts(self.hours[mask][keep]),
                            "demand_kwh": values[keep],
                            "available_at": _ts(self.hours[mask][keep] + np.timedelta64(2, "h")),
                        }
                    )
                )
            if tables:
                emit(
                    pa.concat_tables(tables),
                    Path(f"demand/year={year}/part-0000.parquet"),
                )

        return written
