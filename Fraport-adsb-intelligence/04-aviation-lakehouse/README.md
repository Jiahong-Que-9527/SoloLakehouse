# 04 · Aviation Lakehouse Integration

Project 04 uses **Databricks Free Edition** for Spark, managed Delta tables,
Unity Catalog and Serverless Jobs. Its Bronze, Silver and Gold layers begin
with a Geometry v2 release staged in a Unity Catalog **managed volume**. The
OpenSky observations and the original aviation Bronze and Silver remain in
the acquisition and transformation projects.

**Status (2026-11-23)** All 24 Geometry v2 releases passed a local Delta Lake
rehearsal and reconciled against M5 BigQuery. Free Edition workspace
acceptance and the Databricks CLI smoke test are pending.

## Schema mapping and quality checks

| Delta table | Grain and fields | Validation |
|---|---|---|
| `aviation_bronze_release` | `(release_id, day_utc, flight_key)` with all 15 published Parquet fields and release lineage | Checks the two manifest payload checksums, passed gate, approval, completion marker, schema and expected row count |
| `aviation_silver_arrivals` | Same grain and fields, plus `is_labeled` | Checks the release month, reconstructed event key, uniqueness, known statuses and labeled event chronology. The target must equal taxi end minus surface start and fall within the release bounds |
| `aviation_gold_taxi_in_labels` | Same grain for labeled rows. Keeps the event key, release ID, manifest SHA-256, label version, release creation time and `taxi_in_s` | Publishes labels after Bronze and Silver read-back. Reports total candidates and status counts alongside the label coverage |

A run compares the persisted slice to the expected rows and reports the Delta
version and a deterministic SHA-256 for each table. Replays reuse matching
slices and reject differences. A run interrupted between tables resumes from
its matching slices. The three tables commit independently, and job success
records the completed release after all three checks.

## Local release rehearsal

```bash
cd Fraport-adsb-intelligence/04-aviation-lakehouse
uv sync --locked
uv run --locked python -m unittest discover -v

release=/home/bill/slh-data/full-20241101-20261031-geometry-v2/releases-geometry-v2/geometry-v2-2024-11
out=$(mktemp -d /tmp/fraport-lakehouse.XXXXXX)
uv run --locked python lakehouse.py "$release" --local-delta "$out/delta" > "$out/first.json"
uv run --locked python lakehouse.py "$release" --local-delta "$out/delta" > "$out/replay.json"
```

The accepted November 2024 input produced 17,051 rows each in Bronze and
Silver and 13,413 rows in Gold (78.7% of candidates), matching the M5 BigQuery
receipt. The repeat reproduced all three table hashes and versions. December
appended 16,218 candidates and 13,079 labels. A November replay after that
append reused the November rows without advancing any table version.
All 24 months together reconciled to 433,694 candidates and 400,942 labels.

## Free Edition workspace acceptance

Use a writable Unity Catalog catalog, an isolated schema such as
`fraport_free_pilot`, a managed input volume and Serverless compute. Keep this
pilot in the Free Edition allowance. The private GCS Landing bucket stays in
project 03. Direct GCS access through a storage credential and external
location is deferred and carries its own acceptance evidence if taken up
later. [Free Edition limits](https://docs.databricks.com/gcp/en/getting-started/free-edition-limitations)
· [Managed volumes](https://docs.databricks.com/gcp/en/volumes/)

1. Run the synthetic Geometry v2 release in a compatible Spark 4 Python
   environment. A managed volume holds the complete release directory with
   its manifest, contract, validation, approval, completion marker and
   `data/part-0001.parquet`. The expected counts are 3 Bronze, 3 Silver and
   2 Gold. The prepared interactive Notebook can stage its embedded fixture
   in the volume. [Serverless environments](https://docs.databricks.com/gcp/en/release-notes/serverless/environment-version/)
2. Replay the same release and record all three table hashes and Delta
   versions. Acceptance requires matching counts and hashes, all three
   slices marked `reused`, and unchanged table versions. Run serially in the
   pilot schema. Users who create the pilot objects need the corresponding
   Unity Catalog privileges on that catalog and schema.
3. Once the synthetic path passes, a monthly release may be tested in the
   same managed-volume workflow if it is approved for transfer to the
   workspace. For November 2024, the reference counts are 17,051 Bronze and
   Silver rows and 13,413 Gold labels (78.7% coverage). The two-year series
   has already been reconciled locally against BigQuery.

## Databricks CLI plan

The CLI has workspace import, managed-volume file and Jobs commands for this
workflow. The first test is interactive workspace OAuth and read access in the
actual Free Edition workspace. CLI support for this project is accepted after
that workspace returns the synthetic result and replay evidence. [CLI authentication](https://docs.databricks.com/gcp/en/dev-tools/cli/authentication)
· [CLI command reference](https://docs.databricks.com/gcp/en/dev-tools/cli/commands)

| Step | Planned check |
|---|---|
| 1. Authenticate | Register the Free Edition workspace in the browser and install the current Databricks CLI locally. Run `databricks auth login --host "$workspace_url" --profile fraport-free`, complete the browser sign-in, then run `databricks current-user me --profile fraport-free` and `databricks workspace list / --profile fraport-free`. Use workspace-level user OAuth. |
| 2. Import a synthetic launcher | Prepare a reproducible Notebook from the current `lakehouse.py` and a synthetic release, then use `databricks workspace import "$notebook_path" --format JUPYTER --file "$notebook_file" --profile fraport-free`. Use a new pilot path on first import. The embedded fixture lets the Notebook create and seed the managed volume. For a separately approved input file, the later upload path is `databricks fs cp` with a `dbfs:/Volumes/...` destination. |
| 3. Submit a single run | Use `databricks jobs submit --json @run.json --profile fraport-free` with one Serverless notebook task targeting the imported workspace path, a finite task timeout and no schedule. The Notebook runs the first publish and replay serially and returns compact JSON through `dbutils.notebook.exit`. The output-return step is part of the planned CLI launcher. |
| 4. Save acceptance evidence | Use `databricks jobs get-run` to capture the run status and task run ID. Use `databricks jobs get-run-output` with that task run ID and save the JSON locally. Check the synthetic 3/3/2 counts and replay hashes and versions. Record the tested CLI version and workspace capabilities. |

If the workspace blocks OAuth or a required Jobs operation, use the Free
Edition UI to import the Notebook and run it, then record which CLI step was
unavailable. Keep automated CI and account-level operations outside this
pilot. [Workspace import](https://docs.databricks.com/gcp/en/dev-tools/cli/reference/workspace-commands)
· [Volume file commands](https://docs.databricks.com/gcp/en/dev-tools/cli/reference/fs-commands)
· [Jobs CLI](https://docs.databricks.com/gcp/en/dev-tools/cli/reference/jobs-commands)

## Handoff to taxi-in prediction

`aviation_gold_taxi_in_labels` is the outcome table. `taxi_in_s` is the
Geometry v2 ADS-B proxy target. The flight key embeds OpenSky `lastseen` and
serves as retrospective join metadata. Treat the key, date, label version,
and release creation time as metadata. The creation timestamp provides
release lineage and does not establish when a feature became available.

Project 05 needs a separate observation-time feature source and a prediction
cutoff supplied by an event available to the scoring system. Require both
feature event time and availability time to be at or before that cutoff, and
retain source/version lineage for each feature. The published touchdown
estimate, taxi-end time, surface-window statistics, callsign and candidate
selection have no verified point-in-time availability in this release. The
Gold allowlist exposes no predictive features. Use labeled-target coverage
when reporting training and evaluation scope.
