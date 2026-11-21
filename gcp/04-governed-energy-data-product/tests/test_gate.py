"""The gate: key-set completeness, uniqueness, range, freshness.

Sequence step 2 pins the decisive case: a duplicate masking a missing
interval fails even though the total row count matches the grid.
"""

from datetime import timedelta

from conftest import load_contracts
from energy_product.fixture import (
    EVALUATION_TIME,
    candidate_metadata,
    candidate_rows,
    expected_grid,
    stale_metadata,
    with_duplicate_masking_missing,
    with_missing_column,
    with_null_value,
)
from energy_product.gate import run_gate

CONTRACT, _, _ = load_contracts()
GRID = expected_grid()
ROWS = candidate_rows(GRID)
META = candidate_metadata()


def test_good_candidate_passes_every_check():
    result = run_gate(
        CONTRACT,
        ROWS,
        GRID,
        evaluation_time=META["evaluation_time"],
        ingested_at=META["ingested_at"],
    )
    assert result.passed
    assert all(check.passed for check in result.checks)
    assert [check.name for check in result.checks] == [
        "schema",
        "grain_uniqueness",
        "completeness",
        "value_range",
        "freshness",
    ]


def test_duplicate_masking_a_missing_interval_fails_despite_the_row_count():
    damaged = with_duplicate_masking_missing(ROWS)
    assert len(damaged) == len(ROWS)  # counts match...
    result = run_gate(
        CONTRACT,
        damaged,
        GRID,
        evaluation_time=META["evaluation_time"],
        ingested_at=META["ingested_at"],
    )
    assert not result.passed
    by_name = {check.name: check for check in result.checks}
    assert not by_name["grain_uniqueness"].passed
    assert not by_name["completeness"].passed
    # Both offending sets are reported: the duplicated key and the gap.
    duplicated_key = by_name["grain_uniqueness"].offending
    assert len(duplicated_key) == 1
    missing_key = by_name["completeness"].offending
    assert len(missing_key) == 1
    assert duplicated_key != missing_key


def test_null_measure_fails_the_value_check():
    result = run_gate(
        CONTRACT,
        with_null_value(ROWS),
        GRID,
        evaluation_time=META["evaluation_time"],
        ingested_at=META["ingested_at"],
    )
    by_name = {check.name: check for check in result.checks}
    assert not by_name["value_range"].passed
    assert by_name["value_range"].offending


def test_stale_ingestion_fails_freshness():
    stale = stale_metadata()
    result = run_gate(
        CONTRACT,
        ROWS,
        GRID,
        evaluation_time=stale["evaluation_time"],
        ingested_at=stale["ingested_at"],
    )
    by_name = {check.name: check for check in result.checks}
    assert not by_name["freshness"].passed
    # 72 hours old renders as 3 days against the 2-day allowance.
    assert "3 days" in by_name["freshness"].detail


def test_freshness_boundary_is_inclusive_at_exactly_48_hours():
    boundary = EVALUATION_TIME - timedelta(hours=48)
    result = run_gate(CONTRACT, ROWS, GRID, evaluation_time=EVALUATION_TIME, ingested_at=boundary)
    assert result.passed


def test_missing_required_column_fails_the_schema_check():
    result = run_gate(
        CONTRACT,
        with_missing_column(ROWS),
        GRID,
        evaluation_time=META["evaluation_time"],
        ingested_at=META["ingested_at"],
    )
    by_name = {check.name: check for check in result.checks}
    assert not by_name["schema"].passed
    assert ("unit",) in by_name["schema"].offending


def test_an_unexpected_extra_interval_fails_completeness():
    extra = dict(ROWS[0])
    extra["interval_start"] = GRID[-1][2] + timedelta(minutes=15)
    extra["interval_end"] = extra["interval_start"] + timedelta(minutes=15)
    result = run_gate(
        CONTRACT,
        ROWS + [extra],
        GRID,
        evaluation_time=META["evaluation_time"],
        ingested_at=META["ingested_at"],
    )
    by_name = {check.name: check for check in result.checks}
    assert not by_name["completeness"].passed
    assert len(by_name["completeness"].offending) == 1
