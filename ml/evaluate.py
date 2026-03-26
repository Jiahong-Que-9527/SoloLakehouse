"""ML experiment runner for ECB/DAX gold features."""

from __future__ import annotations

import pickle
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import mlflow
import pandas as pd
import structlog

from ml.train_ecb_dax_model import train

logger = structlog.get_logger()


def run_experiment_set(
    minio_client: Any, mlflow_tracking_uri: str, bucket: str = "sololakehouse"
) -> str:
    """Run all configured experiment combinations and return the best run_id."""
    gold_path = "gold/rate_impact_features/ecb_dax_features.parquet"
    response = minio_client.get_object(bucket, gold_path)
    try:
        df = pd.read_parquet(BytesIO(response.read()))
    finally:
        response.close()
        response.release_conn()

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
