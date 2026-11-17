# Governed Energy Data Product implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

**Status:** planned. [Project brief](../README.md) and [technical design](design.md).

## First delivery

Deliver one immutable energy-load release, one reader-facing view and an auditable withdrawal. A consumer must be able to identify which release supplied a row even after the current view changes.

## Implementation sequence

1. Define a fixture and contract. Pin metric actual_load_mwh, unit MWh, UTC start/end, release ID and expected interval grid. Include duplicate, missing, null and stale-ingestion variants. Put ingested_at in input metadata and define the reference clock for the 48-hour freshness check. For historical replay use a recorded evaluation time.

2. Implement the checks offline first. Compare actual keys with the expected grid as well as counts. Emit outcomes and offending keys. Test a duplicate masking a missing interval and verify it fails even though the total row count matches.

3. Provision isolated source, quarantine and publication access. Publish a good candidate under an immutable ID. Record the manifest and approval, switch the authorized view, then read it as an analyst. Verify denied raw and quarantine reads and confirm the auditor can inspect release records.

4. Submit an invalid candidate and compare the visible view and release ID before and after. Simulate failure between creating a version table and moving the view. Retry with the same candidate ID, verify checksum and reconcile the publication record before marking the release current.

5. Withdraw the current release and confirm fallback to the last passed release or an empty view. Publish corrected data under a fresh ID. Trace one resulting row through the manifest to the source revision. Record catalog lineage separately from manifest lineage and identify any unavailable cloud evidence.

## Acceptance record

A pair of successful and blocked release records, an access test with named roles and a reversible publishing demonstration. These illustrate how to keep a data product usable during a quality incident. Link the run record from the project brief after execution and identify any checks still pending.
