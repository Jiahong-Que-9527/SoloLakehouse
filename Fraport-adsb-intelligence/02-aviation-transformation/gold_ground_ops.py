"""Gold market `ground_ops`: arrival threading and taxi-in labels (02 M2).

Consumes the neutral Silver v2 tables only. Semantics (documented proxies):

- Candidate arrivals: Silver flights with estarrivalairport = EDDF and a
  non-EDDF departure (EDDF->EDDF records are turnaround phantoms).
- Touchdown estimate: the last airborne observation (geoaltitude present,
  within 15 km) before the first surface observation (geoaltitude null,
  within 5 km) in a +-30 min window around the flight's lastseen.
- Taxi-in window: surface observations within 1 km of the airport reference
  point, ending at the last such point within 45 min of the touchdown.
- The taxi-in label is a proxy: stands are never inferred, gaps are never
  bridged, and every candidate carries its coverage status.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from silver_v2 import digest, displacement

AIRPORT = "EDDF"
ANCHOR_WINDOW_S = 30 * 60
SURFACE_DIST_M = 5_000
AIRBORNE_DIST_M = 15_000
TAXI_DIST_M = 1_000
TAXI_MAX_S = 45 * 60
SCHEMA_VERSION = "gold-ground-ops-v1"

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
        order by lastseen_epoch_s
    """, [day, AIRPORT, AIRPORT]).fetchall()


def label_arrival(observations, lastseen):
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
    taxi = [o for o in surface if o["airport_ref_distance_m"] <= TAXI_DIST_M
            and o["time_epoch_s"] <= surface_start + TAXI_MAX_S]
    if len(taxi) < 2:
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


def build_day(con, day, tables):
    candidates = _candidates(con, day)
    rows = con.execute("""
        select icao24, time_epoch_s, geoaltitude_m, airport_ref_distance_m, lat, lon
        from obs_view
        where day_utc = ? order by icao24, time_epoch_s
    """, [day]).fetchall()
    obs_by_icao = defaultdict(list)
    for icao, t, alt, dist, lat, lon in rows:
        obs_by_icao[icao].append({"time_epoch_s": t, "geoaltitude_m": alt,
                                  "airport_ref_distance_m": dist,
                                  "lat": lat, "lon": lon})
    for icao, callsign, lastseen, flight_key in candidates:
        result = label_arrival(obs_by_icao.get(icao, []), lastseen)
        tables["arrivals"].append(dict(
            day_utc=day, flight_key=flight_key, icao24=icao, callsign=callsign,
            lastseen_epoch_s=lastseen, **result))
    print(f"{day}: {len(candidates)} arrival candidates, "
          f"{Counter(r['status'] for r in tables['arrivals'])}", flush=True)


def report(output, arrivals, meta, days):
    statuses = Counter(a["status"] for a in arrivals)
    labeled = [a for a in arrivals if a["status"] == "labeled"]
    lines = [
        "# gold/ground_ops · taxi-in 标签覆盖报告", "",
        "**[GLM·2026-11-21]** 依据 ADR-006：消费 Silver v2 中性层；"
        "落地估计 = 进港航班 lastseen 窗口内最后一次空中观测；"
        "滑行标签是代理（不推断机位、不桥接间隙）。", "",
        "| 日期 | 候选 | labeled | no_surface | no_airborne | surface_without_approach | censored |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
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
    parser.add_argument("--output", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--date", action="append", type=date.fromisoformat)
    choice.add_argument("--date-list", type=Path)
    args = parser.parse_args()
    days = tuple(sorted(set(args.date))) if args.date else parser.error("--date is required")
    silver, output = args.silver_root.resolve(), args.output.resolve()
    repo = Path(__file__).resolve().parents[2]
    if output.is_relative_to(repo) or output.is_relative_to(silver):
        parser.error("write to a new local directory outside the repository and Silver")
    if output.exists():
        parser.error("output directory already exists; choose a new directory")
    _flights = str(silver / "flights.parquet")
    _observations = str(silver / "observations.parquet")
    con = duckdb.connect()
    con.execute("set threads=4")
    con.execute(f"CREATE VIEW flights_view AS SELECT * FROM read_parquet('{_flights}')")
    con.execute(f"CREATE VIEW obs_view AS SELECT * FROM read_parquet('{_observations}')")
    tables = {k: [] for k in SCHEMAS}
    all_arrivals = []
    for day in days:
        build_day(con, day, tables)
        all_arrivals.extend(tables["arrivals"])
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    meta = {
        "schema_version": SCHEMA_VERSION, "adr": "ADR-006", "silver_input": str(silver),
        "dates_utc": [str(d) for d in days],
        "policy": {"anchor_window_s": ANCHOR_WINDOW_S, "surface_dist_m": SURFACE_DIST_M,
                   "taxi_dist_m": TAXI_DIST_M, "taxi_max_s": TAXI_MAX_S,
                   "max_air_to_surface_gap_s": 600},
        "code_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    }
    meta["input_id"] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    artifacts = {}
    for name, schema in SCHEMAS.items():
        file = output / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(tables[name], schema=pa.schema(schema)), file,
                       compression="zstd", row_group_size=65536)
        artifacts[file.name] = {"rows": len(tables[name]), "sha256": digest(file)}
    report(output, all_arrivals, meta, [str(d) for d in days])
    artifacts["coverage_report.md"] = {"sha256": digest(output / "coverage_report.md")}
    meta["outputs"] = artifacts
    (output / "run_manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v.get("rows") for k, v in artifacts.items()}), flush=True)


if __name__ == "__main__":
    main()
