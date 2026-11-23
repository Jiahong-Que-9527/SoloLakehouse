from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from charging_forecast import monitoring
from charging_forecast.features import FeatureBuilder
from charging_forecast.serving import PREDICTIONS_NAME, Release, score_issue_day
from charging_forecast.training import FEATURE_COLUMNS


class ConstantModel:
    def predict(self, features):
        return np.full(len(features), 50.0)


def test_window_uses_verified_scores_and_mature_labels(tiny_release, tmp_path):
    release, config = tiny_release
    day = date(2025, 3, 18)
    features = tmp_path / "features"
    feature_manifest = FeatureBuilder(release, config).materialize(day, day, features)
    pinned = Release(
        "model-test",
        {
            "feature_release_id": feature_manifest["feature_release_id"],
            "data_release_id": config["release_id"],
            "mlflow_model_version": 1,
            "source_commit": "test",
        },
        "test-manifest-sha",
        tmp_path / "model.joblib",
        ConstantModel(),
    )
    score_dir = tmp_path / "scores"
    score = score_issue_day(
        pinned,
        release,
        config,
        features,
        day,
        scores_dir=score_dir,
        score_releases_dir=tmp_path / "manifests",
    )
    table = monitoring.load_training_features(features, day, day)
    assert {column for family in monitoring.FAMILIES.values() for column in family} == {
        *FEATURE_COLUMNS,
        "predicted_kwh",
    }
    reference = {
        column: monitoring._reference(table[column].to_numpy(), column in monitoring.CATEGORICAL)
        for column in FEATURE_COLUMNS
    }
    reference["predicted_kwh"] = monitoring._reference(np.full(len(table), 50.0), False)
    calibration = {
        "schema_version": monitoring.SCHEMA_VERSION,
        "model_manifest_sha256": pinned.manifest_sha256,
        "reference": reference,
        "thresholds": {"residual.mae_kwh": {"limit": 0.0}},
    }
    predictions = score_dir / pinned.model_release_id / str(day) / PREDICTIONS_NAME
    args = (
        pinned,
        release,
        config,
        features,
        day,
        calibration,
        predictions,
        score["manifest_path"],
    )
    mature_at = datetime(2025, 3, 20, 1, tzinfo=UTC)
    partial = monitoring.evaluate(*args, as_of=mature_at - timedelta(hours=1))
    assert 0.0 < partial["label_coverage"] < 1.0
    assert partial["signals"]["residual.mae_kwh"]["value"] is None
    assert not partial["signals"]["residual.mae_kwh"]["breached"]
    mature = monitoring.evaluate(*args, as_of=mature_at)
    assert mature["labeled_rows"] == mature["scored_rows"] == 144
    assert mature["signals"]["residual.mae_kwh"]["breached"]
    assert monitoring.retraining_decision(mature)["action"] == "retrain"
    with predictions.open("ab") as out:
        out.write(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        monitoring.evaluate(*args, as_of=mature_at)


def test_policy_records_calendar_drift_data_quality_and_override():
    report = {
        "as_of": "2026-11-17T01:00:00+00:00",
        "issue_date": "2026-11-15",
        "model_release_id": "model-test",
        "model_manifest_sha256": "model-hash",
        "data_manifest_sha256": "data-hash",
        "signals": {
            "residual.mae_kwh": {"breached": True},
            "weather.fcst_temperature_c.missing": {"breached": True},
        },
    }
    last_training = date(2026, 10, 18)
    blocked = monitoring.retraining_decision(report, last_training=last_training)
    assert blocked["action"] == "hold"
    assert set(blocked["reasons"]) == {"input_quality", "drift", "calendar"}
    assert monitoring.retraining_decision(report, last_training=last_training) == blocked

    overridden = monitoring.retraining_decision(
        report, last_training=last_training, manual_reason="weather backfill verified"
    )
    assert overridden["action"] == "retrain"
    assert overridden["decision_id"] != blocked["decision_id"]

    report["signals"] = {}
    assert (
        monitoring.retraining_decision(report, last_training=last_training)["action"] == "retrain"
    )
    assert (
        monitoring.retraining_decision(report, last_training=last_training + timedelta(days=1))[
            "action"
        ]
        == "hold"
    )


def test_unseen_categories_and_missing_values_use_separate_buckets():
    spec = monitoring._reference(np.array(["a", "b", None], dtype=object), True)
    observed, _, missing = monitoring._distribution(
        np.array(["a", "new", None, None], dtype=object), spec
    )
    assert observed.tolist() == [0.25, 0.0, 0.25, 0.5]
    assert missing == 0.5
