"""ML experiment runner for ECB/DAX gold features."""

from __future__ import annotations

import os
import pickle
import tempfile
import urllib.parse
from io import BytesIO
from pathlib import Path
from typing import Any

import mlflow
import pandas as pd
import structlog

from ml.train_ecb_dax_model import train

logger = structlog.get_logger()


def _gold_dataframe_from_trino(trino_url: str) -> pd.DataFrame:
    import trino as trino_mod

    parsed = urllib.parse.urlparse(trino_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8080
    user = os.environ.get("TRINO_USER", "sololakehouse")
    conn = trino_mod.dbapi.connect(
        host=host,
        port=port,
        user=user,
        catalog="iceberg",
        schema="gold",
        http_scheme="http",
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM ecb_dax_features_iceberg")
    rows = cur.fetchall()
    if cur.description is None:
        raise ValueError("Trino returned no column description for Gold Iceberg table")
    columns = [d[0] for d in cur.description]
    df = pd.DataFrame(rows, columns=columns)
    cur.close()
    conn.close()
    return df


def _gold_dataframe_from_minio_parquet(minio_client: Any, bucket: str) -> pd.DataFrame:
    gold_path = "gold/rate_impact_features/ecb_dax_features.parquet"
    response = minio_client.get_object(bucket, gold_path)
    try:
        return pd.read_parquet(BytesIO(response.read()))
    finally:
        response.close()
        response.release_conn()


def run_experiment_set(
    minio_client: Any,
    mlflow_tracking_uri: str,
    bucket: str = "sololakehouse",
    trino_url: str | None = None,
) -> str:
    """Run all configured experiment combinations and return the best run_id."""
    resolved_trino = trino_url or os.environ.get("TRINO_URL")
    if resolved_trino:
        df = _gold_dataframe_from_trino(resolved_trino)
    else:
        df = _gold_dataframe_from_minio_parquet(minio_client, bucket)

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
