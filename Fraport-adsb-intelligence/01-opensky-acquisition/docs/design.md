# Design: OpenSky acquisition

Implementation design for subproject 01. It covers a two-year, 75 km regional
Bronze dataset on WSL Ubuntu, collected in monthly batches and prepared for
later lakehouse ETL. The code is built in the order of section 13. Figures
marked *estimate* are replaced by pilot measurements. See the [batch plan](batch-plan.md) for the run order.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Runtime | WSL Ubuntu, local Python CLI, one process at a time |
| Source | OpenSky Trino, `minio.osky.state_vectors_data4` and `minio.osky.flights_data4` |
| Datasets | `eddf_r75km` (state vectors) and `eddf_flights` (flights, section 3.1) |
| Region | Rectangle around EDDF, about 75 km in each direction |
| Period | `[2024-11-01, 2026-11-01)` UTC, 730 days, 17,520 hours |
| Format | Parquet, ZSTD, explicit schema, sorted by `icao24, time` |
| Unit of work | One UTC hour is one query, one file and one manifest |
| Unit of delivery | One calendar month is one batch |
| Truth of state | Hour manifests. SQLite is a rebuildable index |
| Local data root | `/home/bill/slh-data/aviation` |
| Backup | `/mnt/e/slh-backup/aviation`, after each accepted batch |
| Cloud | None for this subproject. Bronze and Silver stay on this machine. Only Gold is published to the cloud ([ADR-003](../../docs/adr/ADR-003-local-bronze-silver-published-gold.md)) |
| Bronze content | Source columns only. No filtering, cleaning or derived fields |
| `serials` column | Excluded from v1. The 2026-07-15 A/B made files 1.57× larger and collection 1.76× slower |
## 2. Storage layout

The data root sits on the WSL ext4 disk. Do not use `/mnt/c` or `/mnt/e` for
primary data: they are 9p mounts and slow for many small files. `/mnt/e` holds
backups only. The Git repository holds no data and no credentials.

```text
/home/bill/slh-data/aviation/
  bronze/opensky/state_vectors/eddf_r75km/v1/
    dt=2025-01-01/hour-00.parquet ... hour-23.parquet
  bronze/opensky/flights/eddf/v1/
    dt=2025-01-01/flights.parquet
  metadata/
    datasets/eddf_r75km_v1.json        dataset contract (section 3)
    schemas/state_vectors_v1.json      column names, types, units
    reference/known_gaps.yaml          OpenSky documented data gaps
    reference/processing_epochs.yaml   OpenSky pipeline change times
    manifests/hours/dt=2025-01-01/hour-00.json
    manifests/days/dt=2025-01-01/flights.json
    manifests/batches/b01-2026-10.json
    ledger/events.jsonl                append-only event log
    state.db                           SQLite index
    catalog.duckdb                     views for inspection
  staging/<run_id>/                    in-flight files, safe to delete
  quarantine/                          files that failed validation
  reports/batches/<batch_id>/          report.md, report.json
  reports/dataset-summary.json
  logs/<run_id>.log
  _locks/ingest.lock
```

Outside the data root:

- `~/.config/sololakehouse/opensky/` holds the OAuth token cache (mode `0600`).
- `OPENSKY_USERNAME` and `SLH_DATA_ROOT` come from the environment.

Dataset path rules:

- `eddf_r75km` names the region and `v1` names the extraction contract. A change
to bounds, columns or query meaning creates a new dataset, not an overwrite.
- `dt=` is the UTC date. Hour is the file name. This gives 730 partitions and
17,520 files. The pilot day 2026-10-15 averaged 2.9 MB per file.
- Committed files are never modified.
- Hours with zero rows get a manifest and no data file.

## 3. Dataset contract

### Region

Centre: EDDF reference point, 50.0333 N, 8.5706 E.

| Edge | Value |
|------|-------|
| south | 49.36 |
| north | 50.71 |
| west | 7.52 |
| east | 9.62 |

The box is about 150 km by 150 km. Corners are about 106 km from the centre.
The box is filtered by latitude and longitude only. A circular cut is a later
Silver step.

### Query

One query per hour, no `ORDER BY`, no row limit:

```sql
SELECT time, icao24, lat, lon, velocity, heading, vertrate, callsign,
       onground, alert, spi, squawk, baroaltitude, geoaltitude,
       lastposupdate, lastcontact, hour
FROM minio.osky.state_vectors_data4
WHERE hour = :hour_epoch
  AND lat BETWEEN :south AND :north
  AND lon BETWEEN :west AND :east
```

- `hour` is the partition column. Trino rejects queries without it.
- `serials` is **excluded from v1**. On 2026-07-15 the same rows were collected
  with and without it. With the column, Parquet grew from 75.1 MB to 117.6 MB
  (1.57×) and query-plus-download grew from 95 s to 168 s (1.76×). Peak
  collection memory was 1.08 GB. Every hour's row count matched. The column
  is a list of receiver identifiers, and publication would have to anonymise
  them. v1 keeps the position record. Adding the column later needs a new
  dataset version. The comparison is in `reports/serials-ab/2026-07-15/`.
- Stale and null-contact rows stay in the data. The manifest counts rows with
`lastcontact IS NULL OR time - lastcontact > 15` so Silver can decide.
- The SQL template and its SHA256 are part of the dataset contract and every
hour manifest.

### Schema

Names, units and meaning follow the source. Types are fixed in an explicit
PyArrow schema, not inferred.

| Column | Arrow type | Notes |
|--------|-----------|-------|
| time | int64 | Unix seconds, UTC |
| icao24 | string | hex |
| lat, lon | float64 | WGS84 degrees |
| velocity | float64 | m/s |
| heading | float64 | degrees |
| vertrate | float64 | m/s |
| callsign | string | stored as received, including padding |
| onground | bool | |
| alert, spi | bool | |
| squawk | string | |
| baroaltitude, geoaltitude | float64 | m |
| lastposupdate, lastcontact | float64 | Unix seconds |
| hour | int64 | source partition, Unix seconds at hour start |
| serials | list of int32 | excluded from v1 by the 2026-07-15 A/B test |

All columns are nullable. A schema drift check runs at the start of each run
(`DESCRIBE`) and stops the run on any difference.

### Parquet settings

- ZSTD, compression level configurable (default 9, as used in the size test).
- Rows sorted by `icao24, time` before writing. This helps compression and
trajectory scans.
- Row groups of about 100k rows. Dictionary encoding and statistics on.
- No file-level metadata is required for correctness. Lineage lives in manifests.

### 3.1 Flights dataset

`flights_data4` holds one row per flight that OpenSky reconstructed from state
vectors. It adds flight-level context that state vectors lack, because a
callsign or an `icao24` alone does not identify a flight.

Limits to keep in mind (from the OpenSky documentation):

- `firstseen` and `lastseen` are not true take-off and landing times.
- Airports are inferred. They can be null or wrong.
- A callsign is not a unique flight identifier.

Design:

| Item | Decision |
|------|----------|
| Dataset | `eddf_flights` v1 |
| Path | `bronze/opensky/flights/eddf/v1/dt=YYYY-MM-DD/flights.parquet` |
| Unit of work | One source `day` partition: one query, one file, one manifest |
| Filter | `day = :day AND (estdepartureairport = 'EDDF' OR estarrivalairport = 'EDDF')` |
| Columns | All source columns, including nested `track` and candidate arrays |
| Sort | `icao24`, `firstseen`. State vectors stay sorted by `icao24`, `time` |
| Types | Fixed from `DESCRIBE`, with nested Arrow types |
| Period | Source days `[2024-11-01, 2026-11-02)`, 731 days |

The source `day` is the UTC day of `lastseen`. A flight that leaves EDDF late
on the last day ends on the next day, so the period runs one day past the
state-vector window. Silver selects flights by overlap with the window.

Flights with null or wrong airports that actually used EDDF cannot be found
this way. Silver reconstructs them from the state vectors. Bronze does not try.

Flights follow the same commit protocol, manifests, statuses, batches and
reports as state vectors. Each monthly batch collects its state-vector hours
and then its flight days. The pilot week averaged 1,330 flights and 7.4 MB a
day, with no duplicate `(icao24, firstseen)` keys. Scaled across 731 days that
is about 0.97 million rows and 5.4 GB.

## 4. Hour lifecycle and commit protocol

Hour states:

```text
pending -> fetching -> staged -> validated -> complete
                                            -> empty
                                            -> source_gap
failed (retryable)        quarantined (needs inspection)
```

`complete`, `empty` and `source_gap` are committed states. Flight days use the
same states.

Commit steps for one hour:

1. Run the query. Stream rows into Arrow batches with the per-hour budgets
   applied (section 5).
2. Sort, then write a Parquet file under `staging/<run_id>/`.
3. Re-read the staged file. Check schema, row count, bounds and the hour window.
   Compute SHA256, size and quality counters.
4. If rows is zero, run the partition probe (section 6) and skip the data file.
5. Move the file to its final path without overwriting (`link` then `unlink`),
   and fsync the file and directory.
6. Write the hour manifest through a temporary file and rename it. **The
   manifest is the commit marker.**
7. Update SQLite and append to the ledger.

Recovery rules after a crash:

- Final file without a manifest is an orphan. Move it to `quarantine/` and redo
the hour.
- Manifest without a file, or with a checksum mismatch, marks the hour `failed`.
- `staging/` content is always disposable.
- `rebuild-state` recreates SQLite from manifests and verified files.

A repeat run skips committed hours. Re-fetching a committed hour requires an
explicit new dataset version.

### Hour manifest

```json
{
  "dataset_id": "eddf_r75km", "dataset_version": "v1",
  "hour": 1793440800, "window_start": "2026-11-02T10:00:00Z",
  "status": "complete",
  "path": "bronze/opensky/state_vectors/eddf_r75km/v1/dt=2026-11-02/hour-10.parquet",
  "rows": 0, "bytes": 0, "sha256": "...", "compression": "zstd",
  "aircraft": 0, "ground_rows": 0, "stale_or_unknown_rows": 0,
  "duplicate_key_rows": 0, "min_time": 0, "max_time": 0,
  "query_id": "...", "processed_bytes": 0, "elapsed_seconds": 0.0,
  "sql_sha256": "...", "schema_version": "1.0",
  "flags": ["known_gap_overlap", "processing_epoch_boundary"],
  "processing_epoch": "C",
  "batch_id": "b01-2026-10", "run_id": "...",
  "tool_version": "...", "git_commit": "...", "collected_at": "..."
}
```

Values shown as `0` are placeholders. Paths are relative to the data root.

### SQLite index

Tables: `hours`, `batches`, `runs`, `events`. `hours` holds one row per hour
with status, attempts, counters, relative path and error class. SQLite
tracks progress and powers `status`. It is never the only record of a commit.

## 5. Source behaviour

### Authentication

- OAuth2 browser login through the Trino client. The login URL is printed and
stored with mode `0600`. The user opens it in the Windows browser. The URL,
token and password never go to logs, chat or Git.
- `login` is a separate interactive command. `run` never prompts. If the token
is missing or expired, it stops the batch cleanly with exit code 75 and the
message `AUTH_REQUIRED`.
- fin's records show a session lasting about three days. Plan one login per
working session and treat expiry as normal.

### Pacing and limits

OpenSky documents these limits: hour partition filter required, 100 GB scan
per query, two concurrent and two queued queries per user, 30 minutes per query
including queueing.

| Rule | Value |
|------|-------|
| Concurrency | 1 query at a time |
| Pause between queries | at least 0.5 s |
| Query timeout | 300 s, then cancel |
| Queue or capacity error | wait 30 s, doubling to 10 min, at most 6 tries |
| Consecutive failed hours | 3, then pause the batch |
| Per-hour row cap | 1,000,000 |
| Per-hour size cap | 400 MB serialised |
| Scan abort threshold | 20 GB per query (documented limit is 100 GB) |
| Run duration | `--max-duration`, default 3 h |
| Free disk check | at least 50 GB before each run |

The pilot day 2026-10-15 scanned 0.53 to 1.15 GB per hour for this box.
The busiest benchmark day, 2026-07-15, scanned up to 1.16 GB per hour.
Fin measured about 0.7 GB per hour for the smaller box.

### Freshness

OpenSky may still add late data for recent hours. The window ends well before
today. Later incremental runs only collect hours older than 48 h.

## 6. Quality and validation

### Reference data

- `known_gaps.yaml` lists OpenSky's documented permanent gaps. Two fall in the
window: 2026-01-02 19:00 to 2026-01-03 18:00 and 2026-01-24 08:00 to 17:00.
- `processing_epochs.yaml` marks pipeline changes at 2026-08-13 12:10 and
2026-08-14 08:10 UTC. Each hour gets an epoch label. Hours across a boundary
are flagged.
- Hours overlapping a gap are still queried and flagged `known_gap_overlap`.
They do not count as missing.

### Hour status for zero rows

| Situation | Status |
|-----------|--------|
| Zero rows, probe shows the global hour has data | `empty` |
| Zero rows, global hour also empty, hour fully inside a known gap | `source_gap` |
| Zero rows, global hour also empty, not inside a known gap | `failed` with class `SOURCE_MISSING` |
| Rows returned for an hour inside a known gap | `complete` with flag `known_gap_overlap` |
| Query error | `failed`, retried up to the attempt limit |

A `source_gap` hour has a manifest and no data file. It counts as accounted
for in completeness checks, and it is listed in the dataset summary.

A flight day is one source partition. When that partition is empty and the
day overlaps a documented gap, including a gap that covers only part of the
day, the day is committed as `source_gap`. The `known_gap_overlap` flag records
that the gap did not cover the whole day. An empty partition on a day with no
documented gap stays `SOURCE_MISSING`.

The probe is `SELECT 1 FROM ... WHERE hour = :hour LIMIT 1`.

### Checks

Hour level, always:

- File schema equals the contract.
- Row count read back equals rows streamed.
- Every row is inside the box and inside the hour window.
- `hour` column equals the partition hour.
- Counters: nulls per column, duplicate `(icao24, time)` keys, stale rows.
Duplicates are counted, not removed.

Batch level, `validate`:

- Every expected hour has a committed manifest or a flagged gap.
- No orphan files and no manifests without files.
- Batch sums equal the sum of hour manifests.
- A random sample of files is re-hashed.
- Row-count anomalies: hours far below the median for the same weekday and hour
in the batch are listed for review.

Source reconciliation, `reconcile`:

- Run aggregate queries (count, distinct aircraft, min and max time) for a
sample of hours and compare them to the files. Default sample is one random
day per batch. The pilot reconciles every hour.

Pilot cross-check against the legacy small box:

- The fin receipts for 2026-10 give rows, aircraft and time range for the
small box. Counting the same inner box in the new Parquet must match them.
Differences are reported and investigated, not silently accepted.

## 7. Records per batch

Each batch produces:

1. Hour manifests and SQLite rows.
2. `manifests/batches/<batch_id>.json`: window, expected, complete, empty,
   gap-flagged and failed hours, totals for rows, bytes, scan bytes and
    duration, run IDs, tool version, git commit, config hash and SQL hash.
3. `reports/batches/<batch_id>/report.md` and `report.json`: a per-day table,
   anomalies, flags, validation and reconciliation results.
4. Ledger events: batch started, paused, resumed, validated, accepted,
   published.
5. An acceptance record written by `accept`: who, when and notes. Publishing
   requires acceptance.

Batch states:

```text
planned -> running -> paused (auth, errors, time limit) -> running
        -> collected -> validated -> accepted -> published
```

## 8. Publish: local backup

`publish` means a verified local backup. It starts only after `accept`.

`rsync` the batch files and metadata to `/mnt/e/slh-backup/aviation/`, then
verify sizes and SHA256 against the manifests. Back up SQLite with its backup
API or after the run ends.

Nothing from this subproject goes to the cloud. Bronze is the private source
of record. Later subprojects read it from this machine, and only the Gold
product is released to cloud storage under its own contract (ADR-003).

## 9. Lakehouse readiness

- **Layout.** Hive-style `dt=` partitions work as is in DuckDB, Spark,
Databricks and BigQuery external tables. Column names and units match the
source.
- **Contract.** `metadata/datasets/eddf_r75km_v1.json` records bounds, SQL
template, schema, partitioning, version, known gaps and epochs.
- **Read through manifests.** Silver reads the list of `complete` hours from
the manifests, not a directory listing, and only from accepted batches.
Uncommitted or quarantined files are then never read.
- **Lineage tables.** `export-manifests` writes `hour_manifest.parquet` and
`batch_manifest.parquet` so lineage can be queried with the data.
- **DuckDB catalog.** Views for `state_vectors`, `hour_manifest`, `known_gaps`.
- **No compaction in Bronze.** Silver can rewrite to larger daily files. Any
compacted copy goes to a separate directory, never next to the hourly files.
- **Later formats.** Delta or Iceberg conversion can read the same Parquet.

## 10. Tool structure

Layout inside this subproject. `config`, `auth`, `trino_client`, `discover` and
`reference` exist. The rest follows the build order in section 13:

```text
pyproject.toml
configs/dataset.eddf_r75km.v1.yaml     bounds, columns, limits, paths
configs/batches.yaml                   batch list and order
configs/reference/                     known gaps, processing epochs
src/opensky_ingest/
  cli.py  config.py  auth.py  trino_client.py  discover.py  reference.py
  query.py
  plan.py  fetch.py  parquet_writer.py  schema.py  validate.py
  manifest.py  state.py  batch.py  report.py  publish.py  catalog.py
tests/
docs/
```

Commands:

| Command | Purpose |
|---------|---------|
| `login` | Interactive OpenSky login |
| `discover` | Read-only checks: tables, `DESCRIBE`, hour and day partition availability across the window |
| `benchmark` | Collect chosen days, record rows, timings, size and quality counters |
| `plan` | Expand batches into hours and show what is pending |
| `run --from T --until T [--max-duration]` | Collect pending state-vector hours. `--until` is exclusive. A batch id is added with the monthly batches |
| `collect-flights --from D --until D [--max-duration]` | Collect pending flight days. `--until` is exclusive |
| `status [--batch B]` | Progress by state |
| `validate --batch B` | Batch checks |
| `reconcile --from T --until T` | Compare every hour in the range with source aggregates. A batch sample is added with the monthly batches |
| `cross-check --from T --until T --receipts DIR` | Compare the legacy 10 km box in each hour with fin receipts |
| `report --batch B` | Write the batch report |
| `accept --batch B` | Record acceptance |
| `publish --batch B` | Back up an accepted batch to `E:` and verify it |
| `verify` | Re-hash all committed files and check manifests |
| `rebuild-state` | Recreate SQLite from manifests |
| `export-manifests`, `catalog` | Lakehouse helpers |

Python target: 3.12 or newer, managed with `uv`. Dependencies: `trino`,
`pyarrow`, `duckdb`, `pyyaml`, `pytest`.

## 11. Failure handling

| Failure | Response |
|---------|----------|
| `AUTH_REQUIRED` | Stop cleanly, exit 75, keep state. Run `login`, then `run` |
| Queue or capacity error | Backoff and retry, then pause the batch |
| Query timeout or stream break | Delete the partial, count an attempt, retry |
| Budget exceeded | Mark `quarantined`, stop the batch, review the cause |
| Schema drift | Stop the run, record the difference |
| Orphan or missing file | Quarantine or redo as described in section 4 |
| Low disk space | Refuse to start |
| WSL restart or crash | Rerun. Staging is discarded, committed hours remain |
| Concurrent run | File lock refuses it |

## 12. Test strategy

Tests use synthetic fixtures and a fake Trino client. No real OpenSky data
enters the repository.

- Resume after a crash injected at each step of the commit protocol.
- Repeat run adds no files and no manifest changes.
- Empty, failed and gap-flagged hours are distinguished.
- Schema drift, checksum mismatch and orphan files are detected.
- `AUTH_REQUIRED` produces exit 75 and leaves state intact.
- `rebuild-state` reproduces the same index.
- Path-scoped GitHub Actions run tests and lint for this directory.

## 13. Build order

1. **M0, skeleton.** Config, schema, manifest and state modules, fake client
   tests, CLI shell.
2. **M1, collect and commit.** Fetch, Parquet writer, validation and commit
   protocol against the fake client.
3. **M2, live checks.** Discovery, then one hour, one day, the pilot week and
   the benchmark days (see the batch plan). Settle the `serials` decision.
   Replace estimates with measurements. Build `discover` first so live checks
   can start before the rest of the tool is finished.
4. **M3, batches.** Reports, acceptance, backup and the monthly runs.
5. **M4, lakehouse helpers.** Manifest export and the DuckDB catalog, so
   later local subprojects can read accepted hours.
6. **M5, dataset sign-off.** Full verify, dataset summary, restore test from
   the `E:` backup.

## 14. Open items

- `E:` is confirmed as a separate physical disk, so it counts as an independent
  backup.
- The `serials` column is excluded from v1. The 2026-07-15 comparison is in
  section 3. Adding it later needs a new dataset version.
