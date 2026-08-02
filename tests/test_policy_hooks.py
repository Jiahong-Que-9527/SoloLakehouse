from __future__ import annotations

import json

import pytest

from governance.contracts import contract_path, load_contract, load_contracts
from governance.policy_hooks import (
    ML_TRAIN_ACTION,
    PolicyHookError,
    build_policy_hook_catalog,
    policy_hook_from_contract,
    validate_ml_training_allowed,
    validate_policy_action,
)


def test_policy_hook_catalog_covers_all_governed_datasets() -> None:
    contracts = load_contracts()
    catalog = build_policy_hook_catalog(contracts)

    assert len(catalog.hooks) == len(contracts)
    assert catalog.enforcement_mode == "metadata_only"
    assert {hook.dataset_id for hook in catalog.hooks} == set(contracts)


def test_gold_policy_hook_exposes_ml_train_action() -> None:
    contract = load_contract(contract_path("fin.ecb_dax_features_gold"))
    hook = policy_hook_from_contract(contract)

    action_ids = {action.action_id for action in hook.actions}
    assert ML_TRAIN_ACTION in action_ids
    assert hook.ai_use_allowed is True
    assert hook.enforcement_mode == "metadata_only"


def test_bronze_policy_hook_disallows_ml_training() -> None:
    contract = load_contract(contract_path("fin.ecb_rates_bronze"))

    with pytest.raises(PolicyHookError, match="AI use is not allowed"):
        validate_ml_training_allowed(contract)


def test_validate_policy_action_rejects_unknown_consumer() -> None:
    contract = load_contract(contract_path("fin.ecb_dax_features_gold"))
    hook = policy_hook_from_contract(contract)

    with pytest.raises(PolicyHookError, match="not allowed"):
        validate_policy_action(hook, ML_TRAIN_ACTION, "external_partner")


def test_catalog_json_is_deterministic() -> None:
    first = build_policy_hook_catalog().canonical_json_bytes()
    second = build_policy_hook_catalog().canonical_json_bytes()

    assert first == second
    assert json.loads(first.decode("utf-8"))["schema_version"] == "v1"
