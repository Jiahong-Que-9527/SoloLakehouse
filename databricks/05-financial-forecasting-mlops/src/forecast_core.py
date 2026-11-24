"""Point-in-time ECB feature contract and frozen evaluation windows."""

from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite

SERIES = "EXR.D.USD.EUR.SP00.A"
FEATURES = ("lag_1", "lag_5")
FEATURE_VERSION = "observed-lags-1-and-5-v1"
FOLDS = ((24, 32), (32, 42), (42, None))
SEED = 42
CANDIDATE_PARAMS = {
    "n_estimators": 20,
    "learning_rate": 0.20,
    "max_depth": 2,
    "random_state": SEED,
}


@dataclass(frozen=True)
class Observation:
    day: date
    value: float


@dataclass(frozen=True)
class Example:
    as_of: date
    source_dates: tuple[date, date]
    features: tuple[float, float]
    label_date: date | None
    label: float | None

    def __post_init__(self):
        latest, oldest = self.source_dates
        if not oldest < latest <= self.as_of:
            raise ValueError("Feature source dates must precede or equal the forecast cutoff")
        if (self.label_date is None) != (self.label is None):
            raise ValueError("Label date and value must be available together")
        if self.label_date is not None and self.label_date <= self.as_of:
            raise ValueError("Label must follow the forecast cutoff")


def build_examples(observations):
    ordered = sorted(observations, key=lambda row: row.day)
    dates = {point.day for point in ordered}
    if len(dates) != len(ordered):
        raise ValueError("Duplicate observation dates")
    if any(not isfinite(point.value) or point.value <= 0 for point in ordered):
        raise ValueError("FX rates must be finite and positive")
    examples = []
    for index in range(4, len(ordered)):
        latest, oldest = ordered[index], ordered[index - 4]
        following = ordered[index + 1] if index + 1 < len(ordered) else None
        examples.append(
            Example(
                latest.day,
                (latest.day, oldest.day),
                (latest.value, oldest.value),
                following.day if following else None,
                following.value if following else None,
            )
        )
    return examples


def evaluation_folds(examples):
    labeled = [example for example in examples if example.label_date is not None]
    if len(labeled) < 52:
        raise ValueError("D05 requires at least 52 labeled examples for the frozen folds")
    for start, stop in FOLDS:
        held_out = labeled[start:stop]
        cutoff = held_out[0].as_of
        training = [row for row in labeled[:start] if row.label_date <= cutoff]
        yield cutoff, training, held_out


def qualifies(candidate_mae, naive_mae):
    return isfinite(candidate_mae) and isfinite(naive_mae) and 0 <= candidate_mae <= naive_mae


def synthetic_observations(high, *, reject=False):
    """Use a predictable alternating weekday fixture or an isolated gate-failure regime."""
    start = date(2025, 1, 6)
    days = [start + timedelta(days=i) for i in range(80) if i % 7 < 5]
    return [
        Observation(day, high if i % 2 and (not reject or i < 46) else 1.0)
        for i, day in enumerate(days[:57])
    ]
