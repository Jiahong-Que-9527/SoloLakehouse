"""Agent-ready policy hooks derived from governed dataset contracts (v2.8 E3)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from governance.contracts import DatasetContract, load_contracts
from governance.ml_lineage import contract_content_sha256

POLICY_HOOK_SCHEMA_VERSION = "v1"
EnforcementMode = Literal["metadata_only"]
ML_TRAIN_ACTION = "ml.train"
SQL_READ_ACTION = "sql.read"
LINEAGE_EMIT_ACTION = "lineage.emit"


class PolicyHookError(ValueError):
    """A policy hook or evidence-boundary check failed."""

    def __init__(self, dataset_id: str, reason: str) -> None:
        super().__init__(f"Policy hook for {dataset_id!r} is invalid: {reason}")
        self.dataset_id = dataset_id
        self.reason = reason


class PolicyAction(BaseModel):
    """One machine-readable action an agent or tool may attempt on a dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1)
    allowed_consumer_classes: tuple[str, ...]
    requires_ml_lineage: bool = False


class AgentPolicyHook(BaseModel):
    """Structured policy surface for MCP-style consumers; metadata-only in v2.8."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = POLICY_HOOK_SCHEMA_VERSION
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dagster_asset_key: str = Field(min_length=1)
    approved_consumer_classes: tuple[str, ...]
    access_policy_hint: str = Field(min_length=1)
    ai_use_allowed: bool
    risk_tier: str = Field(min_length=1)
    intended_uses: tuple[str, ...]
    prohibited_uses: tuple[str, ...]
    human_oversight_required: bool
    model_lineage_required: bool
    enforcement_mode: EnforcementMode = "metadata_only"
    actions: tuple[PolicyAction, ...] = Field(min_length=1)

    def canonical_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json_bytes()).hexdigest()


class PolicyHookCatalog(BaseModel):
    """Canonical export of every governed dataset policy hook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = POLICY_HOOK_SCHEMA_VERSION
    enforcement_mode: EnforcementMode = "metadata_only"
    hooks: tuple[AgentPolicyHook, ...] = Field(min_length=1)

    def canonical_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json_bytes()).hexdigest()


def _actions_for_contract(contract: DatasetContract) -> tuple[PolicyAction, ...]:
    read_action = PolicyAction(
        action_id=SQL_READ_ACTION,
        allowed_consumer_classes=tuple(contract.approved_consumer_class),
    )
    emit_action = PolicyAction(
        action_id=LINEAGE_EMIT_ACTION,
        allowed_consumer_classes=tuple(contract.approved_consumer_class),
    )
    if not contract.ai_governance.ai_use_allowed:
        return (read_action, emit_action)

    train_classes = tuple(
        consumer
        for consumer in contract.approved_consumer_class
        if consumer in {"internal_ml", "internal_analytics"}
    )
    if not train_classes:
        train_classes = ("internal_ml",)
    train_action = PolicyAction(
        action_id=ML_TRAIN_ACTION,
        allowed_consumer_classes=train_classes,
        requires_ml_lineage=contract.ai_governance.model_lineage_required,
    )
    return (read_action, emit_action, train_action)


def policy_hook_from_contract(contract: DatasetContract) -> AgentPolicyHook:
    """Build one agent-ready policy hook from a validated dataset contract."""
    ai = contract.ai_governance
    return AgentPolicyHook(
        dataset_id=contract.dataset_id,
        contract_sha256=contract_content_sha256(contract),
        dagster_asset_key=contract.dagster_asset_key,
        approved_consumer_classes=tuple(contract.approved_consumer_class),
        access_policy_hint=contract.access_policy_hint,
        ai_use_allowed=ai.ai_use_allowed,
        risk_tier=ai.risk_tier,
        intended_uses=tuple(ai.intended_uses),
        prohibited_uses=tuple(ai.prohibited_uses),
        human_oversight_required=ai.human_oversight_required,
        model_lineage_required=ai.model_lineage_required,
        actions=_actions_for_contract(contract),
    )


def build_policy_hook_catalog(
    contracts: dict[str, DatasetContract] | None = None,
) -> PolicyHookCatalog:
    """Return the full governed policy-hook catalog in stable dataset order."""
    registry = contracts or load_contracts()
    hooks = tuple(
        policy_hook_from_contract(registry[dataset_id])
        for dataset_id in sorted(registry)
    )
    return PolicyHookCatalog(hooks=hooks)


def validate_policy_action(
    hook: AgentPolicyHook,
    action_id: str,
    consumer_class: str,
) -> PolicyAction:
    """Fail loudly when a consumer class is not allowed for one action."""
    for action in hook.actions:
        if action.action_id == action_id:
            if consumer_class not in action.allowed_consumer_classes:
                raise PolicyHookError(
                    hook.dataset_id,
                    f"consumer class {consumer_class!r} is not allowed for action {action_id!r}",
                )
            return action
    raise PolicyHookError(hook.dataset_id, f"unknown action {action_id!r}")


def validate_ml_training_allowed(
    contract: DatasetContract,
    consumer_class: str = "internal_ml",
) -> AgentPolicyHook:
    """Evidence-boundary check before governed ML training starts."""
    hook = policy_hook_from_contract(contract)
    if not contract.ai_governance.ai_use_allowed:
        raise PolicyHookError(
            contract.dataset_id,
            "AI use is not allowed for this dataset contract",
        )
    action = validate_policy_action(hook, ML_TRAIN_ACTION, consumer_class)
    if action.requires_ml_lineage and not contract.ai_governance.model_lineage_required:
        raise PolicyHookError(
            contract.dataset_id,
            "ml.train requires model_lineage_required on the contract",
        )
    return hook


def bind_mlflow_policy_hook(run: Any, hook: AgentPolicyHook) -> None:
    """Attach policy-hook identity tags to one active MLflow run."""
    tags = mlflow_tags_for_policy_hook(hook)
    set_tag = getattr(run, "set_tag", None)
    if callable(set_tag):
        for key, value in tags.items():
            set_tag(key, value)
        return

    import mlflow

    for key, value in tags.items():
        mlflow.set_tag(key, value)


def mlflow_tags_for_policy_hook(hook: AgentPolicyHook) -> dict[str, str]:
    """Attach policy-hook identity to an MLflow run alongside ML lineage tags."""
    return {
        "slh.policy_hook_schema": POLICY_HOOK_SCHEMA_VERSION,
        "slh.policy_hook_sha256": hook.sha256(),
        "slh.policy_enforcement_mode": hook.enforcement_mode,
        "slh.dataset_id": hook.dataset_id,
    }
