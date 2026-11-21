"""Build the neutral Silver v2 observation layer from committed Bronze (ADR-006).

Silver answers "what was observed this day in this region, and how
trustworthy is it". It carries no business semantics: arrival threading,
taxi usability and phase annotation are Gold logic. Four tables, partitioned
by day_utc:

- observations: every fresh position update, airborne and ground, full region
- segments:     per-aircraft continuous runs with the reason each break
- flights:      deduplicated Bronze flight records for the day
- daily_coverage: per-aircraft trust statistics plus the day rollup

The Bronze ``onground`` flag is carried as a raw column and never used for
decisions (see ADR-006, case 3c618b).
"""
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

from silver_m1 import digest, fresh, read_manifest, source_hours

AIRPORT_REF_LON, AIRPORT_REF_LAT = 8.5706, 50.0333
MAX_AGE, MAX_GAP = 15, 30
SCHEMA_VERSION = "silver-eddf-v2"
NEAR_AIRPORT_M = 15_000
D = date32 = pa.date32()
S, I, F, B = pa.string(), pa.int64(), pa.float64(), pa.bool_()
KEY = [("day_utc", D), ("icao24", S)]
SCHEMAS = {
    "observations": KEY + [
        ("time_epoch_s", I), ("lastposupdate_epoch_s", F), ("position_age_s", F),
        ("lat", F), ("lon", F), ("baroaltitude_m", F), ("geoaltitude_m", F),
        ("velocity_mps", F), ("heading_deg", F), ("vertrate_mps", F),
        ("onground_raw", B), ("callsign", S), ("airport_ref_distance_m", F),
        ("segment_no", I),
    ],
    "segments": KEY + [
        ("segment_no", I), ("first_time_epoch_s", I), ("last_time_epoch_s", I),
        ("point_count", I), ("observed_span_s", I), ("observed_path_m", F),
        ("max_internal_gap_s", F), ("segment_type", S), ("starts_after_break", B),
        ("ends_before_break", B), ("break_reason_after", S), ("gap_after_s", F),
        ("displacement_after_m", F),
    ],
    "flights": KEY + [
        ("callsign", S), ("firstseen_epoch_s", I), ("lastseen_epoch_s", I),
        ("estdepartureairport", S), ("estarrivalairport", S),
    ],
    "daily_coverage": KEY + [
        ("observation_count", I), ("first_seen_epoch_s", I), ("last_seen_epoch_s", I),
        ("segment_count", I), ("break_count", I), ("max_gap_s", F),
        ("stale_dropped", I), ("invalid_dropped", I), ("duplicates_dropped", I),
        ("within_15km_share", F), ("flights_recorded", I),
    ],
}


def ref_distance(lat, lon):
    return float(np.hypot((lon - AIRPORT_REF_LON) * 71500, (lat - AIRPORT_REF_LAT) * 110570))


def displacement(a, b):
    return float(np.hypot((a["lon"] - b["lon"]) * 71500, (a["lat"] - b["lat"]) * 110570))


def load_flights(con, root, day, records):
    manifest = root / "metadata/manifests/days" / f"dt={day}" / "flights.json"
    path, status = read_manifest(
        root, manifest, "eddf_flights", records, f"{day.isoformat()}T00:00:00Z"
    )
    if not path:
        return [], {"raw": 0, "deduplicated": 0, "status": status}
    rows = con.execute("""
        select distinct lower(icao24), callsign, firstseen, lastseen,
               estdepartureairport, estarrivalairport
        from read_parquet(?)
        where icao24 is not null and lastseen is not null
    """, [str(path)]).fetchall()
    raw = con.execute("select count(*) from read_parquet(?)", [str(path)]).fetchone()[0]
    table = [dict(zip(("icao24", "callsign", "firstseen_epoch_s", "lastseen_epoch_s",
                       "estdepartureairport", "estarrivalairport"), r)) for r in rows]
    return table, {"raw": raw, "deduplicated": len(table), "status": status}


def load_observations(con, root, day, records):
    """Read the full day, clean it in SQL, return rows grouped per aircraft."""
    lo = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    paths, issues = source_hours(root, lo, lo + 86399, records)
    if not paths:
        return {}, issues
    rows = con.execute("""
        select lower(icao24) as icao24, time, lastposupdate, lat, lon,
               baroaltitude, geoaltitude, velocity, heading, vertrate,
               onground, callsign
        from read_parquet(?)
        where icao24 is not null and lat is not null and lon is not null
          and lat between -90 and 90 and lon between -180 and 180
        order by icao24, time, lastposupdate, lat, lon
    """, [paths]).fetchall()
    grouped = defaultdict(list)
    for r in rows:
        grouped[r[0]].append(r)
    return grouped, issues


def segment_aircraft(day, icao, rows, issues):
    """Clean one aircraft's raw states into observations, segments and counters."""
    stale = invalid = duplicates = 0
    cleaned, seen = [], set()
    for (_, time_s, last, lat, lon, baro, geo, vel, head, vert, onground, callsign) in rows:
        if last is None or not fresh(time_s, last):
            stale += 1
            continue
        if (time_s, last, lat, lon) in seen:
            duplicates += 1
            continue
        seen.add((time_s, last, lat, lon))
        cleaned.append(dict(
            time_epoch_s=time_s, lastposupdate_epoch_s=last, position_age_s=time_s - last,
            lat=lat, lon=lon, baroaltitude_m=baro, geoaltitude_m=geo, velocity_mps=vel,
            heading_deg=head, vertrate_mps=vert, onground_raw=onground, callsign=callsign,
            airport_ref_distance_m=ref_distance(lat, lon),
        ))
    segments = []
    current = []
    for point in cleaned:
        if current:
            last_p = current[-1]
            gap = point["time_epoch_s"] - last_p["time_epoch_s"]
            distance = displacement(last_p, point)
            issue = any(h <= point["time_epoch_s"] and h + 3600 > last_p["time_epoch_s"]
                        for h, _ in issues)
            surface_pair = last_p["onground_raw"] and point["onground_raw"]
            reason = ("source_partition" if issue else
                      "time_gap" if gap > MAX_GAP else
                      "implausible_displacement" if surface_pair and distance > 120
                      and gap > 0 and distance / gap > 105 else None)
            if reason:
                segments.append((current, (reason, gap, distance)))
                current = []
        current.append(point)
    if current:
        segments.append((current, None))

    segment_rows, observation_rows = [], []
    for no, (seq, break_info) in enumerate(segments, 1):
        for j, p in enumerate(seq, 1):
            p["segment_no"] = no
            observation_rows.append(dict(day_utc=day, icao24=icao, **p))
        ts = [p["time_epoch_s"] for p in seq]
        path_length = sum(displacement(a, b) for a, b in zip(seq, seq[1:]))
        reason, gap, dist = break_info if no < len(segments) else (None, None, None)
        segment_rows.append(dict(
            day_utc=day, icao24=icao, segment_no=no, first_time_epoch_s=ts[0],
            last_time_epoch_s=ts[-1], point_count=len(seq), observed_span_s=ts[-1] - ts[0],
            observed_path_m=path_length, max_internal_gap_s=max(np.diff(ts), default=None),
            segment_type=("single_point" if len(seq) == 1 else
                          "observed_movement" if path_length >= 30 else
                          "little_observed_movement"),
            starts_after_break=no > 1, ends_before_break=no < len(segments),
            break_reason_after=reason, gap_after_s=gap, displacement_after_m=dist,
        ))
    return observation_rows, segment_rows, {
        "stale_dropped": stale, "invalid_dropped": invalid, "duplicates_dropped": duplicates,
    }


def build_day(con, root, day, records, tables):
    flights, flight_meta = load_flights(con, root, day, records)
    per_aircraft, issues = load_observations(con, root, day, records)
    flights_by_icao = Counter(f["icao24"] for f in flights)
    coverage = []
    for icao in sorted(per_aircraft):
        observation_rows, segment_rows, counters = segment_aircraft(day, icao, per_aircraft[icao], issues)
        tables["observations"].extend(observation_rows)
        tables["segments"].extend(segment_rows)
        gaps = [s["max_internal_gap_s"] for s in segment_rows if s["max_internal_gap_s"]]
        points = [o for o in observation_rows]
        coverage.append(dict(
            day_utc=day, icao24=icao, observation_count=len(points),
            first_seen_epoch_s=min(p["time_epoch_s"] for p in points),
            last_seen_epoch_s=max(p["time_epoch_s"] for p in points),
            segment_count=len(segment_rows), break_count=sum(1 for s in segment_rows if s["ends_before_break"]),
            max_gap_s=max(gaps) if gaps else None,
            stale_dropped=counters["stale_dropped"], invalid_dropped=counters["invalid_dropped"],
            duplicates_dropped=counters["duplicates_dropped"],
            within_15km_share=round(sum(p["airport_ref_distance_m"] <= NEAR_AIRPORT_M
                                        for p in points) / len(points), 4) if points else 0.0,
            flights_recorded=flights_by_icao.get(icao, 0),
        ))
    tables["flights"].extend(dict(day_utc=day, **f) for f in flights)
    tables["daily_coverage"].extend(coverage)
    print(f"{day}: {len(coverage)} aircraft, {len(tables['observations'])} observations, "
          f"{flight_meta['raw']} -> {flight_meta['deduplicated']} flights", flush=True)
    return coverage, flight_meta, issues


def report(output, data, coverage_rows, meta, days, flight_meta, issues):
    segments = data["segments"]
    reasons = Counter(s["break_reason_after"] for s in segments if s["break_reason_after"])
    types = Counter(s["segment_type"] for s in segments)
    lines = [
        "# EDDF Silver v2 · 中性观测层质量报告", "",
        "**[GLM·2026-11-21]** 依据 ADR-006：全天全区域读取，不做业务过滤；"
        "`onground` 标志仅原样保留，不参与任何判定。", "",
        "| 日期 | 飞机数 | 观测点 | 分段 | 航段记录 |",
        "|---|---:|---:|---:|---:|",
    ]
    for day in days:
        bucket = [r for r in coverage_rows if r["day_utc"] == day]
        lines.append(f"| {day} | {len(bucket):,} | {sum(r['observation_count'] for r in bucket):,} "
                     f"| {sum(r['segment_count'] for r in bucket):,} "
                     f"| {sum(r['flights_recorded'] for r in bucket):,} |")
    lines += [
        "",
        f"- 断裂原因：{dict(sorted(reasons.items()))}。",
        f"- 分段类型：{dict(sorted(types.items()))}。",
        f"- 清洗丢弃：过旧/无位置更新 {sum(r['stale_dropped'] for r in coverage_rows):,}，"
        f"坐标无效 {sum(r['invalid_dropped'] for r in coverage_rows):,}，"
        f"重复位置更新 {sum(r['duplicates_dropped'] for r in coverage_rows):,}。",
        f"- 航班记录：{flight_meta['raw']:,} -> {flight_meta['deduplicated']:,}（status {flight_meta['status']}）。",
        f"- 不可用或非 complete 的 Bronze 小时：{len(issues)}。",
        "- 分段不跨日；断裂不插值；phase 判定属 Gold 逻辑（见 ADR-006）。", "",
    ]
    (output / "quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bronze-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--date", action="append", type=date.fromisoformat,
                        help="UTC date (YYYY-MM-DD); repeat for multiple days")
    choice.add_argument("--date-list", type=Path)
    args = parser.parse_args()
    days = tuple(sorted(set(args.date))) if args.date else parser.error("--date is required")
    root, output = args.bronze_root.resolve(), args.output.resolve()
    repo = Path(__file__).resolve().parents[2]
    if output.is_relative_to(repo) or output.is_relative_to(root):
        parser.error("write to a new local directory outside the repository and Bronze")
    if output.exists():
        parser.error("output directory already exists; choose a new directory")
    con = duckdb.connect()
    con.execute("set threads=4")
    records = {}
    data = {k: [] for k in SCHEMAS}
    all_coverage, all_flight_meta, all_issues = [], {}, {}
    for day in days:
        coverage, flight_meta, issues = build_day(con, root, day, records, data)
        all_coverage.extend(coverage)
        all_flight_meta[str(day)] = flight_meta
        all_issues[str(day)] = issues
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    meta = {
        "schema_version": SCHEMA_VERSION, "adr": "ADR-006",
        "dates_utc": [str(d) for d in days], "bronze_manifests": records,
        "code_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "lock_sha256": digest(Path(__file__).parent / "uv.lock"),
        "policy": {"max_freshness_s": MAX_AGE, "max_segment_gap_s": MAX_GAP,
                   "near_airport_m": NEAR_AIRPORT_M, "onground_flag": "carried_raw_never_used"},
        "flight_meta": all_flight_meta, "unavailable_hours": all_issues,
    }
    meta["input_id"] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    artifacts = {}
    for name, schema in SCHEMAS.items():
        file = output / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(data[name], schema=pa.schema(schema)), file,
                       compression="zstd", row_group_size=65536)
        artifacts[file.name] = {"rows": len(data[name]), "sha256": digest(file)}
    report(output, data, all_coverage, meta, days, all_flight_meta[days[0].isoformat()], all_issues[days[0].isoformat()])
    artifacts["quality_report.md"] = {"sha256": digest(output / "quality_report.md")}
    meta["outputs"] = artifacts
    (output / "run_manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v.get("rows") for k, v in artifacts.items()}), flush=True)


if __name__ == "__main__":
    main()
