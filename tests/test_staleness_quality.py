from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from governance.contracts import CONTRACTS_DIRECTORY, DatasetContract, load_contract
from governance.quality import evaluate_max_staleness


def test_event_driven_contract_rejects_max_gap_days() -> None:
    contract = load_contract(
        CONTRACTS_DIRECTORY / "fin.ecb_german_equity_proxy_features_gold.yaml"
    )
    payload = contract.model_dump(mode="json")
    payload["quality_rules"]["max_gap_days"] = 30

    with pytest.raises(ValueError, match="max_gap_days is invalid"):
        DatasetContract.model_validate(payload)


def test_max_staleness_requires_date_column() -> None:
    contract = load_contract(CONTRACTS_DIRECTORY / "fin.ecb_rates_bronze.yaml")
    payload = contract.model_dump(mode="json")
    payload["quality_rules"]["date_column"] = None
    payload["quality_rules"]["max_gap_days"] = None
    payload["quality_rules"]["forbid_future_dates"] = False
    payload["quality_rules"]["max_staleness_days"] = 3

    with pytest.raises(ValueError, match="max_staleness_days requires date_column"):
        DatasetContract.model_validate(payload)


def test_evaluate_max_staleness_warns_when_stale() -> None:
    contract = load_contract(CONTRACTS_DIRECTORY / "fin.ecb_rates_bronze.yaml")
    dataframe = pd.DataFrame(
        {
            "observation_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
            "rate_pct": [4.0, 4.1],
            "rate_type": ["MRO", "MRO"],
            "_ingestion_timestamp": [dt.datetime.now(dt.UTC)] * 2,
            "_source": ["ECB_SDW"] * 2,
        }
    )

    passed, description, metadata = evaluate_max_staleness(
        dataframe,
        contract,
        as_of=dt.date(2024, 1, 10),
    )

    assert passed is False
    assert metadata["age_days"] == 8
    assert "8 day" in description


def test_evaluate_max_staleness_passes_when_fresh() -> None:
    contract = load_contract(CONTRACTS_DIRECTORY / "fin.ecb_rates_bronze.yaml")
    dataframe = pd.DataFrame(
        {
            "observation_date": [dt.date(2024, 1, 8), dt.date(2024, 1, 9)],
            "rate_pct": [4.0, 4.1],
            "rate_type": ["DFR", "DFR"],
            "_ingestion_timestamp": [dt.datetime.now(dt.UTC)] * 2,
            "_source": ["ECB_SDW"] * 2,
        }
    )

    passed, _, metadata = evaluate_max_staleness(
        dataframe,
        contract,
        as_of=dt.date(2024, 1, 10),
    )

    assert passed is True
    assert metadata["age_days"] == 1


def test_event_driven_gold_has_no_staleness_rule() -> None:
    contract = load_contract(
        CONTRACTS_DIRECTORY / "fin.ecb_german_equity_proxy_features_gold.yaml"
    )
    assert contract.quality_rules.update_pattern == "event_driven"
    assert contract.quality_rules.max_gap_days is None
    assert contract.quality_rules.max_staleness_days is None
