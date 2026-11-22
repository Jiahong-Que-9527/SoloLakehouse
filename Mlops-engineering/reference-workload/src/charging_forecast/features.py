"""Point-in-time feature pipeline (M02).

Implements docs/feature-contract.md v1 with one transform and two entry
points: training and serving both read through this module. A feature row is
keyed (station_id, hour_utc) and stamped available_at = T, the issue time it
was built for. The builder reads content-bearing families (demand lags,
weather forecasts, station attributes) only through rows stamped
available_at <= T; published schedules (calendar, tariffs, events) join by
schedule semantics per the contract. Lag and rolling windows are fixed clock
ranges anchored at T, so availability stamping changes readability only —
tests/test_leakage.py enforces it — and two materializations from the same
data release are byte-identical (no wall-clock value enters the output).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .contract import TS, git_commit, issue_time_utc, sha256_file
from .validation import read_table

US_HOUR = 3_600_000_000
US_DAY = 86_400_000_000
TARGET_HOURS = 24
FEATURES_SCHEMA_VERSION = "charging-features-v1"

# The committed feature schema (docs/feature-contract.md, family table).
FEATURES_SCHEMA: list[tuple[str, str]] = [
    ("station_id", "string"),
    ("hour_utc", TS),
    ("available_at", TS),
    ("hour_of_day", "int8"),
    ("day_of_week", "int8"),
    ("is_public_holiday", "bool"),
    ("is_school_break", "bool"),
    ("district", "string"),
    ("poi_category", "string"),
    ("capacity_kw", "float64"),
    ("days_active", "float64"),
    ("demand_lag_24h", "float64"),
    ("demand_lag_168h", "float64"),
    ("demand_rolling_7d_mean", "float64"),
    ("demand_latest", "float64"),
    ("fcst_temperature_c", "float64"),
    ("fcst_precipitation_mm", "float64"),
    ("price_current", "float64"),
    ("price_at_target", "float64"),
    ("is_event_active", "bool"),
    ("event_boost", "float64"),
]

_PA_TYPES = {
    "string": pa.string(),
    "int8": pa.int8(),
    "float64": pa.float64(),
    "bool": pa.bool_(),
    "timestamp[us, tz=UTC]": pa.timestamp("us", tz="UTC"),
}


def feature_release_id(cfg: dict) -> str:
    """Deterministic release ID: schema major + source data release."""
    major = FEATURES_SCHEMA_VERSION.rsplit("-v", 1)[-1]
    return f"feat-v{major}-{cfg['release_id']}"


def _col_us(table: pa.Table, column: str) -> np.ndarray:
    """Timestamp column as int64 microseconds since the epoch."""
    return table[column].cast(pa.int64()).to_numpy()


def _pa_schema() -> pa.Schema:
    return pa.schema([pa.field(n, _PA_TYPES[t]) for n, t in FEATURES_SCHEMA])


class FeatureBuilder:
    """Build point-in-time feature rows from one manifested data release."""

    def __init__(self, release_dir: Path, cfg: dict, *, verify_source: bool = True):
        self.release_dir = Path(release_dir)
        self.cfg = cfg
        self.delay_h = int(cfg.get("ingestion_delay_hours", 1))
        self.manifest = self._read_source_manifest()
        if verify_source:
            self._verify_source()
        self._load_sources()

    # -- source loading ----------------------------------------------------

    def _read_source_manifest(self) -> dict:
        path = self.release_dir / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"source release has no manifest.json: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _verify_source(self) -> None:
        for entry in self.manifest["files"]:
            path = self.release_dir / entry["path"]
            if sha256_file(path) != entry["sha256"]:
                raise ValueError(f"source file changed since the release: {entry['path']}")

    def _load_sources(self) -> None:
        release = self.release_dir

        stations = read_table(release, "stations")
        order = np.argsort(np.array(stations["station_id"].to_pylist()), kind="stable")
        self.station_rows: list[dict] = []
        for i in order.tolist():
            self.station_rows.append(
                {
                    "station_id": stations["station_id"][i].as_py(),
                    "district": stations["district"][i].as_py(),
                    "poi_category": stations["poi_category"][i].as_py(),
                    "capacity_kw": float(stations["capacity_kw"][i].as_py()),
                    "active_us": int(_col_us(stations, "active_from")[i]),
                }
            )

        self.demand: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        table = read_table(release, "demand")
        hours_all = _col_us(table, "hour_utc")
        vals_all = table["demand_kwh"].to_numpy()
        avail_all = _col_us(table, "available_at")
        grouped: dict[str, list[int]] = {}
        for idx, sid in enumerate(table["station_id"].to_pylist()):
            grouped.setdefault(sid, []).append(idx)
        for sid, idxs in grouped.items():
            idxs_arr = np.array(idxs)
            sort = np.argsort(hours_all[idxs_arr], kind="stable")
            self.demand[sid] = (
                hours_all[idxs_arr][sort],
                vals_all[idxs_arr][sort],
                avail_all[idxs_arr][sort],
            )
        self.demand_base_us = int(hours_all.min())
        self.demand_last_us = int(hours_all.max())

        self.tariffs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        table = read_table(release, "tariffs")
        eff_all = _col_us(table, "effective_from")
        price_all = table["price_per_kwh"].to_numpy()
        grouped = {}
        for idx, sid in enumerate(table["station_id"].to_pylist()):
            grouped.setdefault(sid, []).append(idx)
        for sid, idxs in grouped.items():
            idxs_arr = np.array(idxs)
            sort = np.argsort(eff_all[idxs_arr], kind="stable")
            self.tariffs[sid] = (eff_all[idxs_arr][sort], price_all[idxs_arr][sort])

        self.holidays_public: dict[int, bool] = {}
        self.holidays_school: dict[int, bool] = {}
        table = read_table(release, "holidays")
        epoch = date(1970, 1, 1)
        for d, pub, school in zip(
            table["date"].to_pylist(),
            table["is_public_holiday"].to_pylist(),
            table["is_school_break"].to_pylist(),
            strict=False,
        ):
            key = (d - epoch).days
            self.holidays_public[key] = bool(pub)
            self.holidays_school[key] = bool(school)

        self.events: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        table = read_table(release, "events")
        n_hours = (self.demand_last_us - self.demand_base_us) // US_HOUR + 1
        for district in sorted({r["district"] for r in self.station_rows}):
            self.events[district] = (
                np.zeros(n_hours, dtype=bool),
                np.ones(n_hours, dtype=np.float64),
            )
        for sid_row, start, end, boost in zip(
            table["district"].to_pylist(),
            _col_us(table, "start_utc").tolist(),
            _col_us(table, "end_utc").tolist(),
            table["boost"].to_pylist(),
            strict=False,
        ):
            lo = (start - self.demand_base_us) // US_HOUR
            hi = (end - self.demand_base_us) // US_HOUR
            active, boosts = self.events[sid_row]
            active[lo : hi + 1] = True
            boosts[lo : hi + 1] = np.maximum(boosts[lo : hi + 1], boost)

        self.fcst: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        table = read_table(release, "weather_fcst")
        ref_all = _col_us(table, "reference_hour_utc")
        issue_all = _col_us(table, "available_at")
        temp_all = table["temperature_c"].to_numpy()
        prec_all = table["precipitation_mm"].to_numpy()
        order = np.lexsort((issue_all, ref_all))
        districts_sorted = table["district"].take(pa.array(order)).to_pylist()
        grouped: dict[str, list[int]] = {}
        for pos, district in enumerate(districts_sorted):
            grouped.setdefault(district, []).append(int(order[pos]))
        for district, pos in grouped.items():
            pos_arr = np.array(pos)
            self.fcst[district] = (
                ref_all[pos_arr],
                issue_all[pos_arr],
                temp_all[pos_arr],
                prec_all[pos_arr],
            )
        self.fcst_last_ref_us = int(ref_all.max())

    # -- point-in-time reads -------------------------------------------------

    def _demand_value_at(self, sid: str, hour_us: int, t_us: int) -> float:
        """One demand value, readable only if its row is stamped <= T."""
        hours, vals, avail = self.demand[sid]
        idx = int(np.searchsorted(hours, hour_us))
        if idx < len(hours) and hours[idx] == hour_us and avail[idx] <= t_us:
            return float(vals[idx])
        return float("nan")

    def _tariff_at(self, sid: str, at_us: int) -> float:
        eff, price = self.tariffs[sid]
        idx = int(np.searchsorted(eff, at_us, side="right")) - 1
        if idx < 0:
            return float("nan")
        return float(price[idx])

    def _forecasts_for(self, district: str, target_us: np.ndarray, t_us: int) -> dict[int, int]:
        """Readable forecast rows for the target hours: latest issue wins.

        Every picked row must be the day-ahead issue for its reference day
        (issued at 06:00 Europe/Berlin the day before) — a row joined under a
        wrong reference time violates the convention and fails the build.
        """
        refs, issues, _temps, _precs = self.fcst[district]
        lo = int(np.searchsorted(refs, int(target_us[0]), side="left"))
        hi = int(np.searchsorted(refs, int(target_us[-1]) + 1, side="left"))
        mask = issues[lo:hi] <= t_us
        refs_r = refs[lo:hi][mask]
        pos_r = np.flatnonzero(mask)
        picked: dict[int, int] = {}
        for j, ref in enumerate(refs_r.tolist()):
            picked[ref] = int(pos_r[j]) + lo  # (ref, issue)-sorted: last wins
        for ref, pos in picked.items():
            ref_day = datetime.fromtimestamp(ref / 1_000_000, tz=UTC).date()
            expected_us = int(issue_time_utc(ref_day - timedelta(days=1)).timestamp() * 1_000_000)
            if int(issues[pos]) != expected_us:
                raise ValueError(
                    f"forecast row for reference {ref} in {district} is not the day-ahead "
                    f"issue for that reference day (issue {int(issues[pos])}, "
                    f"expected {expected_us})"
                )
        return picked

    # -- build ----------------------------------------------------------------

    def issue_time_us(self, issue_day: date) -> int:
        return int(issue_time_utc(issue_day).timestamp() * 1_000_000)

    def target_hours_us(self, issue_day: date) -> np.ndarray:
        """The 24 target hours of the next UTC day (contract, target window)."""
        start = datetime.combine(issue_day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        start_us = int(start.timestamp() * 1_000_000)
        return start_us + np.arange(TARGET_HOURS, dtype=np.int64) * US_HOUR

    def build_issue(self, issue_day: date) -> pa.Table:
        t_us = self.issue_time_us(issue_day)
        target_us = self.target_hours_us(issue_day)
        if int(target_us[-1]) > self.fcst_last_ref_us:
            raise ValueError(
                f"issue day {issue_day} is beyond forecast coverage "
                f"(last reference hour {self.fcst_last_ref_us})"
            )

        readable_end_us = t_us - (1 + self.delay_h) * US_HOUR
        lag24_us = t_us - 24 * US_HOUR
        lag168_us = t_us - 168 * US_HOUR
        roll_lo_us = t_us - 168 * US_HOUR

        columns: dict[str, list] = {name: [] for name, _ in FEATURES_SCHEMA}
        for station in self.station_rows:  # sorted by station_id
            sid = station["station_id"]
            if station["active_us"] > t_us:
                continue  # station row not readable yet: no feature rows
            hours, vals, avail = self.demand[sid]

            hour_of_day = ((target_us // US_HOUR) % 24).astype(np.int8)
            day_of_week = ((target_us // US_DAY) + 3) % 7
            date_keys = (target_us // US_DAY).tolist()
            is_pub = np.array([self.holidays_public.get(d, False) for d in date_keys])
            is_school = np.array([self.holidays_school.get(d, False) for d in date_keys])

            roll_mask = (hours >= roll_lo_us) & (hours <= readable_end_us) & (avail <= t_us)
            roll_vals = vals[roll_mask]
            rolling_mean = float(np.mean(roll_vals)) if roll_vals.size else float("nan")

            eff, price = self.tariffs[sid]
            t_idx = np.searchsorted(eff, target_us, side="right") - 1
            price_at_target = np.where(t_idx >= 0, price[np.maximum(t_idx, 0)], np.nan)

            active, boosts = self.events[station["district"]]
            e_idx = (target_us - self.demand_base_us) // US_HOUR

            picked = self._forecasts_for(station["district"], target_us, t_us)
            missing = [r for r in target_us.tolist() if r not in picked]
            if missing:
                raise ValueError(
                    f"issue {issue_day}: no readable forecast for {len(missing)} target "
                    f"hours, first missing reference {missing[0]}"
                )
            temp = np.array([self.fcst[station["district"]][2][picked[r]] for r in target_us])
            prec = np.array([self.fcst[station["district"]][3][picked[r]] for r in target_us])

            n = len(target_us)
            columns["station_id"].append([sid] * n)
            columns["hour_utc"].append(target_us)
            columns["available_at"].append(np.full(n, t_us, dtype=np.int64))
            columns["hour_of_day"].append(hour_of_day)
            columns["day_of_week"].append(day_of_week.astype(np.int8))
            columns["is_public_holiday"].append(is_pub)
            columns["is_school_break"].append(is_school)
            columns["district"].append([station["district"]] * n)
            columns["poi_category"].append([station["poi_category"]] * n)
            columns["capacity_kw"].append(np.full(n, station["capacity_kw"]))
            columns["days_active"].append(np.full(n, (t_us - station["active_us"]) / US_DAY))
            columns["demand_lag_24h"].append(np.full(n, self._demand_value_at(sid, lag24_us, t_us)))
            columns["demand_lag_168h"].append(
                np.full(n, self._demand_value_at(sid, lag168_us, t_us))
            )
            columns["demand_rolling_7d_mean"].append(np.full(n, rolling_mean))
            columns["demand_latest"].append(
                np.full(n, self._demand_value_at(sid, readable_end_us, t_us))
            )
            columns["fcst_temperature_c"].append(temp)
            columns["fcst_precipitation_mm"].append(prec)
            columns["price_current"].append(np.full(n, self._tariff_at(sid, t_us)))
            columns["price_at_target"].append(price_at_target)
            columns["is_event_active"].append(active[e_idx])
            columns["event_boost"].append(boosts[e_idx])

        data = {}
        for name, kind in FEATURES_SCHEMA:
            col = columns[name]
            if kind == TS:
                data[name] = pa.array(np.concatenate(col), type=_PA_TYPES[TS])
            elif kind in ("string",):
                data[name] = pa.array([v for chunk in col for v in chunk], type=pa.string())
            else:
                data[name] = pa.array(np.concatenate(col).astype(kind))
        return pa.table(data, schema=_pa_schema())

    # -- materialization -------------------------------------------------------

    def materialize(self, issue_start: date, issue_end: date, out_dir: Path) -> dict:
        """Build the issue range, write partitioned Parquet and the manifest."""
        out_dir = Path(out_dir)
        month_tables: dict[str, list[pa.Table]] = {}
        day = issue_start
        n_issues = 0
        while day <= issue_end:
            month = f"{day:%Y-%m}"
            month_tables.setdefault(month, []).append(self.build_issue(day))
            day += timedelta(days=1)
            n_issues += 1

        files: list[dict] = []
        for month in sorted(month_tables):
            table = pa.concat_tables(month_tables[month])
            rel = Path(f"issue_month={month}/part-0000.parquet")
            path = out_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(table, path, compression="zstd", version="2.6")
            files.append(
                {
                    "path": rel.as_posix(),
                    "rows": table.num_rows,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

        manifest = {
            "feature_release_id": feature_release_id(self.cfg),
            "kind": "features",
            "schema_version": FEATURES_SCHEMA_VERSION,
            "source_release_id": self.manifest["release_id"],
            "source_manifest_sha256": sha256_file(self.release_dir / "manifest.json"),
            "source_config_sha256": self.manifest["config_sha256"],
            "issue_start": issue_start.isoformat(),
            "issue_end": issue_end.isoformat(),
            "issues": n_issues,
            "source_commit": git_commit(out_dir),
            "columns": [list(col) for col in FEATURES_SCHEMA],
            "rows": sum(f["rows"] for f in files),
            "files": files,
        }
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return manifest


# -- read path -----------------------------------------------------------------


def _read_manifest(features_dir: Path) -> dict:
    path = Path(features_dir) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"features directory has no manifest.json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_schema_version(features_dir: Path) -> dict:
    """Schema gate (contract rule 3): refuse a different feature schema."""
    manifest = _read_manifest(features_dir)
    if manifest.get("schema_version") != FEATURES_SCHEMA_VERSION:
        raise ValueError(
            f"feature schema mismatch: manifest has {manifest.get('schema_version')!r}, "
            f"loader implements {FEATURES_SCHEMA_VERSION!r}"
        )
    expected = [name for name, _ in FEATURES_SCHEMA]
    if [col[0] for col in manifest.get("columns", [])] != expected:
        raise ValueError("feature manifest columns do not match the loader schema")
    return manifest


def _read_partitions_up_to(features_dir: Path, issue_day: date) -> pa.Table:
    """Scan partitions whose issue month is at or before the issue month."""
    limit = f"{issue_day:%Y-%m}"
    paths = sorted(
        p
        for p in Path(features_dir).rglob("*.parquet")
        if p.parent.name.replace("issue_month=", "") <= limit
    )
    if not paths:
        raise FileNotFoundError(f"no feature partitions at or before {limit} under {features_dir}")
    return pa.concat_tables([pq.read_table(p) for p in paths])


def load_issue_features(features_dir: Path, issue_day: date) -> pa.Table:
    """The one read path for training and serving (contract rule 1).

    Returns every materialized row readable at T, i.e. available_at <= T;
    rows stamped later are rejected (excluded). The shift test relies on
    this filter — reading the Parquet directly would bypass the contract.
    """
    check_schema_version(features_dir)
    table = _read_partitions_up_to(features_dir, issue_day)
    t_us = int(issue_time_utc(issue_day).timestamp() * 1_000_000)
    avail = _col_us(table, "available_at")
    return table.filter(avail <= t_us)


def load_training_features(features_dir: Path, issue_start: date, issue_end: date) -> pa.Table:
    """Bulk read path for training (contract rule 1: training and serving read
    through charging_forecast.features).

    The training split for issue day D is exactly the rows stamped
    available_at == T(D) — the same split check_fold_leakage verifies day by
    day, gathered here in one scan. Rows stamped at anything else cannot
    belong to an issue day in the range and are dropped by the stamp filter;
    an empty selection is refused loudly instead of silently training on
    nothing.
    """
    check_schema_version(features_dir)
    if issue_end < issue_start:
        raise ValueError(f"empty issue range: {issue_start}..{issue_end}")
    table = _read_partitions_up_to(features_dir, issue_end)
    avail = _col_us(table, "available_at")
    stamps = []
    day = issue_start
    while day <= issue_end:
        stamps.append(int(issue_time_utc(day).timestamp() * 1_000_000))
        day += timedelta(days=1)
    mask = np.isin(avail, np.array(stamps))
    if not mask.any():
        raise ValueError(
            f"no feature rows stamped at the issue times of {issue_start}..{issue_end} "
            f"under {features_dir}"
        )
    return table.filter(mask)


def check_fold_leakage(features_dir: Path, issue_day: date) -> tuple[bool, str]:
    """Acceptance check 3, per fold: inspect the raw split, not the filter.

    The split for issue date T is the set of rows stamped available_at == T.
    Three invariants must hold: every row inside the target window is stamped
    exactly at T (nothing readable after T, nothing missing the stamp); every
    row stamped at T describes a strictly future target hour inside the
    window; and the two selections agree, so no row escaped either check.
    """
    table = _read_partitions_up_to(features_dir, issue_day)
    t_us = int(issue_time_utc(issue_day).timestamp() * 1_000_000)
    start = datetime.combine(issue_day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    b_us = int(start.timestamp() * 1_000_000)
    window_end = b_us + TARGET_HOURS * US_HOUR

    avail = _col_us(table, "available_at")
    hours = _col_us(table, "hour_utc")
    in_window = (hours >= b_us) & (hours < window_end)
    stamped = avail == t_us

    rows_window = int(np.sum(in_window))
    rows_split = int(np.sum(stamped))
    if rows_window == 0 and rows_split == 0:
        return False, f"issue {issue_day}: no feature rows for the target window"

    late = int(np.sum(avail[in_window] > t_us))
    misstamped = int(np.sum(avail[in_window] != t_us))
    split_hours = hours[stamped]
    past_targets = int(np.sum(split_hours <= t_us))
    outside = int(np.sum((split_hours < b_us) | (split_hours >= window_end)))
    mismatched = rows_window != rows_split
    if late or misstamped or past_targets or outside or mismatched:
        return False, (
            f"issue {issue_day}: {late} rows stamped after T, {misstamped} not stamped "
            f"exactly at T, {past_targets} target hours at or before T, {outside} split "
            f"rows outside the target window, selections differ by "
            f"{abs(rows_window - rows_split)}"
        )
    return True, (
        f"issue {issue_day}: {rows_split} rows, all stamped at T, targets strictly future"
    )
