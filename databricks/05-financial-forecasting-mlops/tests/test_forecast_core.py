import json
from datetime import date
from pathlib import Path

import pytest

from forecast_core import Example, Observation, build_examples, evaluation_folds, qualifies

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_observation_lags_preserve_equal_values_and_skip_nonpublication_days():
    points = [
        Observation(date(2025, 4, day), rate)
        for day, rate in [(1, 1.01), (2, 1.02), (3, 1.03), (4, 1.06), (7, 1.06), (8, 1.08)]
    ]
    monday, tuesday = build_examples(reversed(points))
    assert monday.features == (1.06, 1.01)
    assert monday.source_dates == (date(2025, 4, 7), date(2025, 4, 1))
    assert monday.label_date == tuesday.as_of
    assert monday.label == tuesday.features[0] == 1.08
    assert tuesday.label is None


def test_future_sources_and_duplicate_observation_keys_are_rejected():
    cutoff = date(2025, 4, 7)
    with pytest.raises(ValueError, match="Feature source dates"):
        Example(cutoff, (date(2025, 4, 8), date(2025, 4, 1)), (1.2, 1.0), None, None)
    with pytest.raises(ValueError, match="Duplicate observation dates"):
        build_examples([Observation(cutoff, 1.0), Observation(cutoff, 1.0)])


def test_each_fold_respects_the_label_availability_cutoff():
    raw = json.loads((FIXTURES / "ecb_2025q2.json").read_text())
    observations = [
        Observation(date.fromisoformat(day), float(rate)) for day, rate in raw["observations"]
    ]
    folds = list(evaluation_folds(build_examples(observations)))
    assert len(observations) == 62
    assert [len(held_out) for _, _, held_out in folds] == [8, 10, 15]
    for cutoff, training, held_out in folds:
        assert max(row.as_of for row in training) < cutoff == held_out[0].as_of
        assert max(row.label_date for row in training) <= cutoff < held_out[0].label_date
    assert folds[1][2][-1].as_of < folds[2][0]


def test_promotion_gate_allows_ties_and_rejects_worse_or_nonfinite_scores():
    assert qualifies(0.01, 0.01)
    assert qualifies(0.009, 0.01)
    assert not qualifies(0.011, 0.01)
    assert not qualifies(float("nan"), 0.01)
    assert not qualifies(0.01, float("inf"))
