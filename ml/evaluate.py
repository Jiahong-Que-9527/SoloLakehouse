"""ML experiment runner for ECB/DAX gold features."""

from __future__ import annotations

import pickle
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import mlflow
import pandas as pd
import structlog

from governance.ml_lineage import MLLineageTuple, bind_mlflow_run
from governance.model_evidence import write_model_evaluation_manifest
from governance.policy_hooks import (
    AgentPolicyHook,
    bind_mlflow_policy_hook,
    validate_ml_training_allowed,
)
from ingestion import iceberg_io
from ml.generate_model_card import build_model_evaluation_evidence
from ml.train_ecb_dax_model import train

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

    from governance.contracts import DatasetContract

logger = structlog.get_logger()


@dataclass(frozen=True)
class ExperimentRunResult:
    """Outcome of one governed ML experiment sweep."""

    best_run_id: str
    model_evidence_path: str
    model_evidence_sha256: str


def _gold_dataframe_from_iceberg(catalog: "Catalog", snapshot_id: str) -> pd.DataFrame:
    """Read exactly the Gold snapshot bound into governed ML lineage."""
    return iceberg_io.scan_table(
        catalog,
        "gold",
        "ecb_german_equity_proxy_features",
        snapshot_id=snapshot_id,
    )


def run_experiment_set(
    catalog: "Catalog",
    mlflow_tracking_uri: str,
    lineage: MLLineageTuple,
    training_contract: "DatasetContract",
) -> ExperimentRunResult:
    """Run all configured experiment combinations and return governed evidence."""
    policy_hook: AgentPolicyHook = validate_ml_training_allowed(training_contract)
    df = _gold_dataframe_from_iceberg(catalog, lineage.iceberg_snapshot_id)

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment("ecb_dax_impact")

    best_run_id = ""
    best_accuracy = float("-inf")
    best_metrics: dict[str, float] = {}

    for model_type in ["xgboost", "lightgbm"]:
        for n_estimators in [50, 100, 200]:
            for max_depth in [3, 5]:
                params = {
                    "n_estimators": n_estimators,
                    "max_depth": max_depth,
                }
                with mlflow.start_run() as run:
                    bind_mlflow_run(run, lineage)
                    bind_mlflow_policy_hook(run, policy_hook)
                    model, metrics = train(df=df, model_type=model_type, params=params)

                    mlflow.log_param("model_type", model_type)
                    mlflow.log_param("n_estimators", n_estimators)
                    mlflow.log_param("max_depth", max_depth)
                    mlflow.log_metrics(
                        {
                            "accuracy": metrics["accuracy"],
                            "precision": metrics["precision"],
                            "recall": metrics["recall"],
                            "f1": metrics["f1"],
                        }
                    )
                    with tempfile.TemporaryDirectory() as tmpdir:
                        model_path = Path(tmpdir) / "model.pkl"
                        model_path.write_bytes(pickle.dumps(model))
                        mlflow.log_artifact(str(model_path), artifact_path="model")

                    logger.info(
                        "ml_run_complete",
                        run_id=run.info.run_id,
                        accuracy=metrics["accuracy"],
                    )

                    if metrics["accuracy"] > best_accuracy:
                        best_accuracy = metrics["accuracy"]
                        best_run_id = run.info.run_id
                        best_metrics = {
                            "accuracy": float(metrics["accuracy"]),
                            "precision": float(metrics["precision"]),
                            "recall": float(metrics["recall"]),
                            "f1": float(metrics["f1"]),
                        }

    if not best_run_id:
        raise ValueError("No MLflow runs were created")

    manifest = build_model_evaluation_evidence(
        contract=training_contract,
        lineage=lineage,
        policy_hook=policy_hook,
        mlflow_run_id=best_run_id,
        evaluation_metrics=best_metrics,
        generated_at=datetime.now(UTC),
    )
    object_path = write_model_evaluation_manifest(manifest)
    client = mlflow.tracking.MlflowClient()
    with tempfile.TemporaryDirectory() as tmpdir:
        card_path = Path(tmpdir) / "model-card.md"
        card_path.write_text(manifest.evidence.model_card_markdown, encoding="utf-8")
        client.log_artifact(best_run_id, str(card_path), artifact_path="governance")

    return ExperimentRunResult(
        best_run_id=best_run_id,
        model_evidence_path=object_path,
        model_evidence_sha256=manifest.evidence_sha256,
    )
