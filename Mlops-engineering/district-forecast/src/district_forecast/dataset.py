"""The derived district dataset (M09 domain contract).

Consumes the pinned `dataset-v001` release and aggregates the station-hour
demand to the district-hour grain. The derived release never mutates the
source: its lineage pins the source release by manifest SHA-256.

Availability semantics for the aggregate: a district-hour value is fully
known only when every contributing station value has arrived, so the
aggregate row's `available_at` is the maximum over its stations — the
honest point-in-time stamp for anything reading the district grain.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from .releases import build_file_manifest, git_commit, publish_release, read_json, sha256_file

TS = "timestamp[us, tz=UTC]"

DISTRICT_SCHEMA: list[tuple[str, str]] = [
    ("district", "string"),
    ("station_count", "int64"),
    ("capacity_kw_total", "float64"),
    ("poi_office", "int64"),
    ("poi_retail", "int64"),
    ("poi_residential", "int64"),
    ("poi_highway", "int64"),
    ("active_from", TS),
]

AGG_SCHEMA: list[tuple[str, str]] = [
    ("district", "string"),
    ("hour_utc", TS),
    ("demand_kwh", "float64"),
    ("station_count", "int64"),
    ("available_at", TS),
]


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for key in ("release_id", "schema_version", "source_release", "window", "districts"):
        if key not in cfg:
            raise ValueError(f"config missing required key {key!r}")
    cfg["_config_path"] = str(path)
    return cfg


def _write(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _read(source: Path, name: str, partition: str | None = None) -> pa.Table:
    directory = source / "data" / name
    tables = [pq.read_table(p) for p in sorted(directory.rglob("*.parquet"))]
    if not tables:
        raise ValueError(f"no parquet parts under {directory}")
    return pa.concat_tables(tables)


def district_attributes(stations: pa.Table, districts: list[str]) -> pa.Table:
    """One static row per district, aggregated from the station table."""
    rows = {name: [] for name, _ in DISTRICT_SCHEMA}
    for district in districts:
        mask = np.asarray(stations["district"].to_pylist()) == district
        if not mask.any():
            raise ValueError(f"district {district} has no stations")
        poi = np.asarray(stations["poi_category"].to_pylist())[mask]
        rows["district"].append(district)
        rows["station_count"].append(int(mask.sum()))
        rows["capacity_kw_total"].append(
            float(np.asarray(stations["capacity_kw"].to_numpy(), dtype=float)[mask].sum())
        )
        for cat in ("office", "retail", "residential", "highway"):
            rows[f"poi_{cat}"].append(int((poi == cat).sum()))
        active = min(stations["active_from"][i].as_py() for i in np.flatnonzero(mask).tolist())
        rows["active_from"].append(active)
    return pa.table({k: pa.array(v) for k, v in rows.items()})


def aggregate_demand(demand: pa.Table, stations: pa.Table, districts: list[str]) -> pa.Table:
    """Sum station-hour demand to district-hour; available_at = max over stations."""
    sid = np.asarray(demand["station_id"].to_pylist())
    hours = demand["hour_utc"].cast(pa.int64()).to_numpy()
    values = demand["demand_kwh"].to_numpy()
    avail = demand["available_at"].cast(pa.int64()).to_numpy()
    district_of = dict(
        zip(
            np.asarray(stations["station_id"].to_pylist()).tolist(),
            np.asarray(stations["district"].to_pylist()).tolist(),
            strict=True,
        )
    )
    unknown = sorted(set(sid.tolist()) - set(district_of))
    if unknown:
        raise ValueError(f"demand rows reference unknown stations: {unknown[:5]}")
    dist = np.array([district_of[s] for s in sid.tolist()])

    out = {name: [] for name, _ in AGG_SCHEMA}
    order = np.lexsort((hours, dist))
    dist_s, hours_s = dist[order], hours[order]
    values_s, avail_s = values[order], avail[order]
    starts = np.flatnonzero(
        np.concatenate(([True], (dist_s[1:] != dist_s[:-1]) | (hours_s[1:] != hours_s[:-1])))
    )
    ends = np.append(starts[1:], len(dist_s))
    for lo, hi in zip(starts, ends, strict=True):
        out["district"].append(str(dist_s[lo]))
        out["hour_utc"].append(int(hours_s[lo]))
        out["demand_kwh"].append(round(float(values_s[lo:hi].sum()), 6))
        out["station_count"].append(int(hi - lo))
        out["available_at"].append(int(avail_s[lo:hi].max()))
    table = pa.table(
        {
            "district": pa.array(out["district"], type=pa.string()),
            "hour_utc": pa.array(out["hour_utc"], type=pa.int64()).cast(pa.int64()),
            "demand_kwh": pa.array(out["demand_kwh"], type=pa.float64()),
            "station_count": pa.array(out["station_count"], type=pa.int64()),
            "available_at": pa.array(out["available_at"], type=pa.int64()).cast(
                pa.timestamp("us", tz="UTC")
            ),
        }
    )
    table = table.set_column(
        1, "hour_utc", table.column("hour_utc").cast(pa.timestamp("us", tz="UTC"))
    )
    return table.sort_by([("district", "ascending"), ("hour_utc", "ascending")])


def district_tariffs(tariffs: pa.Table, stations: pa.Table) -> pa.Table:
    """Collapse the station tariff schedule to districts, asserting uniformity."""
    district_of = dict(
        zip(
            np.asarray(stations["station_id"].to_pylist()).tolist(),
            np.asarray(stations["district"].to_pylist()).tolist(),
            strict=True,
        )
    )
    dist = np.array([district_of[s] for s in np.asarray(tariffs["station_id"].to_pylist())])
    eff = tariffs["effective_from"].cast(pa.int64()).to_numpy()
    price = tariffs["price_per_kwh"].to_numpy()
    avail = tariffs["available_at"].cast(pa.int64()).to_numpy()

    out = {"district": [], "effective_from": [], "price_per_kwh": [], "available_at": []}
    order = np.lexsort((eff, dist))
    dist_s, eff_s, price_s, avail_s = dist[order], eff[order], price[order], avail[order]
    starts = np.flatnonzero(
        np.concatenate(([True], (dist_s[1:] != dist_s[:-1]) | (eff_s[1:] != eff_s[:-1])))
    )
    ends = np.append(starts[1:], len(dist_s))
    for lo, hi in zip(starts, ends, strict=True):
        if np.unique(price_s[lo:hi]).size > 1:
            raise ValueError(
                f"district {dist_s[lo]} tariff at {eff_s[lo]} is not uniform across stations"
            )
        out["district"].append(str(dist_s[lo]))
        out["effective_from"].append(int(eff_s[lo]))
        out["price_per_kwh"].append(float(price_s[lo]))
        out["available_at"].append(int(avail_s[lo:hi].min()))
    table = pa.table(
        {
            "district": pa.array(out["district"], type=pa.string()),
            "effective_from": pa.array(out["effective_from"], type=pa.int64()).cast(
                pa.timestamp("us", tz="UTC")
            ),
            "price_per_kwh": pa.array(out["price_per_kwh"], type=pa.float64()),
            "available_at": pa.array(out["available_at"], type=pa.int64()).cast(
                pa.timestamp("us", tz="UTC")
            ),
        }
    )
    return table.sort_by([("district", "ascending"), ("effective_from", "ascending")])


def _copy_through(source: Path, out_data: Path, names: list[str]) -> None:
    """Copy shared district-grain tables through as deterministic file bytes."""
    for name in names:
        src_dir = source / "data" / name
        for part in sorted(src_dir.rglob("*.parquet")):
            dest = out_data / name / part.relative_to(src_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(part.read_bytes())


def build_dataset(cfg: dict, source_release: Path, out_release: Path) -> dict:
    source_release, out_release = Path(source_release), Path(out_release)
    source_manifest = read_json(source_release / "manifest.json")
    source_sha = sha256_file(source_release / "manifest.json")

    stations = _read(source_release, "stations")
    demand = _read(source_release, "demand")
    tariffs = _read(source_release, "tariffs")
    districts = list(cfg["districts"])

    out_data = out_release / "data"
    out_data.mkdir(parents=True, exist_ok=True)
    _write(district_attributes(stations, districts), out_data / "districts/part-0000.parquet")
    _write(aggregate_demand(demand, stations, districts), out_data / "demand/part-0000.parquet")
    _write(district_tariffs(tariffs, stations), out_data / "tariffs/part-0000.parquet")
    _copy_through(source_release, out_data, ["holidays", "events", "weather_obs", "weather_fcst"])

    manifest = build_file_manifest(
        out_release,
        release_id=cfg["release_id"],
        schema_version=cfg["schema_version"],
        kind="dataset",
        extra={
            "source_commit": git_commit(out_release),
            "lineage": {
                "source_release_id": source_manifest["release_id"],
                "source_manifest_sha256": source_sha,
                "derivation": "station-hour demand summed to district-hour; "
                "available_at is the max over contributing stations",
            },
        },
    )
    return publish_release(out_release, manifest) and manifest


def validate_dataset(cfg: dict, release_dir: Path) -> list[str]:
    """Release checks; returns the list of check names that all passed."""
    release_dir = Path(release_dir)
    manifest = read_json(release_dir / "manifest.json")
    paths = {entry["path"] for entry in manifest["files"]}
    demand_table = pq.read_table(release_dir / "data/demand/part-0000.parquet")
    districts_table = pq.read_table(release_dir / "data/districts/part-0000.parquet")
    checks: list[str] = []

    def check(name: str, ok: bool) -> None:
        if not ok:
            raise ValueError(f"dataset check failed: {name}")
        checks.append(name)

    check("districts_complete", districts_table["district"].to_pylist() == cfg["districts"])
    hours = demand_table["hour_utc"].cast(pa.int64()).to_numpy()
    dist = np.asarray(demand_table["district"].to_pylist())
    values = demand_table["demand_kwh"].to_numpy()
    for district in cfg["districts"]:
        d_hours = np.sort(hours[dist == district])
        step = np.diff(d_hours)
        check(f"hourly_continuity_{district}", bool((step == 3_600_000_000).all()))
    check("demand_non_negative", bool((values >= 0).all()))
    counts = demand_table["station_count"].to_numpy()
    expected = dict(
        zip(
            districts_table["district"].to_pylist(),
            districts_table["station_count"].to_pylist(),
            strict=True,
        )
    )
    # Stations activate over time, so per-district counts grow to the full
    # roster: every hour has at least one station, never more than exist,
    # the count never decreases, and the last hour has the full roster.
    consistent = True
    for d in cfg["districts"]:
        d_counts = counts[dist == d]
        d_hours = hours[dist == d]
        order = np.argsort(d_hours, kind="stable")
        d_counts = d_counts[order]
        consistent &= bool(
            (d_counts >= 1).all()
            and (d_counts <= expected[d]).all()
            and (np.diff(d_counts) >= 0).all()
            and d_counts[-1] == expected[d]
        )
    check("station_counts_consistent", consistent)
    required = {
        "data/demand/part-0000.parquet",
        "data/districts/part-0000.parquet",
        "data/tariffs/part-0000.parquet",
    }
    check("manifest_files_present", required.issubset(paths))
    return checks
