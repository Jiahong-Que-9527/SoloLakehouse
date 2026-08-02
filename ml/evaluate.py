"""ML experiment runner for ECB/DAX gold features."""

from __future__ import annotations

import pickle
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import mlflow
import pandas as pd
import structlog

from governance.ml_lineage import MLLineageTuple, bind_mlflow_run
from ingestion import iceberg_io
from ml.train_ecb_dax_model import train

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

logger = structlog.get_logger()


def _gold_dataframe_from_iceberg(catalog: "Catalog", snapshot_id: str) -> pd.DataFrame:
    """Read exactly the Gold snapshot bound into governed ML lineage."""
    return iceberg_io.scan_table(
        catalog,
        "gold",
        "ecb_dax_features",
        snapshot_id=snapshot_id,
    )


def run_experiment_set(
    catalog: "Catalog",
    mlflow_tracking_uri: str,
    lineage: MLLineageTuple,
) -> str:
    """Run all configured experiment combinations and return the best run_id."""
    df = _gold_dataframe_from_iceberg(catalog, lineage.iceberg_snapshot_id)

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment("ecb_dax_impact")

    best_run_id = ""
    best_accuracy = float("-inf")

    for model_type in ["xgboost", "lightgbm"]:
        for n_estimators in [50, 100, 200]:
            for max_depth in [3, 5]:
                params = {
                    "n_estimators": n_estimators,
                    "max_depth": max_depth,
                }
                with mlflow.start_run() as run:
                    bind_mlflow_run(run, lineage)
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

    if not best_run_id:
        raise ValueError("No MLflow runs were created")
    return best_run_id
