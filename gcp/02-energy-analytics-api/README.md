# Energy Analytics API

<!-- [房玄龄·2026-11-15] Define the G02 project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G02 · Cloud delivery implemented and accepted** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Execution plan](../../docs/superpowers/plans/2026-11-20-g02-energy-api.md) · [Verification evidence](docs/cloud-verification.md)

Expose approved energy indicators over a read-only API and measure its behavior under a bounded test load.

**Delivered 2026-11-20:** FastAPI on Cloud Run (min instances 0) over an authorized BigQuery view; caller/runtime identity split with denied-by-default access; query guards (31-day span, 15 s timeout, 1 GiB byte cap, fail closed); WIF deploy pipeline behind the `gcp-test` gate; log-based error metric and email alert; revision rollback drill and bounded load check on record.

## Technical scope

Cloud Run, FastAPI, BigQuery and IAM.

## Input and output

- **Input.** The metric schema and a read-only view from [G01](../01-european-energy-pipeline/README.md), or a schema-compatible view seeded in this project's test environment.
- **Output.** An authenticated endpoint that returns the metric, dates, values, unit and data release. Logs identify each request.

## Acceptance

1. Test date filtering, an empty result, an invalid date range and a call made without permission.
2. Deploy the service through CI. Verify that the runtime identity can read the approved view and is denied access to raw inputs.
3. Run a small load test. Report the request rate, latency and error rate alongside the deployment and request IDs.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->
