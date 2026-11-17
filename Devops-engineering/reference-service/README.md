# Energy Data Quality Service

<!-- [房玄龄·2026-11-17] Make the DevOps project self-contained. -->

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [D01](../01-reproducible-development/README.md)

Provide a read-only answer to a practical question. Which checks did the configured synthetic energy snapshot pass, and when was it audited?

## Data flow

1. D01 defines a self-contained `report.json` contract and keeps versioned synthetic audit fixtures under `reference-service/fixtures/`.
2. The service reads one configured report from a read-only path, validates the schema version and fields, and normalizes its summary.
3. The API returns the summary with the audit artifact's identity and timestamp. Later phases reuse these inputs for smoke tests and failure drills.

## Proposed contract

- `GET /v1/quality/latest` returns a summary of the **configured audit**, including year, audit timestamp, check result, expected and observed coverage where available, and a stable report identity. “Latest” means the audit chosen by the operator. The first release does not search directories for a newer run.
- A well-formed report with a failed quality result returns a valid response containing that result. A missing, unreadable or invalid artifact returns a structured availability error without disclosing filesystem details.
- Liveness reports whether the application can respond. Readiness indicates whether it can interpret the configured report. A valid report that records a failed data audit remains readable and is visible to callers.
- Every response contract change requires an explicit compatibility decision. D01 will specify the schema version, report identity, audit timestamp, pass or fail result, and required coverage fields. Tests will exercise unsupported versions.

The first integration run will read a checked-in sample report representing a complete synthetic coverage window and compare the response with its known counts and report identity. A second valid fixture will represent a failed audit with incomplete coverage. Runtime output and logs should carry provenance without dumping report content.

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Synthetic energy audit input for D01–D07

The project owns a small set of synthetic electricity-meter coverage reports. A data platform operator uses the API to decide whether a downstream daily aggregate can use a snapshot. All inputs can be authored and verified offline.

Use one meter and a UTC day with 96 quarter-hour slots. The complete fixture contains an audit summary for 96 expected and 96 observed distinct slots. The partial fixture represents a different snapshot with one missing slot and 95 observed. Keep an independently written expected response for each fixture. The API reads the supplied audit result. The fixture models an upstream producer and requires no live metering system.

For v1 require a schema version, stable report ID, snapshot date, year, UTC audit timestamp, expected and observed distinct-slot counts, and a coverage result. Counts are nonnegative integers and observed coverage cannot exceed expected coverage. For these fixtures coverage passes when all 96 expected slots are present. Preserve report ID and timestamp when serving a report. The selected path identifies the configured audit. Runtime releases refer to its checksum.

A complete and a partial but well-formed report both return a usable quality response. An unsupported schema or malformed file produces an availability error. Use the same examples for contract tests, container smoke tests, release verification and incident exercises.
