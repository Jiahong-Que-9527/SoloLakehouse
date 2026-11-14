# ADR-001: Local execution for historical data acquisition

**Status:** Proposed. Amended by [ADR-003](ADR-003-local-bronze-silver-published-gold.md).

## Context

The first subproject downloads two years of OpenSky state vectors for `EDDF`.
This is a one-time historical backfill. Throughput is limited by OpenSky Trino
queries, not by local compute. Unattended cloud authentication against OpenSky
is unverified.

## Decision

Run historical extraction locally. Keep the Bronze dataset on the local disk
and back it up to a second physical disk. Bronze is not uploaded to cloud
storage. Cloud storage receives only published Gold releases (ADR-003).

## Rationale

- The workload is source-limited, so cloud compute does not speed it up.
- It is a one-time backfill with no requirement for always-on infrastructure.
- Local execution has lower operational complexity. It avoids Cloud Run,
  Artifact Registry, Secret Manager and Cloud Scheduler for this task.
- The 2026-10-15 pilot day scales to about 52 GB of Parquet. That still fits a
  single machine. A local copy plus a backup disk is enough for the source of
  record.

## Consequences

- Subproject 01 gets CI (tests and lint) but no cloud deployment pipeline.
- Local backup and restore need an explicit procedure.
- Later subprojects that need Bronze or Silver run on this machine. Cloud
  subprojects consume Gold releases only.

## Revisit when

Continuous, unattended ingestion becomes a requirement. Then migrate
acquisition to a Cloud Run Job and re-check OpenSky authentication from the
cloud.
