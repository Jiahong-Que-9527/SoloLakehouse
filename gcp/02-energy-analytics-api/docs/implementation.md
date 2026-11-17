# Energy Analytics API implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

**Status:** planned. [Project brief](../README.md) and [technical design](design.md).

## First delivery

Deliver one authenticated query against a named release of German load observations. A data consumer should be able to reproduce a response from its release ID and UTC window.

## Implementation sequence

1. Seed the release. Prepare two small releases for DE, with known UTC interval boundaries and distinct values. For a two-row example use 10 and 12 MWh. Record the expected count, minimum and maximum as 2, 10 and 12. Use half-open windows and test a query ending exactly at the second interval start.

2. Freeze the HTTP contract. Resolve the latest passed release once per request and include its ID in the result. Test an empty window, unsupported metric, reversed range and 32-day request against a fake query layer before building the cloud path. Preserve MWh from G01.

3. Build the read path. Seed an isolated BigQuery dataset and expose an authorized view. Give the runtime identity query-job permission and access to the view. Run a parameterized query with the configured byte cap and timeout. Confirm a denied raw-table read using the same identity that successfully read the view.

4. Deploy one Cloud Run revision. Keep the caller, deployer and runtime identities distinct. Compare an authenticated request with a missing-invoker request and correlate the successful request ID with its query job. Check the app's validation errors separately from platform-level denials.

5. Exercise a second revision and return traffic to the known-good one if the contract smoke test fails. Run a short, fixed-rate load check and record its duration, request count, p50, p95, errors and bytes billed. Record the scale-to-zero setting and inventory any retained billable resources.

## Acceptance record

A request-to-result trace with the revision, principal, release, job ID and cost evidence. This supports an interview discussion of access boundaries and controlling analytical query cost. Link the run record from the project brief after execution and identify any checks still pending.
