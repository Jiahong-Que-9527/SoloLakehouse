"""MLflow registry, promotion gate and the model release manifest (step 4).

The gate registers a candidate only when its holdout MAE is less than or
equal to the baseline's (design §1). A refused candidate stays an
experiment — its run is queryable, it gains no registry version. The
release manifest records source SHA, dataset release and checksum,
evaluation report checksum, library versions, run and version ids, so a
prediction traces to its model, evaluation and dataset (design §7.3).

The baseline registers first as version 1 so a previous version exists
for the step-5 rollback drill.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from energy_forecast.canonical import canonical_checksum
from energy_forecast.dataset import TrainingDataset
from energy_forecast.evaluation import report_checksum
from energy_forecast.fixture import Release
from energy_forecast.splits import Windows

REGISTRY_MODEL_NAME = "g05_load_forecast"


class PromotionRefused(ValueError):
    """Raised when the gate refuses a candidate."""


@dataclass(frozen=True)
class Promotion:
    """The registered version and its recorded lineage."""

    model_version: int
    run_id: str
    stage: str
    manifest: dict


def _tracking_uri(tracking_dir: Path) -> str:
    return f"sqlite:///{Path(tracking_dir) / 'mlflow.db'}"


def _ensure_registered_model(client) -> None:
    from mlflow.exceptions import MlflowException

    try:
        client.get_registered_model(REGISTRY_MODEL_NAME)
    except MlflowException:
        client.create_registered_model(REGISTRY_MODEL_NAME)


def _gate(report: dict) -> str:
    candidate = report["holdout"]["candidate"]["mae_mw"]
    baseline = report["holdout"]["baseline"]["mae_mw"]
    if candidate <= baseline:
        return "promoted"
    raise PromotionRefused(
        f"promotion gate refused the candidate: holdout MAE {candidate} MW "
        f"is worse than the baseline {baseline} MW; the run stays an experiment"
    )


def _log_run(mlflow, dataset: TrainingDataset, report: dict, model, experiment_only: bool) -> str:
    tags = {
        "release_id": dataset.metadata["release_id"],
        "git_sha": report["git_sha"],
        "seed": str(report["seed"]),
        "candidate_library": report["candidate"]["library"],
    }
    if experiment_only:
        tags["experiment_only"] = "true"
    mlflow.set_tags(tags)
    mlflow.log_metrics(
        {
            "validation_baseline_mae_mw": report["validation"]["baseline"]["mae_mw"],
            "validation_candidate_mae_mw": report["validation"]["candidate"]["mae_mw"],
            "holdout_baseline_mae_mw": report["holdout"]["baseline"]["mae_mw"],
            "holdout_candidate_mae_mw": report["holdout"]["candidate"]["mae_mw"],
        }
    )
    mlflow.lightgbm.log_model(model, name="model")
    return mlflow.active_run().info.run_id


def register_baseline(
    dataset: TrainingDataset,
    report: dict,
    model,
    tracking_dir: Path,
    git_sha: str,
) -> Promotion:
    """Register the seasonal-naive baseline as version 1 (the rollback target)."""
    import mlflow

    mlflow.set_tracking_uri(_tracking_uri(tracking_dir))
    mlflow.set_registry_uri(_tracking_uri(tracking_dir))
    mlflow.set_experiment(REGISTRY_MODEL_NAME)
    with mlflow.start_run(run_name="baseline-seasonal-naive-7d") as run:
        mlflow.set_tags({**_baseline_tags(dataset, report, git_sha), "role": "baseline"})
        mlflow.log_metrics({"holdout_baseline_mae_mw": report["holdout"]["baseline"]["mae_mw"]})
        mlflow.lightgbm.log_model(model, name="model")
        run_id = run.info.run_id
    client = mlflow.tracking.MlflowClient()
    _ensure_registered_model(client)
    version = client.create_model_version(
        REGISTRY_MODEL_NAME,
        f"runs:/{run_id}/model",
        run_id=run_id,
        tags={"release_id": dataset.metadata["release_id"], "role": "baseline", "git_sha": git_sha},
    )
    return Promotion(int(version.version), run_id, "baseline", {})


def _baseline_tags(dataset: TrainingDataset, report: dict, git_sha: str) -> dict:
    return {
        "release_id": dataset.metadata["release_id"],
        "git_sha": git_sha,
        "seed": str(report["seed"]),
        "candidate_library": "none (seasonal naive)",
    }


def promote_candidate(
    dataset: TrainingDataset,
    report: dict,
    model,
    tracking_dir: Path,
    releases_dir: Path,
) -> Promotion:
    """Run the gate; on pass, register the candidate and publish the manifest.

    The manifest is deterministic except the run/version ids and the
    recorded promotion timestamp, both of which the registry owns.
    """
    from datetime import UTC, datetime

    import mlflow

    mlflow.set_tracking_uri(_tracking_uri(tracking_dir))
    mlflow.set_registry_uri(_tracking_uri(tracking_dir))
    mlflow.set_experiment(REGISTRY_MODEL_NAME)

    gate = _gate(report)  # raises PromotionRefused for a losing candidate
    with mlflow.start_run(run_name="candidate-lightgbm"):
        run_id = _log_run(mlflow, dataset, report, model, experiment_only=False)
    client = mlflow.tracking.MlflowClient()
    _ensure_registered_model(client)
    version = client.create_model_version(
        REGISTRY_MODEL_NAME,
        f"runs:/{run_id}/model",
        run_id=run_id,
        tags={
            "release_id": dataset.metadata["release_id"],
            "role": "candidate",
            "git_sha": report["git_sha"],
            "gate": gate,
        },
    )

    manifest = {
        "manifest_schema_version": "g05-model-manifest-v1",
        "release_id": dataset.metadata["release_id"],
        "input_sha256": dataset.metadata["input_sha256"],
        "git_sha": report["git_sha"],
        "seed": report["seed"],
        "model_name": REGISTRY_MODEL_NAME,
        "model_version": int(version.version),
        "mlflow_run_id": run_id,
        "evaluation_report_sha256": report_checksum(report),
        "holdout_metrics": {
            "baseline": report["holdout"]["baseline"],
            "candidate": report["holdout"]["candidate"],
        },
        "gate": {
            "decision": gate,
            "rule": "holdout candidate MAE <= baseline MAE",
            "holdout_mae_mw": {
                "candidate": report["holdout"]["candidate"]["mae_mw"],
                "baseline": report["holdout"]["baseline"]["mae_mw"],
            },
        },
        "candidate": report["candidate"],
        "registered_at": datetime.now(UTC).isoformat(),
    }
    releases_dir = Path(releases_dir)
    releases_dir.mkdir(parents=True, exist_ok=True)
    (releases_dir / "model-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return Promotion(int(version.version), run_id, gate, manifest)


def refuse_losing_candidate(
    losing_release: Release,
    losing_report: dict,
    tracking_dir: Path,
) -> dict:
    """Record a gate refusal for a deliberately worse candidate: the run
    stays queryable as an experiment and gains no registry version."""
    import mlflow

    mlflow.set_tracking_uri(_tracking_uri(tracking_dir))
    mlflow.set_registry_uri(_tracking_uri(tracking_dir))
    mlflow.set_experiment(REGISTRY_MODEL_NAME)
    with mlflow.start_run(run_name="candidate-losing-experiment"):
        mlflow.set_tags(
            {
                "release_id": losing_release.release_id,
                "git_sha": losing_report["git_sha"],
                "seed": str(losing_report["seed"]),
                "experiment_only": "true",
            }
        )
        mlflow.log_metrics(
            {
                "holdout_baseline_mae_mw": losing_report["holdout"]["baseline"]["mae_mw"],
                "holdout_candidate_mae_mw": losing_report["holdout"]["candidate"]["mae_mw"],
            }
        )
        run_id = mlflow.active_run().info.run_id
    refusal = {
        "decision": "refused",
        "release_id": losing_release.release_id,
        "run_id": run_id,
        "registry_version": None,
        "reason": _gate_message(losing_report),
    }
    return refusal


def _gate_message(report: dict) -> str:
    candidate = report["holdout"]["candidate"]["mae_mw"]
    baseline = report["holdout"]["baseline"]["mae_mw"]
    return (
        f"holdout MAE {candidate} MW is worse than the baseline {baseline} MW; "
        "the run stays an experiment"
    )


def windows_digest(windows: Windows) -> str:
    return canonical_checksum(
        {name: getattr(windows, name).isoformat() for name in windows.__dataclass_fields__}
    )
