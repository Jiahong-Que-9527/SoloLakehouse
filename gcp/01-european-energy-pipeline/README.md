# European Energy Pipeline

<!-- [Codex · 2026-11-13] Initial project directory. -->
<!-- [Codex · 2026-11-13] Project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G01 · Local implementation** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Data use and compliance](docs/data-use.md)

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
uses the metric `actual_load_mwh`. Downloading, cloud storage, BigQuery
publication and scheduling remain future work.

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

## Cloud acceptance (planned)

1. Test interval boundaries, missing intervals and duplicate keys. Include a fixture around a local-time change.
2. Deploy the job through GitHub Actions using Terraform and a federated deployment identity. Set up a scheduled run in a test environment.
3. Run the same window twice. Compare observation keys, row counts and a reference query. Record the run IDs, validation results and observed cost.

[SMARD data documentation](https://www.smard.de/home/ueber-smard) · [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/execute/jobs)
