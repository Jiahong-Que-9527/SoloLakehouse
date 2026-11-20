# European Energy Pipeline

<!-- [Codex · 2026-11-13] Initial project directory. -->
<!-- [Codex · 2026-11-13] Project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->
<!-- [李淳风·2026-11-20] Link the phased implementation plan for the first cloud delivery. -->

**G01 · Local implementation** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Data use and compliance](docs/data-use.md)

Deliver a repeatable batch pipeline for German electricity-market data. Start with one week of SMARD actual total load and publish a queryable BigQuery table.

## Technical scope

Python, Cloud Storage, BigQuery, Cloud Run Jobs, Terraform and GitHub Actions.

## Input and output

- **Input.** The fixed SMARD exports in [fixtures](fixtures/README.md): one week of German actual total load, plus the 2026-10-25 local-time change. Quarter-hour energy in MWh, Europe/Berlin.
- **Output.** A normalized metric table and a versioned release record with the source window, input checksum, code revision and quality results. G02 and G04 can consume that release.

SMARD actual total load is available under CC BY 4.0. Published data and
derived outputs must retain attribution, source and licence links, and a
description of changes. Automated downloads must not impair the service for
other users. See [data use and compliance](docs/data-use.md) for the scope,
publication requirements and the separate review needed for wholesale prices.

## Local normalization

The local CLI validates a complete SMARD CSV window and writes normalized
Parquet, a quality report and a checksummed manifest. It preserves MWh and
uses the metric `actual_load_mwh`. A bounded SMARD downloader can feed this
same path. The cloud version of this path — Cloud Storage raw objects,
BigQuery publication, a Cloud Run Job and the weekly schedule — is
implemented and accepted; see [cloud verification](docs/cloud-verification.md).

From this directory, with Python 3.12 or later and uv installed:

```bash
uv sync --locked
uv run --locked energy-pipeline normalize \
  --input fixtures/Realisierter_Stromverbrauch_202606080000_202606150000_Viertelstunde.csv \
  --from 2026-06-08 --until 2026-06-15 \
  --output output
```

The downloaded CSV files stay outside Git. Obtain the exports described in
[fixtures](fixtures/README.md) before running the real-data examples. Tests
generate synthetic inputs and run without a source download or cloud access.

Dates mean Europe/Berlin local midnight; `--until` is exclusive. Optional
`--timezone Europe/Berlin` makes the source timezone explicit; other source
timezones are not supported in v1. The input must contain exactly the whole
requested window in chronological source order. The CLI does not filter a
larger file or guess missing intervals.

To process the autumn clock change:

```bash
uv run --locked energy-pipeline normalize \
  --input fixtures/Realisierter_Stromverbrauch_202610250000_202610260000_Viertelstunde.csv \
  --from 2026-10-25 --until 2026-10-26 \
  --output output
```

The normal week yields 672 rows; the autumn day yields 100 distinct UTC
intervals. Spring clock-change tests cover a 92-interval day. The parser
matches local start labels against the complete UTC timeline to resolve the
repeated hour. It accepts SMARD's nominal wall-clock end labels at DST
boundaries; every normalized interval spans 15 elapsed minutes. Because the
CSV has no offset markers, correct source order is required: swapping two
entire identical-label autumn blocks cannot be detected from timestamps alone.

Each invocation creates a new `output/<run_id>/` directory:

- `observations.parquet`: UTC start/end, area, metric, value, unit and source.
- `quality.json`: validation status, expected/validated row counts and errors.
- `manifest.json`: input/output SHA-256, window, package version, Git revision
  and dirty-worktree flag when available, processing time, attribution,
  licence links and transformations. Processing time is not a download date;
  see the fixture notes for source retrieval dates.

Repeated valid input has the same observation rows and Parquet checksum under
the locked environment, with a new run ID and processing time. Prior run
directories are preserved. Invalid CSV data produces a failed report and
manifest, no Parquet, and exit code 1. Invalid arguments or unreadable input
fail before creating a run directory. CLI argument syntax errors use exit
code 2. Output directories are published after all files are written.

```bash
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
```

[Project CI](../../.github/workflows/energy-pipeline.yml) runs these checks
on changes to this project or its workflow. Real-data tests also run when
the local CSV fixtures are present; otherwise those two tests are skipped.
The local stage does not yet add cloud `release_id` or `ingested_at` columns.

## Bounded automatic downloads

The downloader uses the CSV export endpoint called by SMARD's own download
page. It supports only German actual total load, quarter-hour MWh, and closed
windows of 1 to 31 local days ending in the past. The endpoint is a website
implementation detail, not a versioned API with a compatibility guarantee.
The downloader currently targets Linux/macOS (POSIX file locking).

For a small end-to-end run:

```bash
uv run --locked energy-pipeline download \
  --from 2026-06-08 --until 2026-06-09 \
  --cache downloads --normalize-output output
```

Without `--normalize-output`, the command retains only the raw export. Its
`quality_status=not_validated` does not certify interval or value quality.
With the option, normalization runs as a separate step; a validation failure
retains the raw export and produces a failed local report, without Parquet.

The cache stores `downloads/<request-sha256>/source.csv` and `download.json`.
The latter records the exact request, retrieval time, raw checksum, attribution,
licence and policy-check metadata. Cached bytes are checked before reuse. The
same request then needs no network access. There is no automatic refresh or
cache-expiry download; a controlled revision-refresh policy is future work.
The normalized manifest carries the download time separately from processing
time. For manual normalization, `--source-manifest <path>/download.json`
checks that the source checksum and window match before carrying provenance.

Project operating limits (not an official SMARD rate allowance):

- One active downloader per shared cache, with at least five seconds between
  request starts. Use the same persistent cache for all invocations; separate
  machines/caches are not coordinated. No batch fan-out or automatic scheduler
  is included.
- Before an uncached export, check `robots.txt`; retain that policy for 24 hours.
  Honour disallowed paths, longer crawl delays and request-rate directives.
  A 404 means no robots policy was supplied, not permission beyond the terms.
  Other unavailable or malformed policy responses stop the run.
- HTTP 401/403 persist an access-denial stop. HTTP 429 and `Retry-After`
  responses persist a cooldown and exit immediately. Missing/invalid retry
  guidance uses a one-hour cooldown. Do not rotate caches or clear state to
  evade these controls; review a denial with the provider.
- Only 502/503/504 without `Retry-After` receive up to two retries, waiting at
  least 10 then 20 seconds. Ambiguous network failures are not automatically
  resent. Long pacing waits exit for a later invocation rather than looping.
- Thirty-second network timeout, 32 MiB success-response limit, identifiable
  User-Agent, fixed HTTPS host/metric, no redirect following, no browser
  impersonation or alternate-endpoint fallback. Changed CSV headers stop.

See [data use and compliance](docs/data-use.md) for the reviewed terms and
[download verification](docs/download-verification.md) for the one-day live
check. A full-year coverage audit and continuous availability measurements
remain pending. CI uses fake HTTP responses and does not call SMARD.

## Offline coverage acceptance

The [coverage verification](docs/coverage-verification.md) records the live
June 2026 month and both 2026 clock-change days: 2,880, 92 and 100 rows.
Each window passed coverage and cached repeat checks. These bounded samples
do not establish year-round completeness, source-value accuracy or uptime.

After normalizing each selected window twice into the same run root, audit
the written artifacts without source or cloud access:

```bash
uv run --locked energy-pipeline audit \
  --runs-root output/coverage --output output/coverage-reports
```

The auditor checks Parquet schema and checksum, unique observation keys,
complete ordered UTC intervals, 15-minute durations, finite/non-null values,
dimensions, daily counts and consistency with the manifest and quality report.
A window needs at least two distinct run IDs with identical inputs,
observations, Parquet checksums and recorded retrieval time. Copying a run
directory does not count as a repeat execution.

Each audit writes a new directory containing `report.json` and `report.md`,
with per-run checks, daily coverage, hashes and code provenance. Failures
still produce reports and exit code 1. Missing/unreadable run artifacts are
reported as errors rather than ignored. Hidden staging directories are excluded.
Use a dedicated run root; keep audit output outside that root.

## Annual preparation

[2025 acceptance](docs/year-2025-verification.md): all 12 monthly windows
passed, yielding 35,040 unique continuous UTC intervals. All monthly cached
replays and 11 cross-month boundaries passed; the offline annual re-export
has the same checksum. This is a local snapshot, with raw and derived data
kept outside Git.

Prepare one completed calendar year with sequential monthly windows:

```bash
uv run --locked energy-pipeline prepare-year --year 2025 \
  --cache downloads --output output/year-2025
```

This explicit command uses the same bounded downloader and persistent cache;
it does not raise request limits or create parallel workers. Each month is
normalized once, then read from the verified cache and normalized again.
A validation error, provider denial or cooldown stops before the next month.
After resolving the cause, rerunning reuses cached months and preserves all
prior runs. Do not reset cache/control state to bypass a provider restriction.

Only a passing annual audit publishes `observations-2025.parquet` beside the
report. It requires exactly 12 monthly windows, the complete ordered yearly
UTC grid, all monthly repeat checks and 11 continuous month boundaries.
A normal year has 35,040 quarter-hour observations; a leap year has 35,136.
All raw exports, monthly runs and annual artifacts stay outside Git.

Re-audit existing runs without source requests:

```bash
uv run --locked energy-pipeline audit --year 2025 \
  --runs-root output/year-2025/runs --output output/year-2025/reports
```

This creates a new local snapshot and report; it is not a cloud release or a
freshness check. Historical corrections still require a controlled refresh
policy, and cloud delivery remains planned.

## Cloud acceptance (planned)

1. Test interval boundaries, missing intervals and duplicate keys. Include a fixture around a local-time change.
2. Deploy the job through GitHub Actions using Terraform and a federated deployment identity. Set up a scheduled run in a test environment.
3. Run the same window twice. Compare observation keys, row counts and a reference query. Record the run IDs, validation results and observed cost.

[SMARD data documentation](https://www.smard.de/home/ueber-smard) · [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/execute/jobs)
