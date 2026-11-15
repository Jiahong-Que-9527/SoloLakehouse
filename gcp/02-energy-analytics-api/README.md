# Energy Analytics API

<!-- [房玄龄·2026-11-15] Define the G02 project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G02 · Planned** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md)

Expose approved energy indicators over a read-only API and measure its behavior under a bounded test load.

## Technical scope

Cloud Run, FastAPI, BigQuery and IAM.

## Input and output

- **Input.** The metric schema and a read-only view from [G01](../01-european-energy-pipeline/README.md), or a schema-compatible view seeded in this project's test environment.
- **Output.** An authenticated endpoint that returns the metric, dates, values, unit and data release. Logs identify each request.

## Acceptance

1. Test date filtering, an empty result, an invalid date range and a call made without permission.
2. Deploy the service through CI. Verify that the runtime identity can read the approved view and is denied access to raw inputs.
3. Run a small load test. Report the request rate, latency and error rate alongside the deployment and request IDs.
