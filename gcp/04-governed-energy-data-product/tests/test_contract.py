"""Contracts are versioned YAML; thresholds are not hidden in code."""

from pathlib import Path

import pytest

from conftest import LOAD_CONTRACT, PRICES_CONTRACT, RENEWABLE_CONTRACT
from energy_product.contract import ContractError, load_contract


def test_energy_load_contract_loads_with_the_design_values():
    contract = load_contract(LOAD_CONTRACT)
    assert contract.data_product == "energy-load"
    assert contract.slug == "energy_load"
    assert contract.version_table == "energy_load_v"
    assert contract.current_view == "energy_load_current"
    assert contract.version == "1.0.0"
    assert contract.grain == ("area", "metric", "interval_start")
    assert contract.required_columns == (
        "interval_start",
        "interval_end",
        "area",
        "metric",
        "value",
        "unit",
        "release_id",
    )
    assert contract.gates.completeness_min == 1.0
    assert contract.gates.duplicate_business_keys_max == 0
    assert contract.gates.value_min == 0
    assert contract.gates.freshness_hours_max == 48
    assert contract.approval_required is True


def test_the_two_specified_products_have_written_contracts():
    prices = load_contract(PRICES_CONTRACT)
    renewable = load_contract(RENEWABLE_CONTRACT)
    assert prices.data_product == "energy-prices"
    assert renewable.data_product == "renewable-generation"
    # Same view shape so a consumer reads every product the same way.
    assert prices.required_columns == renewable.required_columns
    assert prices.approval_required and renewable.approval_required


def test_missing_file_is_a_contract_error(tmp_path: Path):
    with pytest.raises(ContractError, match="not found"):
        load_contract(tmp_path / "nope.yaml")


def test_malformed_yaml_is_a_contract_error(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("data_product: [unclosed", encoding="utf-8")
    with pytest.raises(ContractError, match="YAML"):
        load_contract(bad)


def test_grain_must_be_a_subset_of_required_columns(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "data_product: x\nversion: 1.0.0\ncontract:\n"
        "  schema_version: 1\n  grain: [area, ghost]\n"
        "  required_columns: [area, value]\n"
        "quality_gates:\n    completeness_min: 1.0\n"
        "    duplicate_business_keys_max: 0\n    value_min: 0\n"
        "    freshness_hours_max: 48\nrelease:\n"
        "  approval_required: true\n  record_manifest: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="grain column"):
        load_contract(bad)


def test_completeness_threshold_must_be_a_fraction(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "data_product: x\nversion: 1.0.0\ncontract:\n"
        "  schema_version: 1\n  grain: [area]\n  required_columns: [area]\n"
        "quality_gates:\n    completeness_min: 1.5\n"
        "    duplicate_business_keys_max: 0\n    value_min: 0\n"
        "    freshness_hours_max: 48\nrelease:\n"
        "  approval_required: true\n  record_manifest: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="completeness_min"):
        load_contract(bad)
