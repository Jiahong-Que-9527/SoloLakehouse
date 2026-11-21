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
  ingestion adds no rows.
- **M4.** Analytics model and core queries with expected results on a fixed
  sample.
- **M5.** Full dataset release, cost record and findings report.

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
