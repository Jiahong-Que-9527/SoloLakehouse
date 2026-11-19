"""Build local EDDF Silver M1 observation tables from committed Bronze."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from airport_geometry import load_geometry

DAYS = tuple(date.fromisoformat(d) for d in ("2026-07-01", "2026-09-01", "2026-10-01"))
AIRPORT = "EDDF"
MIN_OFFSET, MAX_OFFSET = -420, 3000
MAX_AGE, MAX_GAP = 15, 30
SCHEMA_VERSION = "silver-eddf-m1-v1"
S, I, F, B = pa.string(), pa.int64(), pa.float64(), pa.bool_()
KEY = [("day_utc", pa.date32()), ("arrival_id", S)]
SCHEMAS = {
    "surface_points": KEY + [
        ("fragment_no", I), ("point_no", I), ("position_epoch_s", F), ("state_epoch_s", I),
        ("position_age_s", F), ("latitude", F), ("longitude", F), ("zone", S),
        ("nearest_runway", S), ("runway_distance_m", F), ("stand_distance_m", F),
        ("on_apron_geometry", B), ("near_taxiway_geometry", B),
        ("publishable_as_taxi_in", B),
    ],
    "surface_fragments": KEY + [
        ("fragment_no", I), ("first_position_epoch_s", F), ("last_position_epoch_s", F),
        ("point_count", I), ("observed_span_s", F), ("observed_path_m", F),
        ("max_internal_gap_s", F), ("fragment_type", S), ("starts_after_break", B),
        ("ends_before_break", B),
    ],
    "surface_breaks": KEY + [
        ("left_fragment_no", I), ("right_fragment_no", I), ("left_position_epoch_s", F),
        ("right_position_epoch_s", F), ("gap_s", F), ("endpoint_displacement_m", F),
        ("reason", S), ("source_partition_issue_between", B),
    ],
    "arrival_coverage": KEY + [
        ("icao24", S), ("arrival_anchor_epoch_s", I), ("analysis_window_start_epoch_s", I),
        ("analysis_window_end_epoch_s", I), ("censored_at_airborne_epoch_s", F),
        ("raw_near_airport_ground_states", I), ("stale_or_invalid_ground_states", I),
        ("duplicate_position_updates", I), ("surface_points", I), ("fragments", I),
        ("breaks", I), ("coverage_class", S), ("runway_vicinity_observed", B),
        ("runway_air_to_ground_observed", B), ("estimated_runway_axis", S),
        ("taxiway_vicinity_observed", B), ("apron_observed", B), ("stand_vicinity_observed", B),
        ("first_surface_position_epoch_s", F), ("last_surface_position_epoch_s", F),
        ("timing_gap_over_15s", I), ("timing_gap_over_30s", I), ("timing_gap_over_60s", I),
        ("missing_or_noncomplete_source_hours", I), ("publishable_as_taxi_in", B),
    ],
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_manifest(root, manifest, dataset, records, expected_start):
    if not manifest.is_file():
        records[str(manifest.relative_to(root))] = {"status": "missing_manifest"}
        return None, "missing_manifest"
    meta = json.loads(manifest.read_text())
    if (meta["dataset_id"], meta["dataset_version"], meta["window_start"]) != (
        dataset, "v1", expected_start
    ):
        raise ValueError(f"Manifest dataset, version or start differs: {manifest}")
    status = meta["status"]
    records[str(manifest.relative_to(root))] = {
        "status": status, "manifest_sha256": digest(manifest), "parquet_sha256": meta.get("sha256"),
    }
    if status != "complete":
        return None, status
    path = (root / meta["path"]).resolve(strict=True)
    if not path.is_relative_to(root) or digest(path) != meta["sha256"]:
        raise ValueError(f"Bronze path or checksum failed: {manifest}")
    return path, status


def flight_candidates(con, root, day, records):
    stamp = day.isoformat()
    manifest = root / "metadata/manifests/days" / f"dt={day}" / "flights.json"
    path, status = read_manifest(root, manifest, "eddf_flights", records, f"{stamp}T00:00:00Z")
    if not path:
        raise ValueError(f"Flight denominator unavailable for {day}: {status}")
    rows = con.execute("""
        select lower(icao24), lastseen, min(firstseen) from read_parquet(?)
        where estarrivalairport = ? and icao24 is not null and lastseen is not null
        group by 1, 2 order by 2, 1
    """, [str(path), AIRPORT]).fetchall()
    return [
        (f"{day}:{icao}:{last}", icao, last, last + MIN_OFFSET, last + MAX_OFFSET)
        for icao, last, _ in rows
    ]


def source_hours(root, lo, hi, records):
    paths, unavailable = [], []
    for hour in range(lo // 3600 * 3600, hi // 3600 * 3600 + 1, 3600):
        dt = datetime.fromtimestamp(hour, timezone.utc)
        manifest = root / "metadata/manifests/hours" / f"dt={dt:%Y-%m-%d}" / f"hour-{dt:%H}.json"
        path, status = read_manifest(
            root, manifest, "eddf_r75km", records, dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        if path:
            paths.append(str(path))
        else:
            unavailable.append((hour, status))
    return paths, unavailable


def load_states(con, candidates, paths):
    if not candidates or not paths:
        return {}
    con.register("windows", pa.table(dict(zip(
        ("arrival_id", "icao24", "anchor", "lo", "hi"), zip(*candidates)
    ))))
    data = con.execute("""
        select c.arrival_id, s.time, s.lastposupdate, s.lat, s.lon, s.onground
        from read_parquet(?) s join windows c
          on s.icao24 = c.icao24 and s.time between c.lo and c.hi
        where s.lat between 49.96 and 50.10 and s.lon between 8.45 and 8.69
        qualify row_number() over (
          partition by s.icao24, s.time, s.lastposupdate, s.lat, s.lon, s.onground
          order by abs(s.time-c.anchor), c.arrival_id
        ) = 1
        order by c.arrival_id, s.time, s.lastposupdate, s.lat, s.lon, s.onground
    """, [paths]).fetchall()
    con.unregister("windows")
    rows = defaultdict(list)
    for key, *values in data:
        rows[key].append(values)
    return rows


def fresh(state, obs):
    return obs is not None and -2 <= state - obs <= MAX_AGE


def touches_issue(hours, left, right):
    return any(h <= right and h + 3600 > left for h, _ in hours)


def flight_points(rows, airport, runway_labels, anchor):
    raw = [r for r in rows if r[4] is True]
    air = sorted({obs for state, obs, _, _, ground in rows if ground is False and fresh(state, obs)})
    if not raw:
        return [], air, 0, 0, 0, None, None
    xy = np.array([[(r[3] - 8.5706)*71500, (r[2] - 50.0333)*110570] for r in raw])
    distances, taxi, stand, apron = airport(xy)
    runway = distances.min(1)
    nearest = distances.argmin(1)
    near = (np.minimum(runway, taxi) <= 100) | apron | (stand <= 65)
    updates, stale, duplicate = {}, 0, 0
    for i in np.flatnonzero(near):
        state, obs, lat, lon, _ = raw[i]
        if not fresh(state, obs):
            stale += 1
            continue
        if obs in updates:
            duplicate += 1
            continue
        zone = ("runway_vicinity" if runway[i] <= 85 else "stand_vicinity" if stand[i] <= 55
                else "apron" if apron[i] else "taxiway_vicinity" if taxi[i] <= 60 else "airport_buffer")
        updates[obs] = {
            "position_epoch_s": obs, "state_epoch_s": state, "position_age_s": state-obs,
            "latitude": lat, "longitude": lon, "zone": zone,
            "nearest_runway": runway_labels[nearest[i]], "runway_distance_m": float(runway[i]),
            "stand_distance_m": float(stand[i]), "on_apron_geometry": bool(apron[i]),
            "near_taxiway_geometry": bool(taxi[i] <= 60 and runway[i] > 85 and not apron[i]),
            "publishable_as_taxi_in": False,
        }
    ordered = sorted(updates.values(), key=lambda p: p["position_epoch_s"])
    land = next((p for p in ordered if p["runway_distance_m"] <= 85
                 and anchor-300 <= p["position_epoch_s"] <= anchor+480
                 and any(p["position_epoch_s"]-60 <= a < p["position_epoch_s"] for a in air)), None)
    lower = land["position_epoch_s"] if land else anchor-120
    upper = min(anchor+MAX_OFFSET, lower+2400)
    # Two fresh airborne updates within 30 s identify subsequent airborne activity.
    later = [a for a in air if lower+90 < a <= upper]
    cutoff = next((a for a,b in zip(later, later[1:]) if 3 <= b-a <= 30), None)
    if cutoff is not None:
        upper = min(upper, cutoff)
    chosen = [p for p in ordered if lower <= p["position_epoch_s"] <= upper
              and (cutoff is None or p["position_epoch_s"] < cutoff)]
    return chosen, air, int(near.sum()), stale, duplicate, land, cutoff


def split(key, points, air, issues):
    fragments, breaks = [], []
    current = []
    elapsed = []
    for p in points:
        if current:
            last = current[-1]
            t0, t1 = last["position_epoch_s"], p["position_epoch_s"]
            gap = t1 - t0
            distance = displacement(last, p)
            elapsed.append(gap)
            issue = touches_issue(issues, t0, t1)
            reason = ("source_partition" if issue else
                      "airborne_observation" if any(t0 < a < t1 for a in air) else
                      "time_gap" if gap > MAX_GAP else
                      "implausible_displacement" if distance > 120 and distance/gap > 105 else None)
            if reason:
                fragments.append(current)
                breaks.append(dict(key, left_fragment_no=len(fragments),
                                   right_fragment_no=len(fragments)+1, left_position_epoch_s=t0,
                                   right_position_epoch_s=t1, gap_s=gap, endpoint_displacement_m=distance,
                                   reason=reason, source_partition_issue_between=issue))
                current = []
        current.append(p)
    if current:
        fragments.append(current)
    table = []
    for i, seq in enumerate(fragments, 1):
        for j, p in enumerate(seq, 1):
            p.update(key, fragment_no=i, point_no=j)
        ts = [p["position_epoch_s"] for p in seq]
        distance = sum(displacement(a, b) for a,b in zip(seq, seq[1:]))
        table.append(dict(key, fragment_no=i, first_position_epoch_s=ts[0],
                          last_position_epoch_s=ts[-1], point_count=len(seq),
                          observed_span_s=ts[-1]-ts[0], observed_path_m=distance,
                          max_internal_gap_s=max(np.diff(ts), default=None),
                          fragment_type="single_point" if len(seq)==1 else
                          "observed_movement" if distance >= 30 else "little_observed_movement",
                          starts_after_break=i>1, ends_before_break=i<len(fragments)))
    return table, breaks, elapsed


def displacement(a, b):
    return float(np.hypot((a["longitude"]-b["longitude"])*71500,
                          (a["latitude"]-b["latitude"])*110570))


def build_day(con, root, day, airport, labels, records, tables):
    candidates = flight_candidates(con, root, day, records)
    if not candidates:
        return
    paths, issues = source_hours(root, min(c[3] for c in candidates), max(c[4] for c in candidates), records)
    states = load_states(con, candidates, paths)
    for arrival_id, icao, anchor, lo, hi in candidates:
        key = dict(day_utc=day, arrival_id=arrival_id)
        points, air, raw, stale, duplicate, land, cutoff = flight_points(
            states.get(arrival_id, ()), airport, labels, anchor
        )
        fragments, breaks, elapsed = split(key, points, air, issues)
        tables["surface_points"].extend(points)
        tables["surface_fragments"].extend(fragments)
        tables["surface_breaks"].extend(breaks)
        tables["arrival_coverage"].append(dict(
            key, icao24=icao, arrival_anchor_epoch_s=anchor, analysis_window_start_epoch_s=lo,
            analysis_window_end_epoch_s=hi, censored_at_airborne_epoch_s=cutoff,
            raw_near_airport_ground_states=raw, stale_or_invalid_ground_states=stale,
            duplicate_position_updates=duplicate, surface_points=len(points), fragments=len(fragments),
            breaks=len(breaks), coverage_class="none" if not points else
            "movement_fragment" if any(f["fragment_type"]=="observed_movement" for f in fragments)
            else "ground_observations_only",
            runway_vicinity_observed=any(p["zone"]=="runway_vicinity" for p in points),
            runway_air_to_ground_observed=land is not None,
            estimated_runway_axis=land["nearest_runway"] if land else None,
            taxiway_vicinity_observed=any(p["near_taxiway_geometry"] for p in points),
            apron_observed=any(p["on_apron_geometry"] for p in points),
            stand_vicinity_observed=any(p["stand_distance_m"]<=55 for p in points),
            first_surface_position_epoch_s=points[0]["position_epoch_s"] if points else None,
            last_surface_position_epoch_s=points[-1]["position_epoch_s"] if points else None,
            timing_gap_over_15s=sum(t>15 for t in elapsed), timing_gap_over_30s=sum(t>30 for t in elapsed),
            timing_gap_over_60s=sum(t>60 for t in elapsed),
            missing_or_noncomplete_source_hours=sum(h<=hi and h+3600>lo for h,_ in issues),
            publishable_as_taxi_in=False,
        ))
    print(f"{day}: {len(candidates)} arrival candidates", flush=True)


def report(output, data, meta, days):
    coverage, fragments, breaks = (data[k] for k in ("arrival_coverage","surface_fragments","surface_breaks"))
    lines = [
        "# EDDF Silver M1 · 地面轨迹质量报告", "",
        "**[房玄龄·2026-11-19]** 指定 UTC 日期。分母为 OpenSky 航班表识别的 EDDF 到达候选。",
        "片段仅描述观测范围。机位邻近是空间标记，不证明实际进位；本批不生成完整 taxi-in 标签。", "",
        "| 日期 | 到达候选 | 有地面点 | 有移动片段 | 跑道附近空地转换 | 滑行道邻近 | 机坪内 | 机位邻近 | 点数 | 片段 | 断点 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for day in [*days, None]:
        bucket = [r for r in coverage if day is None or r["day_utc"]==day]
        counts = [len(bucket),sum(r["surface_points"]>0 for r in bucket),
                  sum(r["coverage_class"]=="movement_fragment" for r in bucket)]
        counts += [sum(r[k] for r in bucket) for k in ("runway_air_to_ground_observed",
            "taxiway_vicinity_observed","apron_observed","stand_vicinity_observed","surface_points","fragments","breaks")]
        lines.append("| " + " | ".join([str(day or "合计"), *(f"{n:,}" for n in counts)]) + " |")
    lines.extend(["", f"- 断点原因：{dict(sorted(Counter(r['reason'] for r in breaks).items()))}。",
        f"- 片段类型：{dict(sorted(Counter(r['fragment_type'] for r in fragments).items()))}。",
        f"- 有超过 15、30、60 秒断点的候选数："
        f"{[sum(r[f'timing_gap_over_{t}s']>0 for r in coverage) for t in (15,30,60)]}。",
        f"- 在查询窗口内遇到未完成 Bronze 小时的候选："
        f"{sum(r['missing_or_noncomplete_source_hours']>0 for r in coverage)}。",
        f"- 地面候选状态中排除过旧或无有效位置更新时间的状态："
        f"{sum(r['stale_or_invalid_ground_states'] for r in coverage):,}。"
        f"同一位置更新时间去重：{sum(r['duplicate_position_updates'] for r in coverage):,}。",
        f"- 输入指纹：`{meta['input_id']}`。Bronze、几何及产物 SHA-256 见 run_manifest.json。",
        "- 状态只用于观测，原始地速不参与评分。断点不插值，不把首末观测向外延伸。",
        "- 机场参考几何 © OpenStreetMap contributors，采用本次本地快照，不代表 2026 年历史布局。", ""])
    (output/"quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bronze-root","geometry-dir","output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--date", action="append", type=date.fromisoformat,
                        help="UTC date (YYYY-MM-DD); repeat for multiple days")
    choice.add_argument("--date-list", type=Path, help="Text file with one UTC date per line")
    args = parser.parse_args()
    dates = args.date
    if args.date_list is not None:
        try:
            dates = [date.fromisoformat(line.strip()) for line in args.date_list.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
        except (ValueError, OSError) as error:
            parser.error(str(error))
        if not dates:
            parser.error("--date-list has no dates")
    days = tuple(sorted(set(dates))) if dates else DAYS
    root, geo, output = (p.resolve() for p in (args.bronze_root,args.geometry_dir,args.output))
    repo = Path(__file__).resolve().parents[2]
    if output.is_relative_to(repo) or output.is_relative_to(root) or output.is_relative_to(geo):
        parser.error("write to a new local directory outside the source repository, Bronze and geometry")
    if output.exists():
        parser.error("output directory already exists; choose a new directory")
    geometry_inputs = {p.name:digest(p) for p in sorted(geo.glob("geometry-*.osm"))}
    airport, labels, geom_count = load_geometry(geo)
    con = duckdb.connect()
    con.execute("set threads=4")
    records, data = {}, {k:[] for k in SCHEMAS}
    for day in days:
        build_day(con, root, day, airport, labels, records, data)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    meta = {"schema_version":SCHEMA_VERSION, "dates_utc":[str(d) for d in days],
            "geometry":geometry_inputs,"geometry_counts":geom_count,"bronze_manifests":records,
            "code_sha256":{p.name:digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
            "lock_sha256":digest(Path(__file__).parent/"uv.lock"),
            "policy":{"max_freshness_s":MAX_AGE,"max_fragment_gap_s":MAX_GAP}}
    meta["input_id"] = hashlib.sha256(json.dumps(meta,sort_keys=True).encode()).hexdigest()
    artifacts = {}
    for name, schema in SCHEMAS.items():
        file = output / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(data[name], schema=pa.schema(schema)), file,
                       compression="zstd", row_group_size=65536)
        artifacts[file.name] = {"rows":len(data[name]), "sha256":digest(file)}
    report(output, data, meta, days)
    artifacts["quality_report.md"] = {"sha256":digest(output/"quality_report.md")}
    meta["outputs"] = artifacts
    (output/"run_manifest.json").write_text(json.dumps(meta,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v.get("rows") for k,v in artifacts.items()}), flush=True)


if __name__ == "__main__":
    main()
