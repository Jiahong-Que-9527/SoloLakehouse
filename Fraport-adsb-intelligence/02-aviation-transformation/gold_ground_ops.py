"""Gold market `ground_ops`: arrival threading and taxi-in labels (02 M2).

Consumes the neutral Silver v2 tables only. Semantics (documented proxies):

- Candidate arrivals: Silver flights with estarrivalairport = EDDF and a
  non-EDDF departure (EDDF->EDDF records are turnaround phantoms).
- Touchdown estimate: the last airborne observation (geoaltitude present,
  within 15 km) before the first surface observation (geoaltitude null,
  within 5 km) in a +-30 min window around the flight's lastseen.
- Taxi-in window: surface observations within 1 km of the airport reference
  point, capped at 45 min from the first surface observation. The optional
  geometry evaluation also admits mapped taxiway or apron points outside
  that radius and counts distinct position updates.
- The taxi-in label is a proxy: stands are never inferred, gaps are never
  bridged, and every candidate carries its coverage status.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from merge_silver_month import daily_input
from silver_v2 import AIRPORT_REF_LAT, AIRPORT_REF_LON, digest, displacement

AIRPORT = "EDDF"
ANCHOR_WINDOW_S = 30 * 60
SURFACE_DIST_M = 5_000
AIRBORNE_DIST_M = 15_000
TAXI_DIST_M = 1_000
TAXI_MAX_S = 45 * 60
TAXIWAY_MATCH_M = 30
RUNWAY_EXCLUSION_M = 30
SCHEMA_VERSION = "gold-ground-ops-v1"
RADIUS_LABEL_VERSION = "taxi-in-radius-v1"
GEOMETRY_LABEL_VERSION = "taxi-in-geometry-v2"

SCHEMAS = {
    "arrivals": [
        ("day_utc", pa.date32()), ("flight_key", pa.string()), ("icao24", pa.string()),
        ("callsign", pa.string()), ("lastseen_epoch_s", pa.int64()),
        ("touchdown_estimate_epoch_s", pa.int64()), ("surface_start_epoch_s", pa.int64()),
        ("taxi_end_epoch_s", pa.int64()), ("taxi_in_s", pa.int64()),
        ("surface_point_count", pa.int64()), ("taxi_path_m", pa.float64()),
        ("mean_surface_gap_s", pa.float64()), ("max_surface_gap_s", pa.float64()),
        ("end_distance_m", pa.float64()), ("status", pa.string()),
    ],
}


def _candidates(con, day):
    return con.execute("""
        select icao24, callsign, lastseen_epoch_s,
               icao24 || ':' || cast(lastseen_epoch_s as varchar) as flight_key
        from flights_view
        where day_utc = ? and estarrivalairport = ?
          and (estdepartureairport is null or estdepartureairport != ?)
          and lastseen_epoch_s is not null
        order by lastseen_epoch_s, icao24, callsign
    """, [day, AIRPORT, AIRPORT]).fetchall()


def label_arrival(observations, lastseen, *, use_geometry=False):
    """Thread one candidate: touchdown, surface window, taxi-in label."""
    lo, hi = lastseen - ANCHOR_WINDOW_S, lastseen + ANCHOR_WINDOW_S
    window = [o for o in observations if lo <= o["time_epoch_s"] <= hi
              and o["airport_ref_distance_m"] <= AIRBORNE_DIST_M]
    surface = [o for o in window if o["geoaltitude_m"] is None
               and o["airport_ref_distance_m"] <= SURFACE_DIST_M]
    if not surface:
        return {"status": "no_surface", "touchdown_estimate_epoch_s": None,
                "surface_start_epoch_s": None, "taxi_end_epoch_s": None,
                "taxi_in_s": None, "surface_point_count": 0, "taxi_path_m": None,
                "mean_surface_gap_s": None, "max_surface_gap_s": None,
                "end_distance_m": None}
    surface_start = surface[0]["time_epoch_s"]
    airborne_before = [o for o in window if o["geoaltitude_m"] is not None
                       and o["time_epoch_s"] < surface_start
                       and o["airport_ref_distance_m"] <= AIRBORNE_DIST_M]
    if not airborne_before:
        return {"status": "no_airborne_approach", "touchdown_estimate_epoch_s": None,
                "surface_start_epoch_s": surface_start, "taxi_end_epoch_s": None,
                "taxi_in_s": None, "surface_point_count": len(surface),
                "taxi_path_m": None, "mean_surface_gap_s": None,
                "max_surface_gap_s": None, "end_distance_m": None}
    touchdown = airborne_before[-1]["time_epoch_s"]
    if surface_start - touchdown > 600:
        return {"status": "surface_without_approach", "touchdown_estimate_epoch_s": None,
                "surface_start_epoch_s": surface_start, "taxi_end_epoch_s": None,
                "taxi_in_s": None, "surface_point_count": len(surface),
                "taxi_path_m": None, "mean_surface_gap_s": None,
                "max_surface_gap_s": None, "end_distance_m": None}
    taxi = [o for o in surface if o["time_epoch_s"] <= surface_start + TAXI_MAX_S
            and (o["airport_ref_distance_m"] <= TAXI_DIST_M
                 or (use_geometry and o.get("on_mapped_surface")))]
    if use_geometry:
        updates = {}
        for point in taxi:
            updates.setdefault(point["lastposupdate_epoch_s"], point)
        taxi = list(updates.values())
    if len(taxi) < 2 or (use_geometry and taxi[-1]["time_epoch_s"] <= surface_start):
        return {"status": "censored_few_points", "touchdown_estimate_epoch_s": touchdown,
                "surface_start_epoch_s": surface_start, "taxi_end_epoch_s": None,
                "taxi_in_s": None, "surface_point_count": len(surface),
                "taxi_path_m": None, "mean_surface_gap_s": None,
                "max_surface_gap_s": None, "end_distance_m": None}
    taxi_end = taxi[-1]["time_epoch_s"]
    gaps = [b - a for a, b in zip([p["time_epoch_s"] for p in taxi],
                                  [p["time_epoch_s"] for p in taxi][1:])]
    path = sum(displacement(a, b) for a, b in zip(taxi, taxi[1:]))
    return {"status": "labeled", "touchdown_estimate_epoch_s": touchdown,
            "surface_start_epoch_s": surface_start, "taxi_end_epoch_s": taxi_end,
            "taxi_in_s": taxi_end - surface_start, "surface_point_count": len(surface),
            "taxi_path_m": path,
            "mean_surface_gap_s": round(float(np.mean(gaps)), 2) if gaps else 0.0,
            "max_surface_gap_s": float(max(gaps)) if gaps else 0.0,
            "end_distance_m": taxi[-1]["airport_ref_distance_m"]}


def utc_date(epoch_s):
    return datetime.fromtimestamp(epoch_s, UTC).date()


def observation_dates(candidates):
    needed = set()
    for _, _, lastseen, _ in candidates:
        needed.add(utc_date(lastseen - ANCHOR_WINDOW_S).isoformat())
        needed.add(utc_date(lastseen + ANCHOR_WINDOW_S).isoformat())
    return needed


def mark_mapped_surface(points, geometry):
    outside = [
        p for p in points if p["geoaltitude_m"] is None
        and TAXI_DIST_M < p["airport_ref_distance_m"] <= SURFACE_DIST_M
    ]
    for start in range(0, len(outside), 2048):
        batch = outside[start:start + 2048]
        xy = np.array([((p["lon"] - AIRPORT_REF_LON) * 71500,
                        (p["lat"] - AIRPORT_REF_LAT) * 110570) for p in batch])
        runway, taxiway, _, apron = geometry(xy, with_stands=False)
        supported = (runway.min(axis=1) > RUNWAY_EXCLUSION_M) & (
            (taxiway <= TAXIWAY_MATCH_M) | apron)
        for point, matched in zip(batch, supported):
            point["on_mapped_surface"] = bool(matched)


def build_day(con, day, candidates, geometry=None):
    if not candidates:
        return []
    lo = min(c[2] for c in candidates) - ANCHOR_WINDOW_S
    hi = max(c[2] for c in candidates) + ANCHOR_WINDOW_S
    rows = con.execute("""
        select icao24, time_epoch_s, lastposupdate_epoch_s, geoaltitude_m,
               airport_ref_distance_m, lat, lon
        from obs_view
        where day_utc between ? and ? and time_epoch_s between ? and ?
          and icao24 = any(?) and airport_ref_distance_m <= ?
        order by icao24, time_epoch_s, lat, lon, geoaltitude_m, lastposupdate_epoch_s
    """, [utc_date(lo), utc_date(hi), lo, hi, sorted({c[0] for c in candidates}),
          AIRBORNE_DIST_M]).fetchall()
    obs_by_icao = defaultdict(list)
    for icao, t, update, alt, dist, lat, lon in rows:
        obs_by_icao[icao].append({"time_epoch_s": t, "geoaltitude_m": alt,
                                  "airport_ref_distance_m": dist,
                                  "lat": lat, "lon": lon, "lastposupdate_epoch_s": update})
    if geometry is not None:
        mark_mapped_surface((p for points in obs_by_icao.values() for p in points), geometry)
    arrivals = []
    for icao, callsign, lastseen, flight_key in candidates:
        result = label_arrival(
            obs_by_icao.get(icao, []), lastseen, use_geometry=geometry is not None)
        arrivals.append(dict(
            day_utc=day, flight_key=flight_key, icao24=icao, callsign=callsign,
            lastseen_epoch_s=lastseen, **result))
    print(f"{day}: {len(candidates)} arrival candidates, "
          f"{Counter(r['status'] for r in arrivals)}", flush=True)
    return arrivals


def report(output, arrivals, meta, days):
    statuses = Counter(a["status"] for a in arrivals)
    labeled = [a for a in arrivals if a["status"] == "labeled"]
    lines = [
        "# gold/ground_ops · taxi-in 标签覆盖报告", "",
        "**[GLM·2026-11-21]** 依据 ADR-006：消费 Silver v2 中性层；"
        "落地估计 = 进港航班 lastseen 窗口内最后一次空中观测；"
        "滑行标签是代理（不推断机位、不桥接间隙）。", "",
    ]
    for key, label in (
        ("missing_dates_utc", "缺少 Silver 的发布日期"),
        ("missing_observation_dates_utc", "航班时间窗口涉及但缺少观测的日期"),
    ):
        if meta.get(key):
            lines.extend([f"- {label}：{', '.join(meta[key])}。", ""])
    if "airport_geometry" in meta:
        lines.extend(["- 1 公里外的轨迹点需匹配滑行道或机坪，并排除跑道附近的点。"
                      "同一次位置更新只计一次。", ""])
    lines.extend([
        "| 日期 | 候选 | labeled | no_surface | no_airborne | surface_without_approach | censored |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for day in days:
        bucket = [a for a in arrivals if str(a["day_utc"]) == day]
        c = Counter(a["status"] for a in bucket)
        lines.append(f"| {day} | {len(bucket)} | {c.get('labeled', 0)} "
                     f"| {c.get('no_surface', 0)} | {c.get('no_airborne_approach', 0)} "
                     f"| {c.get('surface_without_approach', 0)} | {c.get('censored_few_points', 0)} |")
    if labeled:
        labels = [a["taxi_in_s"] for a in labeled]
        lines += [
            "",
            f"- labeled taxi-in 时长：min {min(labels)/60:.1f} min / 中位 "
            f"{sorted(labels)[len(labels)//2]/60:.1f} min / max {max(labels)/60:.1f} min。",
            f"- 滑行路径长度：min {min(a['taxi_path_m'] for a in labeled):.0f} m / "
            f"max {max(a['taxi_path_m'] for a in labeled):.0f} m。",
            f"- 有 30s 以上滑行间隙的 labeled 航班："
            f"{sum(1 for a in labeled if (a['max_surface_gap_s'] or 0) > 30)}。",
        ]
    lines += ["", f"- 全部状态：{dict(sorted(statuses.items()))}。",
              "- 状态只描述覆盖，不代表滑行真实性；标签是代理，需独立验证。", ""]
    (output / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-root", type=Path, required=True)
    parser.add_argument("--daily-root", type=Path,
                        help="daily Silver for observation windows outside the merged month")
    parser.add_argument("--geometry-dir", type=Path,
                        help="evaluate circle plus taxiway/apron support using a local OSM snapshot")
    parser.add_argument("--output", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--date", action="append", type=date.fromisoformat)
    choice.add_argument("--date-list", type=Path)
    args = parser.parse_args()
    if args.date:
        days = tuple(sorted(set(args.date)))
    elif args.date_list:
        days = tuple(date.fromisoformat(line.strip())
                     for line in args.date_list.read_text(encoding="utf-8").splitlines()
                     if line.strip())
        if not days:
            parser.error("--date-list is empty")
    else:
        parser.error("--date or --date-list is required")
    silver, output = args.silver_root.resolve(), args.output.resolve()
    _here = Path(__file__).resolve()
    # In a container the three-level repository layout does not exist;
    # skip the repo check there and keep the input-directory checks.
    repo = _here.parents[2] if len(_here.parents) > 2 else None
    if (repo and output.is_relative_to(repo)) or output.is_relative_to(silver):
        parser.error("write to a new local directory outside the repository and Silver")
    if output.exists():
        parser.error("output directory already exists; choose a new directory")
    con = duckdb.connect()
    con.execute("set threads=4")
    con.from_parquet(str(silver / "flights.parquet")).create_view("flights_view")
    candidates = {day: _candidates(con, day) for day in days}
    paths = [str(silver / "observations.parquet")]
    meta = {
        "schema_version": SCHEMA_VERSION, "adr": "ADR-006", "silver_input": str(silver),
        "label_version": RADIUS_LABEL_VERSION,
        "dates_utc": [str(d) for d in days],
        "policy": {"anchor_window_s": ANCHOR_WINDOW_S, "surface_dist_m": SURFACE_DIST_M,
                   "taxi_dist_m": TAXI_DIST_M, "taxi_max_s": TAXI_MAX_S,
                   "max_air_to_surface_gap_s": 600},
        "code_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    }
    geometry = None
    if args.geometry_dir:
        from airport_geometry import load_geometry

        snapshot_files = sorted(args.geometry_dir.glob("geometry-*.osm"))
        if not snapshot_files:
            parser.error("--geometry-dir must contain geometry-*.osm snapshot files")
        geometry, _, counts = load_geometry(args.geometry_dir)
        meta["label_version"] = GEOMETRY_LABEL_VERSION
        meta["airport_geometry"] = {
            "files": {path.name: digest(path) for path in snapshot_files},
            "counts": counts,
            "taxiway_match_m": TAXIWAY_MATCH_M,
            "runway_exclusion_m": RUNWAY_EXCLUSION_M,
            "distinct_position_updates": True,
        }
    manifest = silver / "run_manifest.json"
    if manifest.is_file():
        meta["silver_manifest_sha256"] = digest(manifest)
        silver_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        if silver_manifest["schema_version"] == "silver-month-v1":
            requested = set(silver_manifest["requested_dates_utc"])
            present = set(silver_manifest["dates_utc"])
            needed = set().union(*(observation_dates(rows) for rows in candidates.values()))
            context = {}
            if args.daily_root:
                for day in sorted(needed - requested):
                    sha = daily_input(args.daily_root, day, ("observations",))
                    if sha is not None:
                        context[day] = sha
                        paths.append(str(args.daily_root / day / "observations.parquet"))
            meta["silver_dates_utc"] = sorted(present.intersection(meta["dates_utc"]))
            meta["missing_dates_utc"] = sorted(set(meta["dates_utc"]) - present)
            meta["boundary_observation_manifests"] = context
            meta["missing_observation_dates_utc"] = sorted(needed - present - context.keys())
    con.from_parquet(paths).create_view("obs_view")
    all_arrivals = [arrival for day, rows in candidates.items()
                    for arrival in build_day(con, day, rows, geometry)]
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    meta["input_id"] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    artifacts = {}
    file = output / "arrivals.parquet"
    pq.write_table(pa.Table.from_pylist(all_arrivals, schema=pa.schema(SCHEMAS["arrivals"])),
                   file, compression="zstd", row_group_size=65536)
    artifacts[file.name] = {"rows": len(all_arrivals), "sha256": digest(file)}
    report(output, all_arrivals, meta, [str(d) for d in days])
    artifacts["coverage_report.md"] = {"sha256": digest(output / "coverage_report.md")}
    meta["outputs"] = artifacts
    (output / "run_manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v.get("rows") for k, v in artifacts.items()}), flush=True)


if __name__ == "__main__":
    main()
