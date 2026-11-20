"""Parse and validate the v1 energy audit report contract.

The reader is intentionally strict: a document that does not satisfy the
v1 contract raises ReportError instead of producing a partial summary.
Error messages describe the contract violation only; they never include
filesystem paths or file content.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

SUPPORTED_SCHEMA_VERSION = 1
COVERAGE_RESULTS = ("passed", "failed")

REQUIRED_FIELDS = (
    "schema_version",
    "report_id",
    "snapshot_date",
    "year",
    "audited_at",
    "expected_slots",
    "observed_slots",
    "coverage_result",
)


class ReportError(Exception):
    """The configured report does not satisfy the v1 audit report contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ReportError(code, message)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _normalize_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None, "invalid_field", "audited_at must carry a UTC offset.")
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_report(data: bytes) -> dict[str, Any]:
    """Return the normalized v1 summary for report bytes, or raise ReportError."""
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportError("malformed", "The report is not valid JSON.") from exc
    _require(isinstance(document, dict), "malformed", "The report must be a JSON object.")

    missing = [field for field in REQUIRED_FIELDS if field not in document]
    _require(
        not missing,
        "missing_field",
        f"Missing required field(s): {', '.join(sorted(missing))}.",
    )

    _require(
        _is_int(document["schema_version"]),
        "invalid_field",
        "schema_version must be an integer.",
    )
    _require(
        document["schema_version"] == SUPPORTED_SCHEMA_VERSION,
        "unsupported_schema_version",
        f"Unsupported schema version; supported version is {SUPPORTED_SCHEMA_VERSION}.",
    )

    _require(
        isinstance(document["report_id"], str) and document["report_id"].strip() != "",
        "invalid_field",
        "report_id must be a non-empty string.",
    )

    _require(
        isinstance(document["snapshot_date"], str),
        "invalid_field",
        "snapshot_date must be an ISO date string.",
    )
    try:
        date.fromisoformat(document["snapshot_date"])
    except ValueError as exc:
        raise ReportError("invalid_field", "snapshot_date must be an ISO date string.") from exc

    _require(
        _is_int(document["year"]) and document["year"] > 0,
        "invalid_field",
        "year must be a positive integer.",
    )

    _require(
        isinstance(document["audited_at"], str),
        "invalid_field",
        "audited_at must be a UTC timestamp string.",
    )
    audited_at = _normalize_utc(document["audited_at"])

    for field in ("expected_slots", "observed_slots"):
        _require(
            _is_int(document[field]) and document[field] >= 0,
            "invalid_field",
            f"{field} must be a non-negative integer.",
        )
    expected = document["expected_slots"]
    observed = document["observed_slots"]
    _require(
        observed <= expected,
        "invalid_counts",
        "observed_slots cannot exceed expected_slots.",
    )

    _require(
        document["coverage_result"] in COVERAGE_RESULTS,
        "invalid_field",
        "coverage_result must be 'passed' or 'failed'.",
    )
    result = document["coverage_result"]
    _require(
        (result == "passed") == (observed == expected),
        "inconsistent_coverage",
        "coverage_result must be 'passed' only when observed_slots equals expected_slots.",
    )

    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "report_id": document["report_id"],
        "snapshot_date": document["snapshot_date"],
        "year": document["year"],
        "audited_at": audited_at,
        "expected_slots": expected,
        "observed_slots": observed,
        "coverage_result": result,
    }
