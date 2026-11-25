# 03 · Airport Analytics

**Runtime:** Google Cloud: Cloud Storage, BigQuery and the Gold table layer.
Managed with Terraform.

Receive Gold releases from project 02, turn them into managed cloud tables and
answer operational questions about Frankfurt Airport traffic with SQL. This is
the main GCP infrastructure and CI/CD project in the programme.

## Scope

- **Infrastructure as code.** Terraform for the Landing bucket, the Gold
  storage, identities with least privilege, budget alerts and the BigQuery
  datasets. A GitHub Actions pipeline runs plan and apply.
- **Landing.** A private bucket that receives releases with a create-only
  upload. The upload identity cannot read other data.
- **Release ingestion.** A job checks the manifest, contract and checksums,
  then materialises the Gold tables. Ingesting a release twice does not
  duplicate rows. Each table row carries its release ID.
- **Table format.** Apache Iceberg — decided by the ADR-004 spike
  (2026-11-21): BigQuery managed Iceberg tables on a colocated bucket,
  written by BigQuery DML over a BigLake connection, in `europe-west3`.
  [ADR-004](../docs/adr/ADR-004-gold-table-format-and-catalog.md) is
  Accepted with the spike evidence in [spike](spike/).
- **Analytics.** A documented model with grain and keys. Reusable views for
  traffic volume, arrival rate by hour, runway-area activity and surface-time
  distributions. Query cost recorded for the main queries.
- **Synthetic data.** The full flow runs on synthetic releases, so a fork needs
  only its own GCP project.

## Release ingestion (M3)

**[GLM·2026-11-21]** `ingest_release.py` ingests one release folder from the
landing bucket: download → verify (manifest checksums, gate `passed`,
contract covered by the manifest) → ledger + release_id guards → managed
Iceberg table (`CREATE TABLE IF NOT EXISTS`, cluster by `release_id`) →
guarded insert → row reconciliation against the manifest → ledger record.
An `ingest_ledger` table records every accepted release; a release whose
gate is `blocked` never reaches a table.

```bash
uv run --locked python ingest_release.py \
  --landing gs://<project>-aviation-landing/releases/v002 \
  --project <project> --gold-bucket <project>-aviation-gold
```

Recorded runs (2026-11-21, project `slh-gcp-test`):

- Synthetic release (`synthetic-v001`, 3 rows, uploaded through the
  create-only `aviation-upload` identity): ingested, 3 rows reconciled;
  two repeat runs returned `already_ingested` with 0 rows added.
- Real `v002` (4,656 rows, 179.6 KB): ingested, repeat run added 0 rows.
  The analytics query over the table returns exactly the release coverage
  numbers (2,583 labeled of 4,656, avg taxi-in 2.2 min).
- Gate-blocked release (`bad-v001`, `label_coverage` failed): refused with
  `status: blocked` and the failed check names; exit 1; no table touched.
- The `aviation-upload` identity cannot read or overwrite landing objects
  (`storage.objects.get`/`delete` denied) — release immutability is
  enforced by IAM, not by convention.

The ingestion target follows the release manifest's `label_version`.
Radius v1 and historical radius releases use `ground_ops_arrivals` by
default. `taxi-in-geometry-v2` with contract version 2 uses
`ground_ops_arrivals_geometry_v2`. The existing three views query the
radius table. Use the geometry table when analysing a geometry-only
series.

## Analytics model (M4)

**[GLM·2026-11-21]** Three reusable views over `ground_ops_arrivals`, each
carrying `release_id` so results always trace to their release:

| View | Grain | Answers |
|------|-------|---------|
| `v_arrival_traffic` | (release_id, day_utc, status) | traffic volume per day and coverage status |
| `v_arrival_hourly` | (release_id, day_utc, hour_utc) | arrival rate by hour of day |
| `v_surface_time` | (release_id, day_utc) | labeled taxi-in distribution (avg/median/min/max), taxi path, gaps over 30 s |

Runway-area activity has no view: the `ground_ops` market carries no runway
evidence, and inventing coverage the release does not have would break the
findings discipline (ADR-006). It arrives with a future market.

```bash
uv run --locked python analytics_views.py \
  --project <project> --expected expected_results.json
```

`--expected` verifies the views on the fixed sample (release `v002`,
pilot week): per-day candidate and labeled counts from the recorded gold
run, status totals from the release coverage report — 16 checks, all
passing (2026-11-21). Query cost for the three view queries on the sample:
130 KB + 168 KB + 192 KB processed ≈ 0.5 MB, €0 inside the free tier.
5 synthetic tests cover the verification logic (tampered rows must fail).

## Milestones

- **M1.** ADR-004 spike on synthetic data, with the result recorded. Done
  (2026-11-21, on the real `v002` release — all five checks passed in
  `europe-west3`, measured cost €0; evidence in [spike](spike/)).
- **M2.** Terraform creates the bucket, identities and budget alerts. CI runs
  plan on pull requests. Implemented (2026-11-21,
  [infra](infra/): landing + gold buckets, `aviation` dataset, BigLake
  connection, create-only upload identity vs runtime identity, €50 monthly
  budget alert; CI plan on PRs, apply on main behind the `gcp-test`
  environment gate).
- **M3.** Ingest the synthetic release and then release `v001`. A repeat
  ingestion adds no rows. Done (2026-11-21, [ingest_release.py](ingest_release.py)):
  synthetic release and the real `v002` both ingested; repeat runs return
  `already_ingested` and add 0 rows; a gate-blocked release is refused with
  its reason. Recorded runs below.
- **M4.** Analytics model and core queries with expected results on a fixed
  sample. Done (2026-11-21, [analytics_views.py](analytics_views.py)):
  three reusable views deployed and verified against the release `v002`
  sample; runway-area activity is deliberately absent because the
  `ground_ops` market carries no runway evidence (ADR-006). Recorded run
  below.
- **M5.** Two-year Geometry v2 release, cost record and findings report.
  Accepted 2026-11-23. All 24 releases reconciled in BigQuery.

### Geometry v2 handoff (M5)

The [local backfill](../02-aviation-transformation/README.md#backfill-status-and-handoff)
verified all 24 releases and 730 Silver dates on 2026-11-22. The first cloud
attempt stopped at a `403` on `contract.yaml` because `gcloud storage cp`
attempted a read with the create-only identity. `upload_release.py` uses a
conditional create against Cloud Storage. When an object already exists, a
reader checks its SHA-256 before reuse. `_SUCCESS` goes up last. A checksum
mismatch stops the upload.

**Pilot accepted 2026-11-23.** The upload rerun verified and reused all six
objects. The first ingestion attempt inserted the release but its acceptance
query failed on an SQL alias. Recovery kept the existing rows and recorded
the ledger entry after the corrected query passed. Recovery and the ingestion
rerun each verified 17,051 rows, 13,413 labeled rows and zero duplicate keys.
The ingestion rerun added zero rows. The two successful ingestion runs billed
50 MiB combined. The run directory holds `cloud-pilot-verification.json` with
the job IDs, individual bytes billed and upload replay result.

From this directory, use Application Default Credentials (ADC) with permission
to impersonate `aviation-upload`. The upload command can use `--reader` to
impersonate a separate reader if ADC itself lacks Landing read access and can
impersonate the reader. The accepted pilot used ADC for reads.

```bash
run_dir=/home/bill/slh-data/full-20241101-20261031-geometry-v2
uv run --locked python upload_release.py \
  "$run_dir/releases-geometry-v2/geometry-v2-2024-11" \
  --project slh-gcp-test --landing-bucket slh-gcp-test-aviation-landing \
  --uploader aviation-upload@slh-gcp-test.iam.gserviceaccount.com
```

After upload succeeds, run ingestion with ADC for the ingestion identity or an
operator with the equivalent storage and BigQuery permissions. Keep the
100 MiB per-query cap and save each successful run's JSON under the run
directory. The JSON includes BigQuery job IDs and bytes billed.

```bash
pilot_ingest() {
  uv run --locked python ingest_release.py \
    --landing gs://slh-gcp-test-aviation-landing/releases/geometry-v2-2024-11 \
    --project slh-gcp-test --gold-bucket slh-gcp-test-aviation-gold \
    --max-bytes-billed 104857600 --expect-geometry-labels 13413
}
pilot_ingest > "$run_dir/cloud-pilot-ingest.json" &&
  pilot_ingest > "$run_dir/cloud-pilot-repeat.json"
```

Accept the pilot when both runs report **17,051 rows**, **13,413 labeled rows**
and **0 duplicate `(day_utc, flight_key)` keys** in
`ground_ops_arrivals_geometry_v2`, and the repeat reports `rows_added: 0`.
If a run stopped, inspect its output before retrying with the same release ID
and table.

**December 2024 accepted.** The monthly runner reconciled 16,218 rows,
13,079 labeled rows and zero duplicate keys. The repeat added zero rows.
The import billed 50 MiB and the repeat billed 10 MiB. The evidence is
`cloud-series/geometry-v2-2024-12.json` under the run directory.

`geometry_series.py plan` verifies the checksums, label version and Parquet
counts for a date range before any cloud operation. `import` walks the same
range in month order and writes a JSON checkpoint after acceptance. Rerunning
the same command skips verified months. `--replay` also verifies that a
second ingest adds zero rows.

**Full series accepted 2026-11-23.** The 22 releases from January 2025
through October 2026 passed individual BigQuery checks for total rows,
labeled rows and duplicate `(day_utc, flight_key)` keys. The series query
reconciled all 24 releases from November 2024 through October 2026 against
the local packages. There are 433,694 candidates and 400,942 labeled rows
(92.4%). Monthly label coverage ranged from 67.0% in June 2025 to 99.1% in
November 2025. The median taxi-in proxy among labeled candidates ranged
from 198 to 489 seconds in those same months. Coverage varies enough that
month-to-month comparisons should be interpreted together with those rates.

The 22-release import billed 1,100 MiB across 176 BigQuery jobs and the
report billed 16 MiB. The largest individual job billed 20 MiB against
the 100 MiB per-query cap. These totals cover the final batch and report.
The `cloud-series/` directory under the active run holds the month-level
receipts and the report with BigQuery job IDs and billed bytes.

After the cloud import, run `geometry_series.py report` for 2024-11 through
2026-10. It checks the monthly counts against the local releases and writes
`series-report.json` and `series-findings.md`. `local-report` writes the
corresponding Parquet baseline without querying the cloud. All modes take
`--release-dir`, `--first` and `--last`. The import and report commands use
`--evidence-dir`, `--project`, and an optional `--max-bytes-billed` with a
100 MiB default. Import also needs `--landing-bucket`, `--gold-bucket` and
`--uploader`. The local-report command takes `--evidence-dir` for its output.

## Acceptance

- A repeat ingestion of the same release adds no rows.
- A release that fails validation is not ingested.
- Every table has a documented grain and a uniqueness check.
- Query results reconcile with the release manifest row counts.
- Findings state the data period, source and known limits. Surface times are
  proxies from state vectors, not airport ground truth.
- Deployment and runtime identities are separate and documented.

## Depends on

Project 02 Gold releases. M1 to M3 can start with the synthetic release.

## Outputs

Cloud infrastructure code, Gold tables, a model description and an analytics
report. Project 05 uses the same definitions for features.
