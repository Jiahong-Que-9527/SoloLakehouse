"""Generate governed model cards and evaluation evidence for v2.8 E4."""

from __future__ import annotations

from datetime import UTC, datetime

from governance.contracts import DatasetContract
from governance.ml_lineage import MLLineageTuple
from governance.model_evidence import ModelEvaluationEvidence, ModelEvaluationManifest
from governance.policy_hooks import AgentPolicyHook
from ml.train_ecb_dax_model import FEATURE_COLUMNS, FEATURE_VERSION


def build_model_card_markdown(
    contract: DatasetContract,
    lineage: MLLineageTuple,
    policy_hook: AgentPolicyHook,
    mlflow_run_id: str,
    evaluation_metrics: dict[str, float],
) -> str:
    """Render a traceability-oriented model card from governed sources."""
    ai = contract.ai_governance
    metric_lines = "\n".join(
        f"| {name} | {value:.4f} |" for name, value in sorted(evaluation_metrics.items())
    )
    return "\n".join(
        [
            "# Model Card — fin.ecb_dax_impact",
            "",
            "> Reference-implementation evidence only. Not a regulatory compliance claim.",
            "",
            "## Model identity",
            f"- MLflow run id: `{mlflow_run_id}`",
            f"- Dataset id: `{contract.dataset_id}`",
            f"- Feature version: `{FEATURE_VERSION}`",
            f"- Feature columns: `{', '.join(FEATURE_COLUMNS)}`",
            "",
            "## Intended purpose",
            f"- Business purpose: {contract.business_purpose}",
            f"- Intended AI uses: {', '.join(ai.intended_uses)}",
            f"- Risk tier: `{ai.risk_tier}`",
            "",
            "## Prohibited uses",
            *(f"- {use}" for use in ai.prohibited_uses),
            "",
            "## Human oversight",
            f"- Human oversight required: `{ai.human_oversight_required}`",
            f"- Access policy hint: {contract.access_policy_hint}",
            "",
            "## Training data lineage",
            f"- Iceberg snapshot id: `{lineage.iceberg_snapshot_id}`",
            f"- Dagster run id: `{lineage.dagster_run_id}`",
            f"- Code commit: `{lineage.code_commit}`",
            f"- Data contract hash: `{lineage.data_contract_hash}`",
            f"- Policy hook hash: `{policy_hook.sha256()}`",
            "",
            "## Evaluation metrics",
            "| metric | value |",
            "|---|---:|",
            metric_lines,
            "",
            "## Limitations",
            "- Demo classifier trained on a single governed Gold dataset snapshot.",
            "- Serving, drift monitoring, and runtime enforcement are out of scope for v2.8.",
        ]
    )


def build_model_evaluation_evidence(
    *,
    contract: DatasetContract,
    lineage: MLLineageTuple,
    policy_hook: AgentPolicyHook,
    mlflow_run_id: str,
    evaluation_metrics: dict[str, float],
    generated_at: datetime | None = None,
) -> ModelEvaluationManifest:
    """Build a hash-bound model evaluation evidence manifest."""
    stamp = generated_at or datetime.now(UTC)
    markdown = build_model_card_markdown(
        contract,
        lineage,
        policy_hook,
        mlflow_run_id,
        evaluation_metrics,
    )
    evidence = ModelEvaluationEvidence(
        dataset_id=contract.dataset_id,
        mlflow_run_id=mlflow_run_id,
        ml_lineage=lineage,
        policy_hook_sha256=policy_hook.sha256(),
        evaluation_metrics=evaluation_metrics,
        model_card_markdown=markdown,
        generated_at=stamp,
    )
    return ModelEvaluationManifest.from_evidence(evidence, generated_at=stamp)
