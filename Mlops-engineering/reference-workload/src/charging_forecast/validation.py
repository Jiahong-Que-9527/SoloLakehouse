"""Dataset validation suite (M01).

Checks schema, ranges, per-station continuity and regime invariants against
a release directory. The suite is the M01 Release Gate input: it must fail
loudly on seeded corruption and pass on the clean release. Thresholds come
from the frozen config, never from ad-hoc code values.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .contract import TABLE_GRAIN, TABLE_SCHEMAS, issue_time_utc

US_HOUR = 3_600_000_000

_PA_TYPES = {
    "string": pa.string(),
    "float64": pa.float64(),
    "bool": pa.bool_(),
    "date32": pa.date32(),
    "timestamp[us, tz=UTC]": pa.timestamp("us", tz="UTC"),
}


class CheckResult(NamedTuple):
    name: str
    passed: bool
    detail: str


def read_table(release_dir: Path, name: str) -> pa.Table:
    """Read one logical table across all its partitions (sorted for stability)."""
    root = Path(release_dir) / "data" / name
    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"no parquet partitions for table {name!r} under {root}")
    return pa.concat_tables([pq.read_table(p) for p in paths])


def _col_us(table: pa.Table, column: str) -> np.ndarray:
    """Timestamp column as int64 microseconds since the epoch."""
    return table[column].cast(pa.int64()).to_numpy()


def validate_release(release_dir: Path, cfg: dict) -> list[CheckResult]:
    release_dir = Path(release_dir)
    tables = {name: read_table(release_dir, name) for name in TABLE_SCHEMAS}
    results: list[CheckResult] = []

    # 1. Schema checks.
    for name, schema in TABLE_SCHEMAS.items():
        actual = tables[name].schema
        expected_names = [c for c, _ in schema]
        expected_types = [_PA_TYPES[t] for _, t in schema]
        ok = actual.names == expected_names and all(
            actual.field(i).type == expected_types[i] for i in range(len(expected_names))
        )
        results.append(
            CheckResult(
                f"schema_{name}",
                ok,
                f"columns {actual.names}" if ok else f"expected {expected_names}",
            )
        )

    # 2. Grain uniqueness.
    for name, grain in TABLE_GRAIN.items():
        table = tables[name]
        keys = list(zip(*(table[c].to_pylist() for c in grain), strict=False))
        dupes = len(keys) - len(set(keys))
        results.append(
            CheckResult(
                f"grain_unique_{name}",
                dupes == 0,
                f"{len(keys)} rows, {dupes} duplicate grain keys",
            )
        )

    # 3. Value ranges.
    stations = tables["stations"]
    capacity = dict(
        zip(stations["station_id"].to_pylist(), stations["capacity_kw"].to_pylist(), strict=False)
    )
    demand = tables["demand"]
    dvals = demand["demand_kwh"].to_numpy()
    dcaps = np.array([capacity[s] for s in demand["station_id"].to_pylist()])
    in_range = bool(np.all((dvals >= 0.0) & (dvals <= dcaps)))
    results.append(
        CheckResult(
            "range_demand",
            in_range,
            f"min {dvals.min():.1f}, max {dvals.max():.1f} kWh vs capacity "
            f"max {dcaps.min():.0f}-{dcaps.max():.0f}",
        )
    )

    obs = tables["weather_obs"]
    otemp = obs["temperature_c"].to_numpy()
    oprc = obs["precipitation_mm"].to_numpy()
    ok = bool(np.all((otemp >= -35.0) & (otemp <= 45.0)) and np.all(oprc >= 0.0))
    results.append(
        CheckResult(
            "range_weather_obs",
            ok,
            f"temp [{otemp.min():.1f}, {otemp.max():.1f}] C, precip max {oprc.max():.2f} mm",
        )
    )

    fcst = tables["weather_fcst"]
    ftemp = fcst["temperature_c"].to_numpy()
    fprc = fcst["precipitation_mm"].to_numpy()
    ok = bool(np.all((ftemp >= -35.0) & (ftemp <= 45.0)) and np.all(fprc >= 0.0))
    results.append(
        CheckResult(
            "range_weather_fcst",
            ok,
            f"temp [{ftemp.min():.1f}, {ftemp.max():.1f}] C, precip max {fprc.max():.2f} mm",
        )
    )

    tariffs = tables["tariffs"]
    price = tariffs["price_per_kwh"].to_numpy()
    results.append(
        CheckResult(
            "range_tariff",
            bool(np.all(price > 0.0)),
            f"price [{price.min():.3f}, {price.max():.3f}] EUR/kWh",
        )
    )

    # 4. Demand continuity per station (hourly, from active_from to window end).
    window_start = _col_us(demand, "hour_utc").min()
    window_end = _col_us(demand, "hour_utc").max()
    active_us = dict(
        zip(
            stations["station_id"].to_pylist(),
            _col_us(stations, "active_from").tolist(),
            strict=False,
        )
    )
    hours_by_station: dict[str, np.ndarray] = {}
    for sid, hour in zip(
        demand["station_id"].to_pylist(), _col_us(demand, "hour_utc").tolist(), strict=False
    ):
        hours_by_station.setdefault(sid, []).append(hour)
    failures = []
    for sid in sorted(hours_by_station):
        got = np.sort(np.array(hours_by_station[sid]))
        expect0 = max(active_us[sid], window_start)
        want = np.arange(expect0, window_end + US_HOUR, US_HOUR)
        if len(got) != len(want) or not np.array_equal(got, want):
            failures.append(f"{sid}: {len(got)} rows, expected {len(want)}")
    results.append(
        CheckResult(
            "continuity_demand",
            not failures,
            "; ".join(failures[:5])
            if failures
            else f"all {len(hours_by_station)} stations continuous",
        )
    )

    # 5. Realized weather continuity per district.
    obs_hours: dict[str, np.ndarray] = {}
    for district, hour in zip(
        obs["district"].to_pylist(), _col_us(obs, "hour_utc").tolist(), strict=False
    ):
        obs_hours.setdefault(district, []).append(hour)
    failures = []
    for district in sorted(obs_hours):
        got = np.sort(np.array(obs_hours[district]))
        want = np.arange(window_start, window_end + US_HOUR, US_HOUR)
        if len(got) != len(want) or not np.array_equal(got, want):
            failures.append(f"{district}: {len(got)} rows, expected {len(want)}")
    results.append(
        CheckResult(
            "continuity_weather_obs",
            not failures,
            "; ".join(failures[:5]) if failures else f"all {len(obs_hours)} districts continuous",
        )
    )

    # 6. Forecast integrity: issue time is 06:00 Europe/Berlin, references are
    # the next day's 24 hours, exactly 24 rows per (district, issue).
    issue_by_key: dict[tuple, set] = {}
    for district, issue, ref in zip(
        fcst["district"].to_pylist(),
        _col_us(fcst, "issue_at").tolist(),
        _col_us(fcst, "reference_hour_utc").tolist(),
        strict=False,
    ):
        issue_by_key.setdefault((district, issue), set()).add(ref)
    failures = []
    for (district, issue), refs in sorted(issue_by_key.items()):
        day = datetime.fromtimestamp(issue / 1_000_000, tz=UTC).date()
        expected_issue = int(issue_time_utc(day).timestamp() * 1_000_000)
        next_midnight = datetime.combine(
            day + timedelta(days=1), time(0, 0), tzinfo=UTC
        ).timestamp()
        expected_refs = {int(next_midnight * 1_000_000) + h * US_HOUR for h in range(24)}
        if issue != expected_issue:
            failures.append(f"{district}@{issue}: issue time is not 06:00 Europe/Berlin")
        elif refs != expected_refs:
            failures.append(f"{district}@{issue}: {len(refs)} reference hours, wrong set")
    results.append(
        CheckResult(
            "forecast_integrity",
            not failures,
            "; ".join(failures[:3])
            if failures
            else f"{len(issue_by_key)} district-issues well-formed",
        )
    )

    # 7. Availability columns (point-in-time discipline baked into the data).
    delay = int(cfg.get("ingestion_delay_hours", 1))
    hour_us = _col_us(demand, "hour_utc")
    avail_us = _col_us(demand, "available_at")
    ok = bool(np.all(avail_us == hour_us + (1 + delay) * US_HOUR))
    results.append(
        CheckResult(
            "availability_demand",
            ok,
            "available_at = hour + close(1h) + ingestion delay" if ok else "wrong available_at",
        )
    )
    obs_hour_us = _col_us(obs, "hour_utc")
    obs_avail_us = _col_us(obs, "available_at")
    ok = bool(np.all(obs_avail_us == obs_hour_us + delay * US_HOUR))
    results.append(
        CheckResult(
            "availability_weather_obs",
            ok,
            "available_at = hour + observation delay" if ok else "wrong available_at",
        )
    )
    ok = bool(np.all(_col_us(fcst, "available_at") == _col_us(fcst, "issue_at")))
    results.append(
        CheckResult(
            "availability_weather_fcst",
            ok,
            "available_at = issue_at" if ok else "wrong available_at",
        )
    )

    # 8. Regime invariants: tariff step lands on the announced date.
    tcfg = cfg["tariff"]
    step = tcfg["step"]
    step_us = int(np.datetime64(step["date"], "h").astype("datetime64[us]").astype("int64"))
    base_start = int(
        np.datetime64(cfg["stations"]["active_from_default"], "h")
        .astype("datetime64[us]")
        .astype("int64")
    )
    district_of = dict(
        zip(stations["station_id"].to_pylist(), stations["district"].to_pylist(), strict=False)
    )
    rows_by_station: dict[str, list[tuple]] = {}
    for sid, eff, price in zip(
        tariffs["station_id"].to_pylist(),
        _col_us(tariffs, "effective_from").tolist(),
        tariffs["price_per_kwh"].to_pylist(),
        strict=False,
    ):
        rows_by_station.setdefault(sid, []).append((eff, price))
    failures = []
    for sid in sorted(rows_by_station):
        stepped = district_of[sid] in set(step["districts"])
        rows = sorted(rows_by_station[sid])
        base = tcfg["base_price_by_district"][district_of[sid]]
        if stepped:
            if len(rows) != 2 or rows[0][0] != base_start or rows[1][0] != step_us:
                failures.append(f"{sid}: stepped station must have base + {step['date']} rows")
            elif abs(rows[1][1] - (base + step["surcharge_eur_kwh"])) > 1e-9:
                failures.append(f"{sid}: stepped price does not match base + surcharge")
        else:
            if len(rows) != 1 or rows[0][0] != base_start:
                failures.append(f"{sid}: non-stepped station must have exactly the base row")
    results.append(
        CheckResult(
            "regime_tariff_step",
            not failures,
            "; ".join(failures[:5]) if failures else f"tariff schedule matches {step['date']} step",
        )
    )

    # 9. Regime invariants: cold-start stations have no earlier rows.
    late: dict[str, str] = {}
    for day, sids in sorted(cfg["stations"].get("active_from_late", {}).items()):
        for sid in sids:
            late[sid] = day
    failures = []
    for sid, day in sorted(late.items()):
        if sid not in hours_by_station:
            failures.append(f"{sid}: no demand rows at all")
            continue
        expected_start = int(np.datetime64(day, "h").astype("datetime64[us]").astype("int64"))
        if min(hours_by_station[sid]) != expected_start:
            failures.append(f"{sid}: first row is not {day}T00:00Z")
    results.append(
        CheckResult(
            "regime_cold_start",
            not failures,
            "; ".join(failures[:5])
            if failures
            else f"{len(late)} late stations start on their active_from",
        )
    )

    # 10. Regime invariant: heatwave week is measurably hotter than the
    # adjacent weeks (skipped when the release window does not overlap it).
    hw = cfg.get("heatwave") or {}
    if hw:
        hw_start = int(np.datetime64(hw["start"], "h").astype("datetime64[us]").astype("int64"))
        hw_end = (
            int(np.datetime64(hw["end"], "h").astype("datetime64[us]").astype("int64"))
            + 23 * US_HOUR
        )
        if hw_end >= window_start and hw_start <= window_end:
            obs_hour = _col_us(obs, "hour_utc")
            temp = obs["temperature_c"].to_numpy()
            inside = (obs_hour >= hw_start) & (obs_hour <= hw_end)
            before = (obs_hour >= hw_start - 7 * 24 * US_HOUR) & (obs_hour < hw_start)
            after = (obs_hour > hw_end) & (obs_hour <= hw_end + 7 * 24 * US_HOUR)
            adjacent = before | after
            if inside.any() and adjacent.any():
                delta = float(temp[inside].mean() - temp[adjacent].mean())
                results.append(
                    CheckResult(
                        "regime_heatwave",
                        delta >= 5.0,
                        f"heatwave week {delta:+.1f} C vs adjacent weeks (threshold +5.0)",
                    )
                )

    return results
