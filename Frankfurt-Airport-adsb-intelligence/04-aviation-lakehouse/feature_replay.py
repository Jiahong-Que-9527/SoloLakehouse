"""Publish one immutable point-in-time Geometry v2 training artifact."""

import argparse
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from release_inputs import check_silver, file_digest, load_release, read_json

HERE = Path(__file__).resolve().parent
FEATURES = ["approach_speed_mps", "approach_altitude_m", "approach_vertical_rate_mps",
            "approach_distance_m", "ground_speed_mps", "approach_age_s", "prediction_hour_utc"]
RULES = {"radius_m": 5000, "max_gap_s": 120, "match_window_s": 90}


def month_bounds(release_id: str) -> tuple[date, date]:
    start = date.fromisoformat(release_id.removeprefix("geometry-v2-") + "-01")
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def silver_inputs(root: Path, start: date, end: date) -> tuple[list[str], list[dict]]:
    paths, pinned = [], []
    for offset in range(-1, (end - start).days):
        day = (start + timedelta(days=offset)).isoformat()
        folder = root / day
        manifest_path = folder / "run_manifest.json"
        parquet = folder / "observations.parquet"
        manifest = read_json(manifest_path)
        entry = manifest["outputs"][parquet.name]
        actual_hash = file_digest(parquet)
        if (manifest["schema_version"] != "silver-eddf-v2" or manifest["dates_utc"] != [day]
                or actual_hash != entry["sha256"]):
            raise ValueError(f"Silver observation manifest mismatch for {day}")
        paths.append(str(parquet))
        pinned.append({"day_utc": day, "sha256": actual_hash,
                       "manifest_sha256": file_digest(manifest_path)})
    return paths, pinned


def replay(connection, start: date, end: date, delay: int | None):
    params = {**RULES, "start_at": epoch(start), "end_at": epoch(end)}
    if delay is None:
        availability = "available_at_epoch_s"
        invalid = connection.execute("""
            SELECT count(*) FROM silver_observations
            WHERE available_at_epoch_s IS NULL OR available_at_epoch_s < time_epoch_s
        """).fetchall()[0][0]
        if invalid:
            raise ValueError(f"missing or invalid observation availability for {invalid} records")
    else:
        params["delay_s"] = delay
        availability = "time_epoch_s + $delay_s"
    sql = (HERE / "feature_replay.sql").read_text().format(availability=availability)
    return connection.sql(sql, params=params).to_arrow_table()


def summarize(table) -> dict:
    rows = table.to_pylist()
    if not rows or len({row["prediction_id"] for row in rows}) != len(rows):
        raise ValueError("missing or duplicate predictions")
    timing = (row["prior_event_at"] <= row["trigger_event_at"] <= row["prediction_at"]
              and row["prior_event_at"] <= row["prior_available_at"] <= row["prediction_at"]
              for row in rows)
    if not all(timing):
        raise ValueError("feature observation falls after the cutoff")
    counts = Counter(row["match_status"] for row in rows)
    return {"predictions": len(rows), "match_status": dict(sorted(counts.items())),
            "label_match_rate": (len(rows) - counts["unmatched"]) / len(rows),
            "training_label_coverage": counts["matched_labeled"] / len(rows),
            "feature_nulls": {column: table[column].null_count for column in FEATURES}}


def build(silver: Path, release: Path, output: Path, delay: int | None) -> dict:
    if delay is not None and delay < 0:
        raise ValueError("simulated delay must be nonnegative")
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    lineage, labels = load_release(release)
    statuses = check_silver(labels, lineage["release_id"])
    start, end = month_bounds(lineage["release_id"])
    paths, pinned_silver = silver_inputs(silver, start, end)
    with duckdb.connect(config={"threads": 4}) as connection:
        connection.read_parquet(paths).create_view("silver_observations")
        connection.register("outcomes", labels)
        table = replay(connection, start, end, delay)
    evidence = summarize(table)
    inputs = {"label_release": lineage, "silver_observations": pinned_silver,
              "availability": {"mode": "observed" if delay is None else "simulated_fixed_delay",
                               "delay_seconds": delay},
              "rules": RULES, "training_features": FEATURES,
              "code_sha256": {name: file_digest(HERE / name) for name in (
                  "feature_replay.py", "feature_replay.sql", "release_inputs.py", "uv.lock")}}
    input_sha = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    manifest = {"feature_dataset_id": f"features-{start:%Y-%m}-{input_sha[:16]}",
                "input_sha256": input_sha, **inputs,
                "label_source_rows": len(labels), "label_source_labeled": statuses["labeled"],
                "source_label_training_fraction": evidence["match_status"].get("matched_labeled", 0)
                / statuses["labeled"], **evidence}
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        path = staged / "training.parquet"
        pq.write_table(table, path, compression="zstd")
        manifest["files"] = {path.name: {"rows": len(table), "sha256": file_digest(path)}}
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        staged.rename(output)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-root", type=Path, required=True)
    parser.add_argument("--label-release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simulated-delay-seconds", type=int,
                        help="historical availability assumption in seconds; omit for recorded availability")
    args = parser.parse_args()
    try:
        manifest = build(args.silver_root, args.label_release, args.output, args.simulated_delay_seconds)
    except (OSError, ValueError, KeyError, duckdb.Error) as exc:
        parser.exit(1, f"feature replay: {exc}\n")
    print(json.dumps({"feature_dataset_id": manifest["feature_dataset_id"],
                      "predictions": manifest["predictions"], "match_status": manifest["match_status"]}))


if __name__ == "__main__":
    main()
