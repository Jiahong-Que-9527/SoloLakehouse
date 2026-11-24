"""Audit measured feature availability before a local EDDF serving pilot."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from feature_replay import FEATURES, HERE, epoch, replay, silver_inputs, summarize
from release_inputs import file_digest, read_json

RECEIPT_COLUMN = "available_at_epoch_s"
SIMULATED_DELAY = 5


def partition_status(silver: Path, day: date) -> tuple[str, dict | None]:
    folder = silver / day.isoformat()
    parquet = folder / "observations.parquet"
    if not parquet.exists() or not (folder / "run_manifest.json").exists():
        return "missing_partition", None
    schema = pq.read_schema(parquet)
    if RECEIPT_COLUMN not in schema.names:
        return "missing_receipt_column", None
    if not pa.types.is_integer(schema.field(RECEIPT_COLUMN).type):
        return "invalid_receipt_type", None
    provenance = read_json(folder / "run_manifest.json").get("availability")
    if (not isinstance(provenance, dict) or provenance.get("mode") != "observed"
            or provenance.get("timestamp_column") != RECEIPT_COLUMN
            or provenance.get("recorded_at") != "feature_input"
            or not all(isinstance(provenance.get(key), str) and provenance[key].strip()
                       for key in ("source", "clock"))):
        return "missing_observed_provenance", None
    return "observed", {key: provenance[key] for key in ("source", "clock")}


def delay_statistics(connection, start: date, end: date) -> dict:
    row = connection.execute("""
        WITH delays AS (
            SELECT CAST(available_at_epoch_s AS HUGEINT) - time_epoch_s AS delay_s,
                   time_epoch_s >= ? AND time_epoch_s < ? AS in_window
            FROM silver_observations
        )
        SELECT count(*) FILTER (WHERE delay_s IS NULL OR delay_s < 0),
               count(*) FILTER (WHERE in_window),
               count(*) FILTER (WHERE in_window AND delay_s <= ?),
               quantile_disc(delay_s, 0.50) FILTER (WHERE in_window),
               quantile_disc(delay_s, 0.95) FILTER (WHERE in_window),
               max(delay_s) FILTER (WHERE in_window)
        FROM delays
    """, [epoch(start), epoch(end), SIMULATED_DELAY]).fetchone()
    keys = ("invalid_timestamps_including_context", "observations", "within_simulated_delay",
            "median_seconds", "p95_seconds", "max_seconds")
    return dict(zip(keys, row, strict=True))


def trigger_comparison(connection, start: date, end: date) -> dict:
    # The existing replay can build the same triggers without retrospective outcomes.
    connection.execute("""CREATE TEMP TABLE outcomes (icao24 VARCHAR, day_utc DATE, flight_key VARCHAR,
                        status VARCHAR, taxi_in_s BIGINT, surface_start_epoch_s BIGINT, taxi_end_epoch_s BIGINT)""")
    outputs = [replay(connection, start, end, delay) for delay in (None, SIMULATED_DELAY)]
    for table in outputs:
        if table.num_rows:
            summarize(table)
    observed, simulated = [{row["prediction_id"]: row for row in table.to_pylist()} for table in outputs]
    shared = observed.keys() & simulated.keys()
    return {"observed": len(observed), "simulated": len(simulated), "shared": len(shared),
            "observed_only": len(observed) - len(shared), "simulated_only": len(simulated) - len(shared),
            "shared_with_changed_features": sum(
                any(observed[key][name] != simulated[key][name] for name in FEATURES) for key in shared),
            "observed_within_simulated_delay": sum(
                row["prediction_at"] - row["trigger_event_at"] <= SIMULATED_DELAY for row in observed.values())}


def audit(silver: Path, start: date, end: date) -> dict:
    if end <= start:
        raise ValueError("--until must follow --from")
    context = start - timedelta(days=1)
    partitions = {}
    for offset in range((end - context).days):
        day = context + timedelta(days=offset)
        status, evidence = partition_status(silver, day)
        partitions[day.isoformat()] = {"status": status, **(evidence or {})}
    counts = {status: sum(entry["status"] == status for entry in partitions.values())
              for status in sorted({entry["status"] for entry in partitions.values()})}
    report = {"schema_version": "frankfurt-airport-availability-audit-v1", "status": "blocked",
              "utc_from": start.isoformat(), "utc_until_exclusive": end.isoformat(),
              "context_day": context.isoformat(), "partition_counts": counts,
              "simulated_delay_seconds": SIMULATED_DELAY,
              "code_sha256": {name: file_digest(HERE / name) for name in (
                  "availability_audit.py", "feature_replay.py", "feature_replay.sql", "release_inputs.py", "uv.lock")}}
    if counts.get("observed", 0) != len(partitions):
        return report | {"reason": "missing_measured_receipt_evidence"}

    paths, pinned = silver_inputs(silver, start, end)
    report["observed_partitions"] = [{**entry, **partitions[entry["day_utc"]]} for entry in pinned]
    with duckdb.connect(config={"threads": 4}) as connection:
        connection.read_parquet(paths, union_by_name=True).create_view("silver_observations")
        stats = delay_statistics(connection, start, end)
        report["observation_delays"] = stats
        if stats["invalid_timestamps_including_context"]:
            return report | {"reason": "invalid_measured_timestamps"}
        if not stats["observations"]:
            return report | {"reason": "empty_observation_window"}
        report["arrival_triggers"] = trigger_comparison(connection, start, end)
    if not report["arrival_triggers"]["observed"]:
        return report | {"reason": "no_observed_arrival_triggers"}
    report["status"] = "measured"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-root", type=Path, required=True)
    parser.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    parser.add_argument("--until", required=True, type=date.fromisoformat, help="exclusive UTC date")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.silver_root, args.start, args.until)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError, KeyError, duckdb.Error) as exc:
        parser.exit(1, f"availability audit: {exc}\n")
    print(json.dumps({key: report[key] for key in ("status", "partition_counts")}))
    if report["status"] == "blocked":
        parser.exit(2, f"availability audit: {report['reason']}\n")


if __name__ == "__main__":
    main()
