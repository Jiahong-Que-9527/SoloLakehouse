# 04 · Point-in-Time Feature Dataset

**Runtime:** local DuckDB SQL and Python over Parquet. Project 04 builds the
versioned training dataset for [05 Taxi-in Prediction](../05-taxi-in-prediction/README.md).
Project 02 provides the accepted Geometry v2 labels, and project 03 uses the
same Gold releases for cloud analytics in BigQuery managed Iceberg.

**Status:** the November 2024 simulated feature replay produced 8,570
predictions and 7,607 usable labels. The previous platform rehearsal and
implementation are historical evidence. [Historical Delta prototype](https://github.com/Jiahong-Que-9527/SoloLakehouse/pull/262)

## Inputs and data contract

| Input | Role | What the build pins |
|---|---|---|
| Project 02 Geometry v2 Gold Parquet release | Outcome labels and label coverage | `release_id`, manifest SHA-256, label version and verified payload checksums |
| Local Silver observations and their source manifests | Candidate source for events and features | Observation partitions, checksums and the provenance of each availability timestamp |
| Feature SQL and configuration | Cutoff event, lookback windows, feature allowlist and matching rules | Code revision and configuration hash |

Choose a cutoff triggered by an event observable by the intended scoring
system. Create a stable `prediction_id` at that event and record its UTC
`prediction_at`. Build the prediction population from observations available
at that time. Select each feature only from inputs whose event time and
availability time are at or before `prediction_at`. Define how ties,
duplicates and missing observations are handled. If historical availability
cannot be established, label the dataset as a simulated replay and state the
assumption. Treat verified availability as a requirement for serving.

Join Geometry v2 outcomes after the feature rows are built. Treat `flight_key`
(which embeds OpenSky `lastseen`), the label status and release fields as
retrospective join or audit metadata. The feature allowlist excludes the
published touchdown estimate, taxi-end time and full surface-window statistics.
Keep predictions without an outcome in the denominator when reporting label
coverage. `taxi_in_s` is an ADS-B proxy target.

## Implemented replay rules

A prediction is triggered by a reported air-to-ground transition within 5 km of the
airport reference, with a preceding airborne observation at most 120 seconds
earlier. The trigger belongs to the UTC month of its event time. The replay
reads the prior day's partition for month-start context, chooses the first
available observation at each aircraft event time, and ignores stale arrivals
that come after a newer event. The seven predictor fields are listed in the
manifest. The predecessor timestamps remain available for audit.

After the feature build, match an aircraft's trigger to the nearest Geometry
v2 surface start within 90 seconds. The match must be nearest on both sides,
with stable keys breaking ties. Keep unmatched rows, rows that match an
unlabeled outcome, and outcomes that already ended at prediction time in the
artifact. Project 05 trains only on `match_status = 'matched_labeled'` and
uses the manifest's `training_features` allowlist.

The Silver archive lacks per-observation receipt times. The November pilot
assigns availability at event time plus five seconds as a simulation. Runs
without `--simulated-delay-seconds` require `available_at_epoch_s` in the source.

## First delivery

1. Run a synthetic replay that covers a late-arriving observation, duplicate
   input, an unmatched label and events around a UTC month boundary. A late
   observation with an earlier event time must be excluded from the affected
   feature row.
2. Replay one month, using the accepted November 2024 Geometry v2 release as
   the initial label input. Its 17,051 candidates and 13,413 labels are source
   checks, while replay and matching produce their own counts and coverage.
3. Write a versioned training Parquet artifact and manifest outside Git. Pin
   the source identities and feature definition, record artifact checksums,
   feature nulls and label-match rates, and verify the same logical output on
   a repeat run. Hand the manifest and dataset to project 05 for the
   chronological baseline. [Label release contract](../02-aviation-transformation/contracts/ground_ops_geometry.yaml)
   · [Cloud reconciliation](../docs/project-plan.md#phase-3-03-airport-analytics-and-cloud-gold)

```bash
cd Fraport-adsb-intelligence/04-aviation-lakehouse
uv sync --locked
uv run --locked python -m unittest discover -v
run_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
out=$(mktemp -d /tmp/fraport-feature-replay.XXXXXX)
for run in first replay; do
  uv run --locked python feature_replay.py --silver-root "$run_root/silver" \
    --label-release "$run_root/releases-geometry-v2/geometry-v2-2024-11" \
    --output "$out/$run" --simulated-delay-seconds 5
done
cmp "$out/first/manifest.json" "$out/replay/manifest.json"
cmp "$out/first/training.parquet" "$out/replay/training.parquet"
```

The November pilot matched 8,238 of 8,570 predictions (96.1%). Of the
matched outcomes, 7,607 were usable labels, 522 had no label and 109 had
already ended. The usable rows cover 88.8% of triggered predictions and 56.7%
of the source release's 13,413 labeled arrivals. The repeated run reproduced
the manifest and Parquet bytes. The five-second assumption applies to every
observation; serving still needs measured availability.

## Measured availability audit

`availability_audit.py` checks whether the serving feature input has measured
receipt times. It verifies the daily Silver manifests and Parquet checksums
for measured partitions. It reports receipt delay (median, p95, maximum and
count within five seconds), then replays arrival triggers with measured and
simulated timing on the same input. It counts triggers unique to each replay
and changes to predictors among shared triggers. This audit uses no outcome
labels and does not make a deployment decision.

Use a UTC day window and include the preceding UTC day's partition for
approach context. The existing Silver observation columns and manifest remain
the input contract. Add integer `available_at_epoch_s`, recorded when each
observation first becomes available to the feature input, with the following
`availability` entry in the daily `run_manifest.json`. Use the actual source
and describe its clock. Historical retrieval times and event-time offsets do
not establish availability to the live feature input.

```json
{
  "mode": "observed",
  "timestamp_column": "available_at_epoch_s",
  "recorded_at": "feature_input",
  "source": "<recording source>",
  "clock": "<UTC clock and synchronization method>"
}
```

```bash
uv run --locked python availability_audit.py \
  --silver-root /home/bill/slh-data/full-20241101-20261031-geometry-v2/silver \
  --from 2024-11-01 --until 2026-11-01 --output /tmp/eddf-archive-availability.json
```

The end date is exclusive. Exit 0 produces measured evidence when the window
contains observable arrival triggers. Exit 2 records a blocked audit (for
example, absent receipt fields, invalid timestamps or no observed triggers).
Exit 1 indicates a tool or input integrity error. Choose a new output path on
each run.

The archive audit covered 730 days plus one context day. All **731** daily
Parquet schemas lack `available_at_epoch_s`, and two audit runs produced
identical JSON. The next input is a measured EDDF sample from the collection
owner. [Archive audit result](evidence/availability-archive.json)
