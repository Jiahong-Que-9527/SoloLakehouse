# Dataset summary · `eddf_r75km` v1 and `eddf_flights` v1

**Generated:** 2026-11-25 (M5 sign-off). Source record:
`/home/bill/slh-data/aviation/metadata/datasets/dataset_summary.json`.
The machine-readable summary, the manifest Parquet tables, the dataset
contract and the DuckDB catalog live next to it in `metadata/datasets/`.

## Result

The five-year window `[2021-11-01, 2026-11-01)` is collected, verified and
backed up. Every one of the 43,824 expected state-vector hours and all 1,827
flight days has a terminal state: `complete`, `empty` or `source_gap`. There
are no pending and no failed units anywhere in the dataset.

| Measure | State vectors `eddf_r75km` v1 | Flights `eddf_flights` v1 |
|---------|------------------------------:|--------------------------:|
| Expected units | 43,824 hours | 1,827 days |
| Complete | 33,661 (76.8%) | 1,425 (78.0%) |
| `empty` (no rows inside the box) | 3 | 0 |
| `source_gap` (documented source hole) | 10,160 | 402 |
| Failed / pending | 0 | 0 |
| Rows | 4,601,043,115 | 1,659,236 |
| Bytes (Parquet, ZSTD) | 88.3 GB | 8.5 GB |
| Unique `icao24` | 28,842 | 9,476 |
| First / last data | 2022-08-12T05Z / 2026-10-31T23Z | 2022-07-06 / 2026-11-01 |

The complete share is below 100% because OpenSky's global
`state_vectors_data4` table does not exist for most of 2022 (March 2022
through November 2022 is empty except for isolated islands, the longest at
2022-08-12T05Z and 2022-11-04T22Z) and because of the documented gaps in
December 2022, January 2023 and elsewhere. The 21 known gaps cover 10,302
hours; 10,160 hours committed as `source_gap` because their global partition
was empty, while the remaining gap hours still had a global partition and
committed `complete`. The three `empty` hours (2023-10-13T23Z,
2023-10-14T01Z, 2026-05-25T21Z) are inside the EDDF box only. Every
non-complete unit is explained by the reference data in
`configs/reference/known_gaps.yaml`.

## Processing epochs

| Epoch | Start | State-vector rows |
|-------|-------|------------------:|
| A | before 2026-08-13T12:10Z | 4,298,921,497 |
| B | 2026-08-13T12:10Z (decoder and state-vector fixes) | 3,110,236 |
| C | 2026-08-14T08:10Z (performance refactor) | 299,011,382 |

Two hours straddle an epoch boundary (2026-08-13T12Z and 2026-08-14T08Z) and
carry the boundary flag from b06.

## Per-month coverage

`complete` is complete hours; rows are state-vector rows. Flight days are
source days whose partition carried EDDF flights. b01 also owns the extra
flight day 2026-11-01, so its flight-day count is 32.

| Batch | Month | Complete | Rows | Bytes | Flight days | Flight rows |
|-------|-------|---------:|-----:|------:|------------:|------------:|
| b01 | 2026-10 | 744/744 | 109,641,931 | 2.13 GB | 32 | 40,844 |
| b02 | 2026-07 | 744/744 | 121,955,581 | 2.33 GB | 31 | 40,596 |
| b03 | 2026-01 | 714/744 | 89,882,973 | 1.53 GB | 28 | 26,637 |
| b04 | 2026-04 | 720/720 | 102,748,798 | 1.95 GB | 30 | 33,852 |
| b05 | 2026-09 | 720/720 | 120,648,884 | 2.26 GB | 30 | 39,580 |
| b06 | 2026-08 | 744/744 | 121,391,958 | 2.26 GB | 31 | 40,021 |
| b07 | 2026-06 | 720/720 | 113,094,102 | 2.15 GB | 30 | 38,682 |
| b08 | 2026-05 | 741/744 | 115,582,748 | 2.18 GB | 31 | 40,416 |
| b09 | 2026-03 | 744/744 | 102,717,025 | 1.85 GB | 31 | 33,987 |
| b10 | 2026-02 | 672/672 | 84,895,854 | 1.51 GB | 28 | 28,405 |
| b11 | 2025-12 | 744/744 | 99,472,643 | 1.80 GB | 31 | 33,863 |
| b12 | 2025-11 | 720/720 | 103,472,219 | 1.85 GB | 30 | 35,562 |
| b13 | 2025-10 | 744/744 | 120,362,843 | 2.23 GB | 31 | 41,349 |
| b14 | 2025-09 | 720/720 | 123,070,660 | 2.28 GB | 30 | 41,225 |
| b15 | 2025-08 | 744/744 | 119,685,125 | 2.34 GB | 31 | 42,224 |
| b16 | 2025-07 | 744/744 | 109,673,473 | 2.21 GB | 31 | 41,821 |
| b17 | 2025-06 | 720/720 | 102,202,707 | 2.11 GB | 30 | 40,588 |
| b18 | 2025-05 | 744/744 | 110,414,775 | 2.11 GB | 31 | 38,658 |
| b19 | 2025-04 | 720/720 | 106,737,212 | 1.98 GB | 30 | 35,918 |
| b20 | 2025-03 | 744/744 | 94,835,855 | 1.83 GB | 31 | 34,604 |
| b21 | 2025-02 | 672/672 | 76,460,404 | 1.51 GB | 28 | 29,561 |
| b22 | 2025-01 | 744/744 | 75,211,438 | 1.53 GB | 31 | 30,174 |
| b23 | 2024-12 | 744/744 | 76,273,462 | 1.54 GB | 31 | 32,449 |
| b24 | 2024-11 | 720/720 | 79,196,910 | 1.62 GB | 30 | 34,142 |
| b25 | 2024-10 | 744/744 | 103,257,913 | 2.05 GB | 31 | 37,197 |
| b26 | 2024-09 | 720/720 | 102,662,366 | 2.08 GB | 30 | 39,219 |
| b27 | 2024-08 | 744/744 | 102,590,636 | 2.12 GB | 31 | 39,699 |
| b28 | 2024-07 | 744/744 | 104,000,793 | 2.15 GB | 31 | 39,625 |
| b29 | 2024-06 | 720/720 | 102,027,738 | 2.09 GB | 30 | 37,438 |
| b30 | 2024-05 | 725/744 | 95,807,540 | 1.97 GB | 31 | 37,443 |
| b31 | 2024-04 | 720/720 | 95,095,454 | 1.92 GB | 30 | 36,856 |
| b32 | 2024-03 | 744/744 | 92,374,398 | 1.75 GB | 31 | 33,171 |
| b33 | 2024-02 | 696/696 | 82,715,394 | 1.54 GB | 29 | 29,484 |
| b34 | 2024-01 | 743/744 | 83,675,860 | 1.55 GB | 31 | 30,192 |
| b35 | 2023-12 | 677/744 | 75,912,627 | 1.43 GB | 28 | 28,772 |
| b36 | 2023-11 | 716/720 | 88,573,039 | 1.65 GB | 30 | 34,084 |
| b37 | 2023-10 | 742/744 | 91,785,144 | 1.74 GB | 31 | 33,995 |
| b38 | 2023-09 | 720/720 | 110,932,377 | 2.09 GB | 30 | 38,854 |
| b39 | 2023-08 | 744/744 | 105,750,767 | 2.08 GB | 31 | 39,330 |
| b40 | 2023-07 | 744/744 | 108,601,864 | 2.15 GB | 31 | 39,360 |
| b41 | 2023-06 | 711/720 | 103,478,172 | 2.05 GB | 30 | 36,804 |
| b42 | 2023-05 | 744/744 | 104,960,659 | 2.02 GB | 31 | 35,640 |
| b43 | 2023-04 | 720/720 | 94,357,799 | 1.80 GB | 30 | 34,894 |
| b44 | 2023-03 | 744/744 | 88,920,876 | 1.69 GB | 31 | 31,395 |
| b45 | 2023-02 | 672/672 | 82,945,644 | 1.50 GB | 28 | 26,284 |
| b46 | 2023-01 | 662/744 | 72,953,873 | 1.31 GB | 31 | 25,981 |
| b47 | 2022-12 | 276/744 | 27,807,306 | 0.50 GB | 18 | 11,763 |
| b48 | 2022-11 | 1/720 | 36,372 | 0.7 MB | 8 | 4,277 |
| b49 | 2022-10 | 0/744 | 0 | 0 | 0 | 0 |
| b50 | 2022-09 | 0/720 | 0 | 0 | 0 | 0 |
| b51 | 2022-08 | 1/744 | 188,924 | 3.4 MB | 2 | 1,166 |
| b52 | 2022-07 | 0/744 | 0 | 0 | 2 | 1,155 |
| b53 | 2022-06 | 0/720 | 0 | 0 | 0 | 0 |
| b54 | 2022-05 | 0/744 | 0 | 0 | 0 | 0 |
| b55 | 2022-04 | 0/720 | 0 | 0 | 0 | 0 |
| b56 | 2022-03 | 0/744 | 0 | 0 | 0 | 0 |
| b57 | 2022-02 | 0/672 | 0 | 0 | 0 | 0 |
| b58 | 2022-01 | 0/744 | 0 | 0 | 0 | 0 |
| b59 | 2021-12 | 0/744 | 0 | 0 | 0 | 0 |
| b60 | 2021-11 | 0/720 | 0 | 0 | 0 | 0 |

A few flight days in 2022 (for example 2 and 3 November, 6 and 7 July, 30 and
31 August) have EDDF rows in `flights_data4` even though the corresponding
`state_vectors_data4` partition is empty; those days are `complete` with only
a few flights. That is the source content, not a collection error.

## Sign-off checks

1. **Full verify** (`verify`, 2026-11-25): all 35,086 committed Parquet files
   re-hashed (96.8 GB), every manifest compared, Bronze walked for orphans,
   the SQLite index cross-checked against the manifests. Outcome: **passed,
   0 problems**. Report: `reports/verify/20261125T142231Z-24ca.json`.
2. **Restore test** (`restore-check`): b07 (a full month, 750 files), b47
   (mostly gaps, 775 units) and b48 (nearly empty, 750 units) were recovered
   from `/mnt/e/slh-backup/aviation` and hash-compared against the local
   manifests. Outcome: **passed, 0 mismatches** each. Reports under
   `reports/restore/`.
3. **Reconciliation and cross-checks** from earlier gates: the pilot week
   matched 168/168 hours against the source and 168/168 against the legacy
   fin small-box receipts; every batch sample day matched 24/24.

## Lakehouse artifacts (M4)

All under `metadata/datasets/` on the data root, regenerated with
`opensky-ingest export-manifests` and `opensky-ingest catalog`:

| File | Content |
|------|---------|
| `eddf_r75km_v1.json` | Dataset contract: bounds, SQL templates, schema, partitioning, known gaps, processing epochs |
| `hour_manifest.parquet` | One row per expected hour with status, rows, bytes, SHA256 and absolute path |
| `flight_manifest.parquet` | One row per expected flight day |
| `batch_manifest.parquet` | One row per batch with validation, acceptance and publication timestamps |
| `catalog.duckdb` | DuckDB catalog with the views `state_vectors`, `flights`, `hour_manifest`, `flight_manifest`, `batch_manifest`, `known_gaps`, `processing_epochs` |
| `dataset_summary.json` | This summary, machine-readable |
| `catalog.json` | Catalog build record |

The data views read the file lists from the manifest tables, so only
committed, accepted hours are ever visible — never quarantined or leftover
files. Silver reads the same way.

## Scope notes

- `serials` stays out of v1 (A/B test of 2026-07-15).
- Bronze is not uploaded to the cloud; the backup of record is `/mnt/e/`.
- A later incremental collection for hours older than 48 h remains a
  separate decision and needs unattended OpenSky login.
