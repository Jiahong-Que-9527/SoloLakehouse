# 2025 annual load snapshot

Accepted locally on 2026-11-17. Dataset: German actual total load from SMARD,
quarter-hour energy in MWh, normalized to UTC as `actual_load_mwh`.
This is a historical snapshot and local engineering acceptance, not a cloud
release, independent measurement validation or provider availability guarantee.

## Coverage and replay

The local window is `[2025-01-01, 2026-01-01)`, Europe/Berlin. Its UTC bounds
are `[2024-12-31T23:00:00Z, 2025-12-31T23:00:00Z)`.

| Month | Expected and actual rows | Monthly validation | Cached replay |
|---|---:|---|---|
| 2025-01 | 2,976 | Passed | Passed |
| 2025-02 | 2,688 | Passed | Passed |
| 2025-03 | 2,972 | Passed | Passed |
| 2025-04 | 2,880 | Passed | Passed |
| 2025-05 | 2,976 | Passed | Passed |
| 2025-06 | 2,880 | Passed | Passed |
| 2025-07 | 2,976 | Passed | Passed |
| 2025-08 | 2,976 | Passed | Passed |
| 2025-09 | 2,880 | Passed | Passed |
| 2025-10 | 2,980 | Passed | Passed |
| 2025-11 | 2,880 | Passed | Passed |
| 2025-12 | 2,976 | Passed | Passed |
| **Total** | **35,040** | **Passed** | **Passed** |

All 365 local dates are present. March 30 has 92 observations and October 26
has 100; other dates have 96. The yearly grid is ordered and continuous in UTC,
with 11 of 11 contiguous month boundaries. Missing/unexpected intervals,
duplicate observation keys, null/nonfinite values, invalid durations and
invalid dimensions are all zero.

There are 24 monthly processing runs: an initial execution and a verified
cache replay for each month. Per-window inputs, observations and Parquet
checksums match, and source retrieval times are preserved. These checks do
not re-query the provider or establish that historical values never change.

## Acquisition and provenance

The explicit `prepare-year --year 2025` command issued 12 sequential CSV
exports through the existing bounded downloader and shared persistent cache.
Request starts were paced at least five seconds apart. The same-day robots
policy was reused. No rate limits, access denials, export retries, redirects
or endpoint fallback occurred. Cache and access-control state were preserved.

Downloads completed between `2026-11-17T13:41:05.879930Z` and
`2026-11-17T13:42:00.763727Z`. All monthly runs and the initial annual audit
record clean source revision `48db004854ecd48ad51d53d3de452fe0a53f7247`.
Each raw `download.json` retains request parameters, exact raw SHA-256,
retrieval time, attribution, licence links and policy-check metadata.

| Month | Raw SHA-256 |
|---|---|
| 2025-01 | `2d9d72408487faf21e29e8db3938841c7579af2aee0a76a25dac7b96355cc3d9` |
| 2025-02 | `19c5156e3333a28c5cfd79fb99cc565940c5df89135d2b7e2b4f5b598f9c54c5` |
| 2025-03 | `ee1ea7a08d486260946b57ab1e80cc1e26c043991aba611b902f364798fb51c3` |
| 2025-04 | `ae0670fcf541d8b0a5c84c49ce2a2d1623c4bcae6011333130c9ea39eb4a8c37` |
| 2025-05 | `b7c979fecfc5784066f9dba4a7c8a3d1da9b3fbe156f6e31e4bfe1ad5dbb2d45` |
| 2025-06 | `2dc61cc0587008c77a79cf795aacae8f17c7352481cc6f232fa87c11c7469592` |
| 2025-07 | `9de9d41faaf937ab983674a45f06e2a6e45865f491db45238737540f33f3cffe` |
| 2025-08 | `aa6d66779bea56edb0e8a26de1f54d9efc4350edad2a8d52dbeaff71b1414596` |
| 2025-09 | `4fbe0a3cebd1018e54a0ac3441b11c70b428731c107cfb013a3f859ccc977bb7` |
| 2025-10 | `de2e47777f98934347dbba9be7a563a4bbf4e7648f25f78a9f27b6c2e09346f2` |
| 2025-11 | `501b2d3c26e778673bc4e659f87f06ccbe9f3d8b06d6c87b5647dfa5254633c0` |
| 2025-12 | `c5e7b4165b41140f2b2f8c75a72b83aff3c5ad69206c46a55b06b1139c3f3b5c` |

## Local artifacts

On the acquisition machine, under the project's ignored `output/year-2025/`:

- `runs/`: the 24 monthly run directories and their manifests/quality reports.
- `reports/audit-jvtfvjo6/`: initial annual JSON/Markdown report and dataset.
- `reports/audit-ev2zxxpy/`: independent offline re-audit and repeated export.

Both annual exports contain 35,040 rows, are 786,112 bytes, and have SHA-256
`3f8da209f76138cc0cd16c1ec93587052933af43ee757b725f9adb208789fb76`.
The dataset filename is `observations-2025.parquet`. Raw exports remain in the
shared ignored `downloads/` cache. Runtime data and reports are not in Git;
this document preserves the evidence summary.

## Reproduce and remaining work

The [annual preparation commands](../README.md#annual-preparation) reuse
already downloaded months and preserve prior runs. A failed validation or
provider restriction stops the sequence before the next month. A yearly audit
requires exactly 12 target windows and passing repeat checks before exporting
an annual dataset; missing or overlapping windows cannot pass by row count alone.

Tests cover incomplete years, leap-year counts, monthly validation failure,
provider restriction stops, cached replay and artifact changes between audit
and publication. Cloud deployment, BigQuery ingestion and historical revision
refresh remain future work. No additional year is included in this acceptance.

Source: [Bundesnetzagentur | SMARD.de](https://www.smard.de/home/downloadcenter/download-marktdaten),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Changes: numbers parsed, timestamps normalized to UTC, monthly observations
concatenated, and coverage/replay statistics computed. No official endorsement
is implied. The [data-use requirements](data-use.md) also apply to derived outputs.
