# Design: European Energy Data Pipeline

**G01 · Bounded download, normalization and offline coverage audit implemented; cloud delivery planned.** See the
[local CLI](../README.md#local-normalization) for commands and current scope.

Build one repeatable batch path from a public electricity metric to a queryable BigQuery table. The path is the thing this project proves: parameterised ingestion, raw retention, a quality gate, an idempotent publish, and a deployment that can be run again.

The source for this scope is the G01 section of the [subproject design note](../../../chatgpt-consulting-subprojects-design.md). The project [brief](../README.md) fixes the first dataset.

[Data use and compliance](data-use.md) records the SMARD licence, attribution,
automated-download practices and scope limits. Carry source and licence
notices into release metadata and downstream documentation. Review the
current wholesale-price terms before adding the later day-ahead price metric.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| First dataset | German actual total load, one fixed week. The brief already chose this slice. |
| Source | Local SMARD CSV exports or the bounded `download` CLI. Synthetic exports and fake HTTP responses exercise tests without network access. |
| Later metrics | Day-ahead price and generation mix use the same table and a different `metric` value. They are not required for G01 acceptance. |
| Runtime | Cloud Run Job. One execution has a start and an end. It is not a Cloud Run Service. |
| Raw store | Cloud Storage, partitioned by source date. Objects are immutable. |
| Publish | BigQuery table `energy.metric_observation`, loaded for the requested window only. |
| Business key | `(area, metric, interval_start)` |
| Repeat run | Same window and same input checksum: no key changes, a new run record. Corrected rows for that window replace those keys. |
| Schedule | Cloud Scheduler starts the job in the test project. CI uses the sample and does not need the scheduler. |
| Identity | The job runs as its own service account. GitHub Actions deploys with Workload Identity Federation. No long-lived service-account key. |
| IaC | Terraform creates the bucket, dataset, table, job, scheduler, and runtime identity. |

## 2. Boundary

In scope: one metric, one country (`DE`), one declared interval, a fixed historical window, local tests, and one deployed test environment.

Out of scope: the HTTP API (G02), event corrections (G03), the release catalog and IAM product model (G04), training (G05), and a reusable project factory (G06). This project publishes a versioned table and a release record. It does not grant consumer roles.

## 3. Architecture

```text
Local CSV  or  bounded SMARD downloader
            |
            v
Cloud Run Job
  ingest -> land raw -> validate -> publish -> write release
            |
            v
Cloud Storage raw/smard/de_load/dt=YYYY-MM-DD/
            |
            v
BigQuery energy.metric_observation
            |
            v
energy.load_release          queryable by G02 and G04
```

One process does the whole window. There is no queue in this project. Cloud Scheduler passes the window as job arguments. A manual execution uses the same arguments.

The implemented local path is `download -> immutable cache -> normalize`.
The downloader accepts at most 31 local days, fixed to German actual load.
The cache lock, persistent pacing and provider refusal/cooldown behaviour are
documented in the [README](../README.md#bounded-automatic-downloads). Cloud
Scheduler and the cloud stores shown above remain planned. Multi-worker cloud
operation needs coordination beyond the current single-cache file lock.

Historical source revisions require a later controlled refresh policy. The
current downloader reuses a checksummed snapshot indefinitely; it does not
claim that cached values remain the provider's latest version.

The offline `audit` command verifies written Parquet coverage, metadata and
cached repeat executions. [Observed acceptance](coverage-verification.md)
covers one month and both clock-change days. The subsequent
[2025 annual acceptance](year-2025-verification.md) covers all 12 months and
the combined local snapshot. Cloud delivery remains a separate milestone.

## 4. Contracts

### Raw object

```text
gs://<bucket>/raw/smard/de_load/dt=YYYY-MM-DD/<run_id>.csv
gs://<bucket>/raw/smard/de_load/dt=YYYY-MM-DD/<run_id>.manifest.json
```

The manifest records `source`, `metric`, `area`, `interval`, `window_start`, `window_end`, `sha256`, `row_count`, and `retrieved_at`. A later run writes a new object. It does not overwrite a committed object.

### Observation table

| Column | Type | Meaning |
|--------|------|---------|
| `interval_start` | TIMESTAMP | Start of the interval, UTC |
| `interval_end` | TIMESTAMP | End of the interval, UTC |
| `area` | STRING | `DE` for v1 |
| `metric` | STRING | `actual_load_mwh` for v1 |
| `value` | FLOAT64 | Source value, original unit |
| `unit` | STRING | `MWh` (quarter-hour energy, not average power) |
| `source` | STRING | `smard` or `sample` |
| `release_id` | STRING | Id of the publish that wrote the row |
| `ingested_at` | TIMESTAMP | Write time |

The local Parquet contains the first seven columns above. The cloud publisher
will add `release_id` and `ingested_at`; a local run ID identifies processing,
not a cloud release.

v1 interval is 15 minutes. The value is the original quarter-hour energy in
MWh, with no multiplication into MW. Expected row count is the UTC duration
between the requested local midnights divided by 15 minutes: 96 for a normal
day, 92 at the spring clock change and 100 at the autumn change. The local
parser requires complete source order to disambiguate repeated labels.
Later metrics must declare their own unit and interval; do not reuse the
load conversion or assume the same temporal resolution.

### Release record

`energy.load_release` has one row per attempted publish: `release_id`, window, input checksum, row count, `git_sha`, Cloud Run execution id, quality status (`passed` or `failed`), and `published_at`. A failed validation still writes this row and does not change `metric_observation`.

## 5. Behaviour

1. Resolve the window from arguments. Refuse an open-ended window.
2. Read the sample, or the live adapter when that mode is selected. Write the raw object and its manifest.
3. Validate before any publish: column set, types, `interval_start < interval_end`, no null measure, no duplicate business key, row count matches the declared interval. A DST sample is part of the fixture set.
4. On failure, write `quality_status=failed` and stop. The previous rows for that window stay as they are.
5. On success, merge the window on the business key inside one load. A second successful run of the same checksum reports the same keys and the same row count.
6. Record the execution id, checksum, and git revision on the release row.

Overlapping scheduler runs are prevented by a job concurrency limit of one.

## 6. Delivery and cost

Terraform owns the resources listed in the decisions table. GitHub Actions runs the unit tests, then `terraform plan`. Apply on `main` uses a federated identity scoped to the test project.

The sample is small enough to run in CI without a cloud call. The scheduled cloud run uses that same week, not a growing backfill. Cloud Run scales to zero between executions. The release row records bytes billed for the load.

Minimum runtime identity: read the sample or the source secret, write the raw prefix, and edit the two BigQuery tables. It cannot delete the bucket and it cannot read other datasets.

## 7. Acceptance

1. Fixtures cover a normal week, a duplicate key, a missing interval, a null value, and a local-time change. The bad fixtures fail validation and leave the published table unchanged.
2. Deploy the job from GitHub Actions with Terraform and Workload Identity Federation. Record the execution id of one scheduled run in the test project.
3. Run the same window twice. Keys, row count, and a reference query match. Both runs have release rows. Record the execution ids, the checksum, and the observed cost.

## 8. Handoff

G02 and G04 may read `energy.metric_observation` through a view and join `energy.load_release`. They must also ship a fixture with this schema so they can be tested without this job deployed.

A second metric is a new `metric` value and a new raw prefix. It is not a new pipeline and not a new table.
