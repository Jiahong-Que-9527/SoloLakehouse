from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from governance.contracts import (
    CONTRACTS_DIRECTORY,
    DatasetContract,
    governed_pipeline_asset_keys,
    load_contract,
    load_contracts,
)
from governance.quality import validate_dataset_quality


def test_contract_registry_loads_all_governed_financial_datasets() -> None:
    contracts = load_contracts()

    assert set(contracts) == {
        "fin.ecb_rates_bronze",
        "fin.ecb_rates_silver",
        "fin.german_equity_proxy_daily_bronze",
        "fin.german_equity_proxy_daily_silver",
        "fin.ecb_german_equity_proxy_features_gold",
        "fin.dax_daily_bronze",
        "fin.dax_daily_silver",
        "fin.ecb_dax_features_gold",
    }
    assert (
        contracts["fin.ecb_german_equity_proxy_features_gold"].quality_class == "demo_critical"
    )
    assert contracts["fin.dax_daily_bronze"].deprecated is True
    assert (
        contracts["fin.dax_daily_bronze"].superseded_by
        == "fin.german_equity_proxy_daily_bronze"
    )


def test_governed_pipeline_asset_keys_cover_all_contracts() -> None:
    contracts = load_contracts()

    assert set(governed_pipeline_asset_keys(contracts)) == {
        "ecb_bronze",
        "ecb_silver",
        "german_equity_proxy_bronze",
        "german_equity_proxy_silver",
        "ecb_german_equity_proxy_features",
    }


def test_contract_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    contract = (CONTRACTS_DIRECTORY / "fin.ecb_rates_bronze.yaml").read_text(encoding="utf-8")
    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text(f"{contract}\nunapproved_field: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid contract"):
        load_contract(invalid_path)


def test_ai_governance_metadata_distinguishes_training_dataset() -> None:
    contracts = load_contracts()

    gold = contracts["fin.ecb_german_equity_proxy_features_gold"].ai_governance
    bronze = contracts["fin.ecb_rates_bronze"].ai_governance

    assert gold.ai_use_allowed is True
    assert gold.model_lineage_required is True
    assert gold.human_oversight_required is True
    assert bronze.ai_use_allowed is False
    assert bronze.risk_tier == "not_applicable"


def test_ai_governance_rejects_inconsistent_ai_boundary() -> None:
    contract = load_contract(
        CONTRACTS_DIRECTORY / "fin.ecb_german_equity_proxy_features_gold.yaml"
    )
    payload = contract.model_dump(mode="json")
    payload["ai_governance"]["model_lineage_required"] = False

    with pytest.raises(ValueError, match="require model lineage"):
        DatasetContract.model_validate(payload)


def test_runtime_quality_rejects_contract_violation() -> None:
    contract = load_contract(CONTRACTS_DIRECTORY / "fin.ecb_rates_bronze.yaml")
    dataframe = pd.DataFrame(
        {
            "observation_date": ["2024-01-01"],
            "rate_pct": [None],
            "rate_type": ["MRO"],
            "_ingestion_timestamp": ["2024-01-01T00:00:00Z"],
            "_source": ["ECB"],
        }
    )

    with pytest.raises(ValueError, match="null values"):
        validate_dataset_quality(dataframe, contract)


def test_runtime_quality_rejects_too_few_gold_rows() -> None:
    contract = load_contract(
        CONTRACTS_DIRECTORY / "fin.ecb_german_equity_proxy_features_gold.yaml"
    )
    dataframe = pd.DataFrame(
        {
            "event_date": ["2024-01-01"],
            "rate_change_bps": [25.0],
            "rate_level_pct": [4.0],
            "is_rate_hike": [True],
            "is_rate_cut": [False],
            "dax_pre_close": [17000.0],
            "dax_return_1d": [1.0],
            "dax_return_5d": [2.0],
            "dax_volatility_pre_5d": [0.5],
        }
    )

    with pytest.raises(ValueError, match="below minimum 10"):
        validate_dataset_quality(dataframe, contract)
