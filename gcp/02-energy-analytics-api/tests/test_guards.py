"""Task 1.3: request validation and query guards, checked in precedence order."""

from datetime import UTC, datetime, timedelta

import pytest

from energy_api.guards import QueryGuard, ValidationError, validate_request

GUARD = QueryGuard()


def test_valid_window_parses_to_utc():
    area, metric, start, end = validate_request(
        area="DE",
        metric="actual_load_mwh",
        from_s="2026-06-08T00:00:00Z",
        to_s="2026-06-09T00:00:00Z",
        guard=GUARD,
    )
    assert area == "DE"
    assert metric == "actual_load_mwh"
    assert start == datetime(2026, 6, 8, tzinfo=UTC)
    assert end == datetime(2026, 6, 9, tzinfo=UTC)


def test_non_zero_offset_is_accepted_and_normalised_to_utc():
    _, _, start, end = validate_request(
        area="DE",
        metric="actual_load_mwh",
        from_s="2026-06-08T02:00:00+02:00",
        to_s="2026-06-09T02:00:00+02:00",
        guard=GUARD,
    )
    assert start == datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 6, 9, tzinfo=UTC)


@pytest.mark.parametrize("area", ["", "FR", "de"])
def test_area_must_be_de(area):
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area=area,
            metric="actual_load_mwh",
            from_s="2026-06-08T00:00:00Z",
            to_s="2026-06-09T00:00:00Z",
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_parameters"


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="DE",
            metric="actual_load_mwh",
            from_s="2026-06-08T00:00:00",
            to_s="2026-06-09T00:00:00Z",
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_parameters"


def test_garbage_timestamp_is_rejected():
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="DE",
            metric="actual_load_mwh",
            from_s="not-a-date",
            to_s="2026-06-09T00:00:00Z",
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_parameters"


def test_equal_bounds_are_an_invalid_range():
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="DE",
            metric="actual_load_mwh",
            from_s="2026-06-08T00:00:00Z",
            to_s="2026-06-08T00:00:00Z",
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_range"


def test_reversed_range_is_an_invalid_range():
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="DE",
            metric="actual_load_mwh",
            from_s="2026-06-09T00:00:00Z",
            to_s="2026-06-08T00:00:00Z",
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_range"


def test_span_over_limit_is_query_rejected():
    start = datetime(2026, 6, 8, tzinfo=UTC)
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="DE",
            metric="actual_load_mwh",
            from_s=start.isoformat(),
            to_s=(start + timedelta(days=32)).isoformat(),
            guard=GUARD,
        )
    assert excinfo.value.code == "query_rejected"


def test_span_of_exactly_31_days_passes():
    start = datetime(2026, 6, 8, tzinfo=UTC)
    area, metric, parsed_start, parsed_end = validate_request(
        area="DE",
        metric="actual_load_mwh",
        from_s=start.isoformat(),
        to_s=(start + timedelta(days=31)).isoformat(),
        guard=GUARD,
    )
    assert (area, metric) == ("DE", "actual_load_mwh")
    assert parsed_end - parsed_start == timedelta(days=31)


def test_parameter_check_precedes_span_check():
    # Guard precedence inside validate_request: parameters first, then range,
    # then span. (The span-vs-unknown-metric 400-over-404 ordering is pinned
    # at the route layer in test_api.py.)
    start = datetime(2026, 6, 8, tzinfo=UTC)
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="DE",
            metric="",
            from_s=start.isoformat(),
            to_s=(start + timedelta(days=32)).isoformat(),
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_parameters"


def test_error_carries_code_and_message():
    with pytest.raises(ValidationError) as excinfo:
        validate_request(
            area="FR",
            metric="actual_load_mwh",
            from_s="2026-06-08T00:00:00Z",
            to_s="2026-06-09T00:00:00Z",
            guard=GUARD,
        )
    assert excinfo.value.code == "invalid_parameters"
    assert excinfo.value.message
