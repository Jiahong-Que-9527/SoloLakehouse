# Energy Data API

<!-- [房玄龄·2026-11-15] Define the G02 project brief. -->

**Milestone:** G02 in the [Google Cloud roadmap](../README.md). Planned.

Expose a German electricity-load indicator for a bounded date range. Use
FastAPI on Cloud Run and query a BigQuery view with a dedicated read-only
runtime identity.

## Input and output

- Input is the versioned metric contract from the
  [European Energy Pipeline](../european-energy-pipeline/README.md).
  A small fixture represents the same contract for independent tests.
- A response identifies the metric, observation times, values, unit and data
  release. Record a request ID in the response or logs for troubleshooting.

## First delivery

1. Define a sample request and expected response. Cover valid, empty and
   invalid date ranges.
2. Validate the contract with a fixture and deploy to a test Cloud Run service.
3. Run an authenticated query against a seeded view, verify that an
   unauthorized caller is denied, and find the request in the logs.
4. Verify that the runtime identity can read the approved view and is denied
   access to the raw inputs. Record the deployment and query evidence.

For integration, point the API at the approved batch view and verify that the
response identifies the selected release.
