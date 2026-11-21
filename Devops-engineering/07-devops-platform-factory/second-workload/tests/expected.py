"""Expected responses for the committed freshness fixtures.

Test oracle written from the fixture files and the freshness contract,
not from the implementation. FRESHNESS_NOW is pinned to 2026-06-10T00:00:00Z
in the tests.
"""

NOW = "2026-06-10T00:00:00Z"

EXPECTED_FRESH = {
    "schema_version": 1,
    "snapshot_id": "meter-snapshot-20260608",
    "snapshot_generated_at": "2026-06-09T23:00:00Z",
    "age_hours": 1.0,
    "max_age_hours": 24,
    "verdict": "fresh",
}

EXPECTED_STALE = {
    "schema_version": 1,
    "snapshot_id": "meter-snapshot-20260601",
    "snapshot_generated_at": "2026-06-08T18:00:00Z",
    "age_hours": 30.0,
    "max_age_hours": 24,
    "verdict": "stale",
}
