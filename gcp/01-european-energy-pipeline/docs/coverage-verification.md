# Coverage verification

Verified on 2026-11-17 for SMARD German actual total load, in quarter-hour MWh.
This acceptance covers one complete month and both 2026 local clock changes.
It checks written data artifacts and cached replay, not independent source
reconciliation, full-year availability or measurement accuracy.

## Observed results

Dates below are Europe/Berlin; each end date is exclusive.

| Window | Expected rows | Actual rows per run | Missing | Duplicate keys | Null/nonfinite values | Replay |
|---|---:|---:|---:|---:|---:|---|
| 2026-06-01 to 2026-07-01 | 2,880 | 2,880 | 0 | 0 | 0 | Passed |
| 2026-03-29 to 2026-03-30 | 92 | 92 | 0 | 0 | 0 | Passed |
| 2026-10-25 to 2026-10-26 | 100 | 100 | 0 | 0 | 0 | Passed |

Every day in June has 96 observations. The spring day spans 23 elapsed hours;
the autumn day spans 25. All UTC intervals are ordered, unique, continuous
and 15 minutes long. Units and dimensions match the load contract. No unexpected
intervals or invalid durations were found.

Each window has two distinct successful run IDs. Both executions use the same
raw checksum and retrieval timestamp, and produce equal observations and
identical Parquet checksums. Replays ran in the network-restricted environment
using the existing cache; they did not re-query SMARD. Consequently these
checks do not test whether upstream values have since changed.

## Acquisition and provenance

Three sequential CSV exports used the same shared `downloads` cache and its
persistent pacing state. The cached robots policy from the earlier same-day
check was reused. There were no access denials, rate limits, export retries,
redirects or fallback endpoints. The [access limits](data-use.md#automated-downloads)
remain in force.

| Window | Retrieved at (UTC) | Raw SHA-256 |
|---|---|---|
| June | 2026-11-17T13:16:08.888805+00:00 | `5174a80d1a45602cda6724e48836c364c4edb40826141d0845d3a61c79285e36` |
| Spring | 2026-11-17T13:16:12.961092+00:00 | `e654c107d1fedc173ea94b95a18d26cbc438bdae5b71fb1a5a93b430380f6bf1` |
| Autumn | 2026-11-17T13:16:17.942983+00:00 | `eed51b2a912c41af7d907d8cfd0aec7d6c031ac946c2e1ea0441460ec60d9edb` |

The autumn raw checksum matches the separately downloaded fixture recorded on
2026-11-15. This comparison concerns that file only.

| Window | Parquet SHA-256, equal across both runs |
|---|---|
| June | `2c93efded521846579787cd4979a798bf920001d0b03e4d18efcdfdea751a46c` |
| Spring | `967d40d577e1c0bde65aa3c8886ecc2a1e6982c10692183edc4bbf785e0df0f5` |
| Autumn | `2b64a660bd7a1437ce55da42fcf0099b513139f92656638104bfc60c1d59dcb5` |

Run manifests record source revision `dc63735fc19be6444fbaafda7d27573fc42cd1f4`.
Initial runs record a clean worktree; replays record a dirty worktree during
audit development. The audit report also records its own source revision,
dirty flag and the SHA-256 of the audit module. Runtime data and reports remain
outside Git; this document is the versioned evidence summary.

## Reproduce

From the project directory, run the following downloads sequentially. They use
the existing downloader safeguards and stop if a command fails. Repeat the
same commands once to exercise the cache and create distinct replay runs.

```bash
uv run --locked energy-pipeline download --from 2026-06-01 --until 2026-07-01 \
  --cache downloads --normalize-output output/coverage &&
uv run --locked energy-pipeline download --from 2026-03-29 --until 2026-03-30 \
  --cache downloads --normalize-output output/coverage &&
uv run --locked energy-pipeline download --from 2026-10-25 --until 2026-10-26 \
  --cache downloads --normalize-output output/coverage

uv run --locked energy-pipeline audit \
  --runs-root output/coverage --output output/coverage-reports
```

Each audit creates a new directory with `report.json` and `report.md`. JSON
contains per-run checks, daily counts, hashes and errors; Markdown summarizes
the windows. The audit reads Parquet directly and checks it against manifests
and quality reports. Prior `passed` statuses alone are not sufficient.

Tests include same-row-count missing/duplicate substitutions, reordered rows,
invalid durations, null/infinite values, wrong units, damaged metadata,
checksum mismatches and missing repeats. Changing values between otherwise
valid runs also fails replay acceptance. Tests make no source requests.

## Remaining evidence

- A separately planned yearly audit using sequential monthly windows.
- Freshness and availability measured over repeated days, not cached replay.
- A controlled historical revision-refresh policy; no cache rotation to bypass
  provider controls.
- Cloud ingestion, duplicate prevention in BigQuery and deployment acceptance.

Source: [Bundesnetzagentur | SMARD.de](https://www.smard.de/home/downloadcenter/download-marktdaten),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Changes: timestamps converted to UTC, numeric formatting normalized, and
coverage/replay statistics computed. No official endorsement is implied.
