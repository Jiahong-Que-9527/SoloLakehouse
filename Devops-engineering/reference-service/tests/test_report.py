import json
from pathlib import Path

import pytest

from energy_quality.report import ReportError, parse_report
from expected import EXPECTED_FAILED, EXPECTED_PASSED

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_passed_fixture_parses_to_expected_summary():
    assert parse_report(load("report-passed.json")) == EXPECTED_PASSED


def test_failed_fixture_parses_to_expected_summary():
    assert parse_report(load("report-failed.json")) == EXPECTED_FAILED


def test_missing_fields_lists_violations():
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps({"schema_version": 1}).encode())
    assert excinfo.value.code == "missing_field"
    assert "observed_slots" in excinfo.value.message


def test_unsupported_schema_version():
    document = dict(EXPECTED_PASSED, schema_version=2)
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps(document).encode())
    assert excinfo.value.code == "unsupported_schema_version"


def test_boolean_is_not_an_integer_count():
    document = dict(EXPECTED_PASSED, observed_slots=True)
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps(document).encode())
    assert excinfo.value.code == "invalid_field"


def test_negative_count_rejected():
    document = dict(EXPECTED_PASSED, observed_slots=-1)
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps(document).encode())
    assert excinfo.value.code == "invalid_field"


def test_observed_exceeding_expected_rejected():
    document = dict(EXPECTED_PASSED, observed_slots=97)
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps(document).encode())
    assert excinfo.value.code == "deliberate_failure_for_d03_negative_test"


def test_inconsistent_coverage_rejected():
    document = dict(EXPECTED_PASSED, coverage_result="failed")
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps(document).encode())
    assert excinfo.value.code == "inconsistent_coverage"


def test_malformed_json_rejected():
    with pytest.raises(ReportError) as excinfo:
        parse_report(b"{not json")
    assert excinfo.value.code == "malformed"


def test_naive_timestamp_rejected():
    document = dict(EXPECTED_PASSED, audited_at="2026-06-09T06:00:00")
    with pytest.raises(ReportError) as excinfo:
        parse_report(json.dumps(document).encode())
    assert excinfo.value.code == "invalid_field"


def test_offset_timestamp_normalized_to_utc():
    document = dict(EXPECTED_PASSED, audited_at="2026-06-09T08:00:00+02:00")
    summary = parse_report(json.dumps(document).encode())
    assert summary["audited_at"] == "2026-06-09T06:00:00Z"


def test_error_messages_omit_filesystem_details():
    with pytest.raises(ReportError) as excinfo:
        parse_report(b"{not json")
    assert "/fixtures" not in excinfo.value.message
    assert ".json" not in excinfo.value.message
