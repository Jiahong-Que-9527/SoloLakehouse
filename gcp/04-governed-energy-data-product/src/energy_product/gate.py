"""Offline quality gate (design section 5, step 2; sequence step 2).

The gate compares the actual business keys against the expected interval
grid, not only counts: a duplicate that masks a missing interval leaves
the row count intact and must still fail. It never mutates anything; the
publisher decides what a failed or passed result does.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from energy_product.contract import DataProductContract


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    offending: tuple[tuple, ...] = ()


@dataclass(frozen=True)
class GateResult:
    passed: bool
    checks: tuple[CheckResult, ...]

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if not check.passed)


def _key(row: dict, grain: tuple[str, ...]) -> tuple:
    return tuple(row.get(column) for column in grain)


def run_gate(
    contract: DataProductContract,
    rows: list[dict],
    expected_grid: list[tuple],
    *,
    evaluation_time: datetime,
    ingested_at: datetime,
) -> GateResult:
    """Run every check; ``expected_grid`` holds the exact business keys the
    window must contain, and ``evaluation_time`` is the recorded clock the
    freshness check compares ``ingested_at`` against."""
    grain = contract.grain
    checks: list[CheckResult] = []

    # Schema: every required column present (and not null) in every row.
    missing_columns = {
        column for row in rows for column in contract.required_columns if column not in row
    }
    nulls = {
        (column, _key(row, grain))
        for row in rows
        for column in contract.required_columns
        if column in row and row[column] is None
    }
    checks.append(
        CheckResult(
            "schema",
            not missing_columns and not nulls,
            "required columns present and non-null"
            if not missing_columns and not nulls
            else f"missing columns {sorted(missing_columns)}, nulls in {len(nulls)} cells",
            offending=tuple((column,) for column in sorted(missing_columns)),
        )
    )

    # Grain uniqueness: at most duplicate_business_keys_max duplicated keys.
    counts: dict[tuple, int] = {}
    for row in rows:
        counts[_key(row, grain)] = counts.get(_key(row, grain), 0) + 1
    duplicated = tuple(key for key, count in counts.items() if count > 1)
    checks.append(
        CheckResult(
            "grain_uniqueness",
            len(duplicated) <= contract.gates.duplicate_business_keys_max,
            f"{len(duplicated)} duplicated business keys (max "
            f"{contract.gates.duplicate_business_keys_max})",
            offending=duplicated,
        )
    )

    # Completeness against the expected grid, in both directions.
    actual = set(counts)
    expected = set(expected_grid)
    missing = tuple(sorted(expected - actual))
    unexpected = tuple(sorted(actual - expected))
    grid_failed = not missing and not unexpected
    checks.append(
        CheckResult(
            "completeness",
            grid_failed,
            f"{len(actual)}/{len(expected)} expected keys present"
            + (
                f"; missing {len(missing)}, unexpected {len(unexpected)}" if not grid_failed else ""
            ),
            offending=missing + unexpected,
        )
    )

    # Value range: no null measures, every measure at or above value_min.
    bad_values = tuple(
        _key(row, grain)
        for row in rows
        if row.get("value") is None or float(row["value"]) < contract.gates.value_min
    )
    checks.append(
        CheckResult(
            "value_range",
            not bad_values,
            f"{len(bad_values)} rows below {contract.gates.value_min} or null",
            offending=bad_values,
        )
    )

    # Freshness: the input release must be newer than the contract allows.
    age = evaluation_time - ingested_at
    limit = timedelta(hours=contract.gates.freshness_hours_max)
    checks.append(
        CheckResult(
            "freshness",
            age <= limit,
            f"input ingested {age} before evaluation (max {limit})",
        )
    )

    return GateResult(all(check.passed for check in checks), tuple(checks))
