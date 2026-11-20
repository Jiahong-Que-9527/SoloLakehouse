"""Independently written expected responses for the committed fixtures.

These constants are the test oracle required by the D01 development
sequence. They were written from the fixture files and the v1 contract,
not from the parser implementation.
"""

EXPECTED_PASSED = {
    "schema_version": 1,
    "report_id": "eddf-load-20260608-audit-01",
    "snapshot_date": "2026-06-08",
    "year": 2026,
    "audited_at": "2026-06-09T06:00:00Z",
    "expected_slots": 96,
    "observed_slots": 96,
    "coverage_result": "passed",
}

EXPECTED_FAILED = {
    "schema_version": 1,
    "report_id": "eddf-load-20260609-audit-01",
    "snapshot_date": "2026-06-09",
    "year": 2026,
    "audited_at": "2026-06-10T07:30:00Z",
    "expected_slots": 96,
    "observed_slots": 95,
    "coverage_result": "failed",
}
