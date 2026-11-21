"""Shared builders for the G04 contract tests."""

from pathlib import Path

from energy_product.contract import load_contract
from energy_product.fixture import (
    EVALUATION_TIME,
    GOOD_CANDIDATE,
    GOOD_INPUT_RELEASE,
    candidate_metadata,
    candidate_rows,
    expected_grid,
)

PROJECT = Path(__file__).resolve().parents[1]
LOAD_CONTRACT = PROJECT / "contracts" / "energy-load.yaml"
PRICES_CONTRACT = PROJECT / "contracts" / "energy-prices.yaml"
RENEWABLE_CONTRACT = PROJECT / "contracts" / "renewable-generation.yaml"


def load_contracts():
    return (
        load_contract(LOAD_CONTRACT),
        load_contract(PRICES_CONTRACT),
        load_contract(RENEWABLE_CONTRACT),
    )


__all__ = [
    "EVALUATION_TIME",
    "GOOD_CANDIDATE",
    "GOOD_INPUT_RELEASE",
    "PRICES_CONTRACT",
    "RENEWABLE_CONTRACT",
    "candidate_metadata",
    "candidate_rows",
    "expected_grid",
    "load_contracts",
]
