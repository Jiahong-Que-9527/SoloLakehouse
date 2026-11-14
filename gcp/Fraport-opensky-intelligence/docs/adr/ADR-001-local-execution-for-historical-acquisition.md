# ADR-001: Local execution for historical data acquisition

**Status:** Proposed

## Context

The first subproject downloads about one year of OpenSky state vectors for
`EDDF`. This is a one-time historical backfill. Throughput is limited by
OpenSky Trino queries, not by local compute. Unattended cloud authentication
against OpenSky is unverified. The downstream projects need the data in a
shared cloud location.

## Decision

Run historical extraction locally. Persist validated datasets in Google Cloud
Storage, after confirming that the OpenSky terms allow it.

## Rationale

- The workload is source-limited, so cloud compute does not speed it up.
- It is a one-time backfill with no requirement for always-on infrastructure.
- Local execution has lower operational complexity. It avoids Cloud Run,
  Artifact Registry, Secret Manager and Cloud Scheduler for this task.
- Shared cloud storage gives BigQuery, Databricks and Vertex AI one copy.

## Consequences

- Subproject 01 gets CI (tests and lint) but no cloud deployment pipeline.
- The first real GCP CI/CD pipeline moves to subproject 02.
- Local backup and restore need an explicit procedure.
- Retention and cloud storage must follow the OpenSky terms.

## Revisit when

Continuous, unattended ingestion becomes a requirement. Then migrate
acquisition to a Cloud Run Job and re-check OpenSky authentication from the
cloud.
