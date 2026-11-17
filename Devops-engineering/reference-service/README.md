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
