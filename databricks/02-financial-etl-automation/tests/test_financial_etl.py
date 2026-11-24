from datetime import date
from pathlib import Path

import pytest
from financial_etl import Request, outside_window_digest, prepare, validate_quality

from ecb_lakehouse.transforms import normalize_silver

D02 = Path(__file__).resolve().parents[1]
D01_FIXTURES = D02.parent / "01-ecb-delta-lakehouse" / "fixtures"
REV = "1" * 40


def batch(variant, start="2025-01-01", end="2025-03-31"):
    request = Request.parse(start, end, "q1", variant, REV)
    return prepare(request, D01_FIXTURES, D02 / "fixtures")


def test_input_identity_and_backfill_are_bounded():
    faulty = batch("faulty", "2025-02-05", "2025-02-05")
    corrected = batch("corrected", "2025-02-05", "2025-02-05")
    assert faulty.request.batch == corrected.request.batch
    assert faulty.release_id != corrected.release_id
    assert batch("corrected", "2025-02-05", "2025-02-05").release_id == corrected.release_id
    assert [row.observation_date for row in corrected.rows["fx"]] == ["2025-02-05"]
    assert corrected.rate_context[0].observation_date == date(2024, 12, 18)
    assert all(row.observation_date == "2025-02-05" for row in corrected.rows["rate"])


def test_initial_fixture_and_conflicting_repair_pass_through_quality():
    report = {"outside_before": "same", "outside_after": "same"}
    seed = batch("initial")
    silver = {
        "fx": normalize_silver(seed.rows["fx"], "daily").rows,
        "rate": normalize_silver(seed.rows["rate"], "irregular").rows,
    }
    assert len(silver["fx"]) == 10
    validate_quality(seed, silver, report)
    faulty = batch("faulty", "2025-02-05", "2025-02-05")
    with pytest.raises(ValueError, match="conflicting_duplicate_in_batch"):
        validate_quality(faulty, silver, report)
    corrected = batch("corrected", "2025-02-05", "2025-02-05")
    (rev_row,) = normalize_silver(corrected.rows["fx"], "daily").rows
    revised = silver | {
        "fx": tuple(
            rev_row if row.observation_date == rev_row.observation_date else row
            for row in silver["fx"]
        ),
    }
    validate_quality(corrected, revised, report)
    assert outside_window_digest(corrected.request, revised) == outside_window_digest(
        corrected.request, silver
    )
    with pytest.raises(ValueError, match="outside"):
        validate_quality(corrected, revised, report | {"outside_after": "different"})


@pytest.mark.parametrize("batch_id", ["a' OR 1=1", "", "two words"])
def test_batch_identity_rejects_invalid_identifiers(batch_id):
    with pytest.raises(ValueError, match="source_batch_id"):
        Request.parse("2025-01-01", "2025-03-31", batch_id, "initial", REV)
