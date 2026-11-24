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
- **M5.** Full dataset release, cost record and findings report.

### Geometry v2 handoff (M5)

1. Confirm that `local-verification.json` in the
   [active backfill directory](../02-aviation-transformation/README.md#backfill-status-and-handoff)
   lists all 24 release IDs from `geometry-v2-2024-11` through
   `geometry-v2-2026-10`. Check that every monthly date is either present
   or recorded as missing.
2. Check `logs/cloud-pilot.log` and `cloud-pilot-verification.json` in
   that directory. The approved November 2024 pilot is queued behind
   local verification. Its destination is the private Frankfurt dataset
   `slh-gcp-test.aviation`, table `ground_ops_arrivals_geometry_v2`.
   Expect **17,051 rows**, **13,413 labeled rows**, **0 duplicate
   (day_utc, flight_key) keys**, and **0 rows added by a repeat import**.
   Record the BigQuery job IDs and bytes billed.
3. If the pilot stops, check the error before retrying. Reuse an existing
   Landing object only if its checksum matches the local package. For a
   retry, use the same release ID and geometry table, and keep the
   pilot's 100 MiB per-query cap.
4. After the pilot reconciles, size the remaining 23 packages and assess
   their import under the repository's GCP cost rules. Then schedule
   the remaining imports sequentially, reconcile each release, and
   write the cost and findings report. Use the geometry table for the
   series and report taxi-in as an ADS-B proxy.

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
