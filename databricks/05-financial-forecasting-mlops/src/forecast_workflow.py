"""Train, score and monitor the D05 release using MLflow and Delta."""

import hashlib
import json
import re
from datetime import date
from math import isclose
from statistics import fmean

import mlflow
import mlflow.sklearn
import pandas as pd
import sklearn
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from forecast_core import (
    CANDIDATE_PARAMS,
    FEATURE_VERSION,
    FEATURES,
    SERIES,
    Observation,
    build_examples,
    evaluation_folds,
    qualifies,
    synthetic_observations,
)

SYNTHETIC = {
    "rollback_a": ("d05-rollback-a-v1", 1.2),
    "rollback_b": ("d05-rollback-b-v1", 1.4),
    "gate_reject": ("d05-gate-reject-v1", 1.2),
}
GATE = "candidate_mae <= last_value_mae"
OBSERVATION_SCHEMA = (
    "observation_date date, usd_per_eur double, series_key string, release_id string"
)
MODEL_SCHEMA = """
    model_version string, model_name string, registry string, run_id string,
    training_table string, training_version long, training_release string, feature_version string,
    git_sha string
"""


def seed(spark, schema, name, release_id, observations, source_sha256=""):
    table = f"{schema}.{name}"
    spark.createDataFrame(
        [(row.day, row.value, SERIES, release_id) for row in observations],
        OBSERVATION_SCHEMA,
    ).write.saveAsTable(table)
    version = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first().version
    return {
        "table": table,
        "table_version": version,
        "release_id": release_id,
        "source_sha256": source_sha256,
    }


def snapshot_examples(spark, table, version, release_id):
    if not re.fullmatch(r"workspace\.ecb_d05_[a-z0-9_]+\.[a-z0-9_]+", table) or version < 0:
        raise ValueError("Expected a version in the isolated D05 workspace schema")
    raw = spark.sql(
        f"""
        SELECT observation_date, usd_per_eur
        FROM {table} VERSION AS OF {version}
        WHERE release_id = :release AND series_key = :series
        ORDER BY observation_date
        """,
        args={"release": release_id, "series": SERIES},
    ).collect()
    return build_examples([Observation(row.observation_date, row.usd_per_eur) for row in raw])


def frame(rows):
    return pd.DataFrame([row.features for row in rows], columns=list(FEATURES))


def evaluate(examples, snapshot, git_sha):
    folds = list(evaluation_folds(examples))
    report = {}
    for model_name, factory in (
        ("last_value", None),
        ("linear", LinearRegression),
        ("gradient_boosted", lambda: GradientBoostingRegressor(**CANDIDATE_PARAMS)),
    ):
        outcomes = []
        with mlflow.start_run(run_name=f"{snapshot['release_id']} / {model_name}") as run:
            mlflow.log_params(
                {
                    **snapshot,
                    "features": ",".join(FEATURES),
                    "feature_version": FEATURE_VERSION,
                    "git_sha": git_sha,
                    "sklearn_version": sklearn.__version__,
                    "pandas_version": pd.__version__,
                    "mlflow_version": mlflow.__version__,
                    "promotion_gate": GATE,
                }
            )
            if model_name == "gradient_boosted":
                mlflow.log_params(CANDIDATE_PARAMS)
            for fold, (cutoff, training, held_out) in enumerate(folds, 1):
                train_y = [row.label for row in training]
                test_x = frame(held_out)
                if factory is None:
                    predictions = test_x["lag_1"].to_numpy()
                else:
                    model = factory().fit(frame(training), train_y)
                    predictions = model.predict(test_x)
                mae = fmean(
                    abs(prediction - row.label)
                    for row, prediction in zip(held_out, predictions, strict=True)
                )
                outcome = {
                    "cutoff": str(cutoff),
                    "training_count": len(training),
                    "latest_training_label": str(training[-1].label_date),
                    "evaluation_count": len(held_out),
                    "first_evaluation_label": str(held_out[0].label_date),
                    "last_evaluation_label": str(held_out[-1].label_date),
                    "mae": mae,
                }
                outcomes.append(outcome)
                mlflow.log_metric(f"fold_{fold}_mae", mae)
                mlflow.log_metric(f"fold_{fold}_evaluation_count", len(held_out))
            mlflow.log_dict(outcomes, "evaluation.json")
            entry = {"run_id": run.info.run_id, "folds": outcomes}
            if model_name == "gradient_boosted":
                eligible = qualifies(outcomes[-1]["mae"], report["last_value"]["folds"][-1]["mae"])
                mlflow.set_tag("promotion", "eligible" if eligible else "rejected")
                signature = infer_signature(test_x, predictions)
                artifact = mlflow.sklearn.log_model(
                    model,
                    artifact_path="model",
                    signature=signature,
                    input_example=test_x.iloc[:1],
                )
                entry.update(eligible=eligible, model_uri=artifact.model_uri)
            report[model_name] = entry
    return report


def registry_for(schema):
    full_name = f"{schema}.rollback_model"
    mlflow.set_registry_uri("databricks-uc")
    try:
        MlflowClient().create_registered_model(full_name)
    except MlflowException as error:
        if error.error_code not in {
            "PERMISSION_DENIED",
            "FEATURE_DISABLED",
            "UNIMPLEMENTED",
            "INVALID_STATE",
        }:
            raise
        mlflow.set_registry_uri("databricks")
        fallback = f"{schema.split('.')[-1]}_rollback_model"
        MlflowClient().create_registered_model(fallback)
        return "databricks", fallback, error.error_code
    return "databricks-uc", full_name, None


def register(candidate, snapshot, registry, model_name, git_sha):
    if not candidate["eligible"]:
        raise ValueError("Candidate failed the naive baseline gate")
    version = mlflow.register_model(candidate["model_uri"], model_name, await_registration_for=120)
    tags = {
        "training_table": snapshot["table"],
        "training_version": str(snapshot["table_version"]),
        "training_release": snapshot["release_id"],
        "feature_version": FEATURE_VERSION,
        "git_sha": git_sha,
    }
    client = MlflowClient()
    for key, value in tags.items():
        client.set_model_version_tag(model_name, version.version, key, value)
    verified = client.get_model_version(model_name, version.version)
    if any(verified.tags.get(key) != val for key, val in tags.items()):
        raise AssertionError("Registry tags do not match the pinned model inputs")
    return {
        "model_version": str(version.version),
        "model_name": model_name,
        "registry": registry,
        "run_id": candidate["run_id"],
        **tags,
        "training_version": snapshot["table_version"],
    }


def train(spark, schema, fixtures, git_sha, job_run_id):
    spark.sql(f"CREATE SCHEMA {schema}")
    fixture_path = fixtures / "ecb_2025q2.json"
    ecb = json.loads(fixture_path.read_text())
    if ecb["series_key"] != SERIES or ecb["unit"] != "USD_PER_EUR":
        raise ValueError("Incompatible ECB source series")
    snapshots = {
        "ecb": seed(
            spark,
            schema,
            "ecb_gold",
            ecb["release_id"],
            [Observation(date.fromisoformat(d), float(v)) for d, v in ecb["observations"]],
            ecb["source_sha256"],
        )
    }
    for name, (release_id, high) in SYNTHETIC.items():
        snapshots[name] = seed(
            spark,
            schema,
            name,
            release_id,
            synthetic_observations(high, reject=name == "gate_reject"),
        )

    owner = spark.sql("SELECT current_user()").first()[0]
    experiment = mlflow.set_experiment(f"/Users/{owner}/d05-{schema.split('.')[-1]}")
    registry, rollback_name, fallback_reason = registry_for(schema)
    reports = {}
    versions = []
    for name, snapshot in snapshots.items():
        examples = snapshot_examples(
            spark, snapshot["table"], snapshot["table_version"], snapshot["release_id"]
        )
        report = evaluate(examples, snapshot, git_sha)
        reports[name] = report
        candidate = report["gradient_boosted"]
        if name in {"rollback_a", "rollback_b"}:
            versions.append(register(candidate, snapshot, registry, rollback_name, git_sha))
        elif name == "ecb" and candidate["eligible"]:
            model_name = rollback_name.replace("rollback_model", "ecb_candidate")
            MlflowClient().create_registered_model(model_name)
            report["registered"] = register(candidate, snapshot, registry, model_name, git_sha)
        elif name == "gate_reject":
            if candidate["eligible"]:
                raise AssertionError("Synthetic rejection fixture unexpectedly passed")
            rejected = MlflowClient().get_run(candidate["run_id"])
            if rejected.data.tags["promotion"] != "rejected":
                raise AssertionError("Rejected candidate could not be read back from MLflow")

    spark.createDataFrame(
        [
            tuple(
                v[key]
                for key in (
                    "model_version",
                    "model_name",
                    "registry",
                    "run_id",
                    "training_table",
                    "training_version",
                    "training_release",
                    "feature_version",
                    "git_sha",
                )
            )
            for v in versions
        ],
        MODEL_SCHEMA,
    ).write.saveAsTable(f"{schema}.rollback_versions")
    spark.createDataFrame([], OBSERVATION_SCHEMA).write.saveAsTable(f"{schema}.later_actuals")
    return {
        "job_run_id": job_run_id,
        "git_sha": git_sha,
        "experiment_id": experiment.experiment_id,
        "library_versions": {
            "mlflow": mlflow.__version__,
            "pandas": pd.__version__,
            "sklearn": sklearn.__version__,
        },
        "registry": registry,
        "registry_fallback_reason": fallback_reason,
        "snapshots": snapshots,
        "ecb_normalized_fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "reports": reports,
        "rollback_versions": versions,
    }


def merge_row(spark, table, row, columns, key):
    data = spark.createDataFrame([row], columns)
    data.createOrReplaceTempView("d05_batch_row")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({columns}) USING DELTA")
    spark.sql(f"""
        MERGE INTO {table} target USING d05_batch_row source ON {key}
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)


def score(spark, schema, fixtures, model_version, job_run_id):
    version = spark.sql(
        f"SELECT * FROM {schema}.rollback_versions WHERE model_version = :model_version",
        args={"model_version": model_version},
    ).first()
    if not version:
        raise ValueError(f"Unknown registered rollback model version {model_version}")
    expected = json.loads((fixtures / "rollback_reference.json").read_text())
    input_table = f"{schema}.rollback_a"
    input_version = 0
    release_id = expected["input_release_id"]
    row = snapshot_examples(spark, input_table, input_version, release_id)[-1]
    if str(row.as_of) != expected["as_of_date"] or row.label is not None:
        raise AssertionError("The scoring cutoff does not match the pinned reference")
    mlflow.set_registry_uri(version.registry)
    model = mlflow.sklearn.load_model(f"models:/{version.model_name}/{model_version}")
    prediction = float(model.predict(frame([row]))[0])
    reference = expected["expected_score_by_training_release"][version.training_release]
    if not isclose(prediction, reference, rel_tol=0, abs_tol=expected["absolute_tolerance"]):
        raise AssertionError(f"Registry prediction {prediction} differs from reference {reference}")
    table = f"{schema}.predictions"
    key = """target.as_of_date = source.as_of_date AND target.series_key = source.series_key
             AND target.model_version = source.model_version"""
    merge_row(
        spark,
        table,
        (
            row.as_of,
            SERIES,
            prediction,
            model_version,
            version.run_id,
            release_id,
            input_table,
            input_version,
            FEATURE_VERSION,
            version.git_sha,
        ),
        """as_of_date date, series_key string, prediction double, model_version string,
          model_run_id string, release_id string, input_table string, table_version long,
          feature_version string, git_sha string""",
        key,
    )
    scored = spark.table(table).orderBy("model_version").collect()
    if len(scored) != len({(r.as_of_date, r.series_key, r.model_version) for r in scored}):
        raise AssertionError("A batch retry created duplicate prediction keys")
    return {
        "job_run_id": job_run_id,
        "model_version": model_version,
        "reference": reference,
        "predictions": [r.asDict() for r in scored],
        "actuals_before_monitoring": spark.table(f"{schema}.later_actuals").count(),
    }


def monitor(spark, schema, fixtures, model_version, job_run_id):
    expected = json.loads((fixtures / "rollback_reference.json").read_text())
    release_id = expected["input_release_id"]
    as_of = date.fromisoformat(expected["as_of_date"])
    actual_day = date.fromisoformat(expected["later_actual_date"])
    if actual_day <= as_of:
        raise ValueError("An actual must follow the observation cutoff")
    prediction = spark.sql(
        f"SELECT * FROM {schema}.predictions WHERE model_version = :model_version",
        args={"model_version": model_version},
    ).first()
    if not prediction or prediction.as_of_date != as_of or prediction.release_id != release_id:
        raise ValueError("Score the pinned release before monitoring it")

    actuals = f"{schema}.later_actuals"
    merge_row(
        spark,
        actuals,
        (actual_day, expected["expected_next_actual"], SERIES, release_id),
        OBSERVATION_SCHEMA,
        """target.observation_date = source.observation_date
                 AND target.series_key = source.series_key
                 AND target.release_id = source.release_id""",
    )
    actual = spark.sql(
        f"""
        SELECT observation_date, usd_per_eur
        FROM {actuals}
        WHERE series_key = :series AND release_id = :release_id AND observation_date > :as_of
        ORDER BY observation_date LIMIT 1
        """,
        args={"series": SERIES, "release_id": release_id, "as_of": as_of},
    ).first()
    residual = actual.usd_per_eur - prediction.prediction
    residuals = f"{schema}.residuals"
    merge_row(
        spark,
        residuals,
        (
            as_of,
            SERIES,
            model_version,
            actual.observation_date,
            prediction.prediction,
            actual.usd_per_eur,
            residual,
        ),
        """as_of_date date, series_key string, model_version string, actual_date date,
          prediction double, actual double, residual double""",
        """target.as_of_date = source.as_of_date AND target.series_key = source.series_key
           AND target.model_version = source.model_version""",
    )
    return {
        "job_run_id": job_run_id,
        "residuals": [row.asDict() for row in spark.table(residuals).collect()],
    }


def run(spark, fixtures, schema, git_sha, job_run_id, phase, model_version):
    if not re.fullmatch(r"ecb_d05_[a-z0-9_]{1,32}", schema):
        raise ValueError("Expected a dedicated ecb_d05_* schema")
    schema = f"workspace.{schema}"
    if not re.fullmatch(r"[a-f0-9]{40}", git_sha):
        raise ValueError("Expected a full source commit SHA")
    if phase == "train":
        return train(spark, schema, fixtures, git_sha, job_run_id)
    if not re.fullmatch(r"[1-9][0-9]*", model_version):
        raise ValueError("Select a positive registry model version")
    execute = {"score": score, "monitor": monitor}[phase]
    return execute(spark, schema, fixtures, model_version, job_run_id)
