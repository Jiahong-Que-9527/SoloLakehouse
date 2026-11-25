"""Resume monthly Geometry v2 releases or reconcile the deployed series."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

from ingest_release import GEOMETRY_TABLE, BigQueryOps, digest, target_table
from upload_release import approved_release_id

HERE = Path(__file__).resolve().parent
MIB = 1024 ** 2


def release_months(first: str, last: str):
    month = date.fromisoformat(first + "-01")
    end = date.fromisoformat(last + "-01")
    if month > end:
        raise ValueError("the first month must precede or equal the last month")
    while month <= end:
        yield month.isoformat()[:7]
        if month == end:
            break
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def local_release(directory: Path, release_id: str) -> dict:
    if approved_release_id(directory) != release_id:
        raise ValueError(f"release ID does not match its directory: {directory}")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    target_table(manifest, GEOMETRY_TABLE)
    status = pq.read_table(directory / "data/part-0001.parquet", columns=["status"])["status"]
    if len(status) != manifest["files"]["data/part-0001.parquet"]["rows"]:
        raise ValueError(f"manifest row count mismatch for {release_id}")
    return {
        "manifest_sha256": digest(manifest_path),
        "counts": {"rows": len(status), "labeled_rows": pc.sum(pc.equal(status, "labeled")).as_py() or 0,
                   "duplicate_keys": 0},
    }


def command(script: str, *args: str) -> dict:
    result = subprocess.run([sys.executable, str(HERE / script), *args],
                            text=True, stdout=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f"{script} exited {result.returncode}: {result.stdout.strip()}")
    return json.loads(result.stdout)


def atomic_text(path: Path, contents: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(contents, encoding="utf-8")
    os.replace(temp, path)


def atomic_json(path: Path, record: dict) -> None:
    atomic_text(path, json.dumps(record, indent=2) + "\n")


def accept_ingest(result: dict, release_id: str, counts: dict, *, replay: bool = False) -> None:
    if result.get("release_id") != release_id or result.get("geometry_counts") != counts:
        raise ValueError(f"BigQuery evidence does not reconcile for {release_id}")
    if result.get("status") == "already_ingested" and result.get("rows_added") == 0:
        return
    if replay or result.get("status") != "ingested":
        raise ValueError(f"unexpected ingest outcome for {release_id}: {result.get('status')}")


def import_series(args, releases: dict) -> None:
    for release_id, local in releases.items():
        evidence = args.evidence_dir / f"{release_id}.json"
        identity = {"release_id": release_id, "local": local, "project": args.project,
                    "landing_bucket": args.landing_bucket, "gold_bucket": args.gold_bucket,
                    "max_bytes_billed": args.max_bytes_billed}
        record = dict(identity)
        if evidence.exists():
            record = json.loads(evidence.read_text())
            if any(record.get(key) != value for key, value in identity.items()):
                raise ValueError(f"saved evidence does not match the current inputs: {evidence}")
            accept_ingest(record["ingest"], release_id, local["counts"])
            if not args.replay or "replay" in record:
                if args.replay:
                    accept_ingest(record["replay"], release_id, local["counts"], replay=True)
                print(f"{release_id}: already verified", flush=True)
                continue
        ingest_args = ("--landing", f"gs://{args.landing_bucket}/releases/{release_id}",
                       "--project", args.project, "--gold-bucket", args.gold_bucket,
                       "--max-bytes-billed", str(args.max_bytes_billed),
                       "--expect-geometry-labels", str(local["counts"]["labeled_rows"]))
        if "ingest" not in record:
            print(f"{release_id}: uploading and ingesting", flush=True)
            record["upload"] = command("upload_release.py", str(args.release_dir / release_id),
                                       "--project", args.project, "--landing-bucket", args.landing_bucket,
                                       "--uploader", args.uploader)
            record["ingest"] = command("ingest_release.py", *ingest_args)
            accept_ingest(record["ingest"], release_id, local["counts"])
            atomic_json(evidence, record)
        if args.replay:
            record["replay"] = command("ingest_release.py", *ingest_args)
            accept_ingest(record["replay"], release_id, local["counts"], replay=True)
            atomic_json(evidence, record)
        print(f"{release_id}: verified", flush=True)


def report_series(args, releases: dict) -> None:
    ops = BigQueryOps(args.project, "aviation", "europe-west3")
    ops.max_bytes_billed = args.max_bytes_billed
    rows = ops.sql(f"""
        SELECT release_id, COUNT(*) AS total_rows, COUNTIF(status = 'labeled') AS labeled_rows,
               APPROX_QUANTILES(IF(status = 'labeled', taxi_in_s, NULL), 100)[SAFE_OFFSET(10)] AS p10_s,
               APPROX_QUANTILES(IF(status = 'labeled', taxi_in_s, NULL), 100)[SAFE_OFFSET(50)] AS p50_s,
               APPROX_QUANTILES(IF(status = 'labeled', taxi_in_s, NULL), 100)[SAFE_OFFSET(90)] AS p90_s
        FROM {ops.qualified(GEOMETRY_TABLE)}
        WHERE release_id BETWEEN '{next(iter(releases))}' AND '{next(reversed(releases))}'
        GROUP BY release_id
        ORDER BY release_id
    """)
    actual = {row["release_id"]: (row["total_rows"], row["labeled_rows"]) for row in rows}
    expected = {rid: (local["counts"]["rows"], local["counts"]["labeled_rows"])
                for rid, local in releases.items()}
    if actual != expected:
        differences = sorted(rid for rid in actual.keys() | expected.keys()
                             if actual.get(rid) != expected.get(rid))
        raise ValueError(f"series does not reconcile: {', '.join(differences)}")
    write_findings(args.evidence_dir, "series", rows, ops.query_jobs)


def report_local(args, releases: dict) -> None:
    rows = []
    for release_id, local in releases.items():
        parquet = args.release_dir / release_id / "data/part-0001.parquet"
        data = pq.read_table(parquet, columns=["status", "taxi_in_s"])
        labeled = pc.filter(data["taxi_in_s"], pc.equal(data["status"], "labeled"))
        percentiles = pc.quantile(labeled, q=[0.1, 0.5, 0.9], interpolation="nearest").to_pylist()
        rows.append({"release_id": release_id, "total_rows": local["counts"]["rows"],
                     "labeled_rows": local["counts"]["labeled_rows"],
                     **dict(zip(("p10_s", "p50_s", "p90_s"), percentiles, strict=True))})
    write_findings(args.evidence_dir, "local-series", rows, None)


def write_findings(directory: Path, prefix: str, rows: list[dict], query_jobs: list | None) -> None:
    total = sum(row["total_rows"] for row in rows)
    labeled = sum(row["labeled_rows"] for row in rows)
    coverage = labeled / total if total else 0
    source = "Local Parquet baseline" if query_jobs is None else "BigQuery reconciliation"
    lines = ["# Frankfurt Geometry v2 findings", "", f"{source} for {len(rows)} monthly releases. "
             f"{labeled:,} of {total:,} candidates are labeled ({coverage:.1%}).",
             "", "Taxi-in is an ADS-B proxy. Percentiles are in seconds and use labeled candidates.",
             "", "| Release month | Candidates | Labeled | Coverage | P10 | Median | P90 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        coverage = row["labeled_rows"] / row["total_rows"] if row["total_rows"] else 0
        lines.append(f"| {row['release_id'].removeprefix('geometry-v2-')} | {row['total_rows']:,} "
                     f"| {row['labeled_rows']:,} | {coverage:.1%} "
                     f"| {row['p10_s']} | {row['p50_s']} | {row['p90_s']} |")
    if query_jobs is not None:
        report_bytes = sum(job["bytes_billed"] for job in query_jobs)
        lines.extend(["", f"The report query billed {report_bytes / MIB:g} MiB."])
    atomic_json(directory / f"{prefix}-report.json", {"months": rows, "query_jobs": query_jobs})
    atomic_text(directory / f"{prefix}-findings.md", "\n".join(lines) + "\n")
    print(f"{source}. {len(rows)} releases, {total} rows, {labeled} labeled.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "import", "report", "local-report"))
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--first", required=True, help="first month, YYYY-MM")
    parser.add_argument("--last", required=True, help="last month, YYYY-MM")
    parser.add_argument("--project")
    parser.add_argument("--landing-bucket")
    parser.add_argument("--gold-bucket")
    parser.add_argument("--uploader")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--max-bytes-billed", type=int, default=100 * MIB)
    args = parser.parse_args()
    if args.mode != "plan" and not args.evidence_dir:
        parser.error("this mode requires --evidence-dir")
    if args.mode in ("import", "report") and not args.project:
        parser.error("import and report require --project")
    if args.mode == "import" and not all((args.landing_bucket, args.gold_bucket, args.uploader)):
        parser.error("import requires --landing-bucket, --gold-bucket and --uploader")
    if args.max_bytes_billed <= 0:
        parser.error("--max-bytes-billed must be positive")
    try:
        releases = {}
        for month in release_months(args.first, args.last):
            release_id = f"geometry-v2-{month}"
            releases[release_id] = local_release(args.release_dir / release_id, release_id)
        if args.mode == "plan":
            print(json.dumps(releases, indent=2))
            return
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        with (args.evidence_dir / ".series.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.mode == "report":
                report_series(args, releases)
            elif args.mode == "local-report":
                report_local(args, releases)
            else:
                import_series(args, releases)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        parser.exit(1, f"Geometry series: {exc}\n")


if __name__ == "__main__":
    main()
