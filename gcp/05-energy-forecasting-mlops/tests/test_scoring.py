"""Batch scoring: rows, batch ids, MERGE statement and the lineage trace."""

from datetime import UTC, datetime, timedelta

import pytest

from energy_forecast.dataset import build_training_dataset
from energy_forecast.evaluation import run_evaluation
from energy_forecast.features import build_features
from energy_forecast.fixture import pinned_release
from energy_forecast.scoring import (
    PREDICTION_SCHEMA,
    TABLE_DDL,
    merge_statement,
    score_batch,
    verify_trace,
)
from energy_forecast.splits import freeze_windows


@pytest.fixture()
def bundle(tmp_path):
    rows, release = pinned_release()
    dataset = build_training_dataset(rows, release)
    windows, _spec = freeze_windows(dataset)
    features = build_features(dataset)
    report, model, _preds = run_evaluation(dataset, windows, features, git_sha="score-test")
    return dataset, windows, features, report, model


def test_scored_rows_carry_the_full_serving_record(bundle):
    _dataset, windows, features, report, model = bundle
    holdout_day = [r for r in features if windows.contains("holdout", r["interval_start"])][:96]
    rows, batch_id = score_batch(
        model,
        holdout_day,
        model_version=2,
        release_id=report["release_id"],
        predicted_at=datetime(2026, 11, 23, 12, 0, tzinfo=UTC),
    )
    assert len(rows) == 96
    assert set(rows[0]) == {name for name, _ in PREDICTION_SCHEMA}
    assert rows[0]["model_version"] == 2
    assert all(row["batch_id"] == batch_id for row in rows)
    # same content + issue time replays to the same batch id
    rows2, batch_id2 = score_batch(
        model,
        holdout_day,
        model_version=2,
        release_id=report["release_id"],
        predicted_at=datetime(2026, 11, 23, 12, 0, tzinfo=UTC),
    )
    assert batch_id2 == batch_id
    assert batch_id.startswith("batch-")


def test_merge_statement_replaces_on_version_and_interval(bundle):
    _dataset, _windows, features, report, model = bundle
    day = [r for r in features if r["interval_start"].weekday() == 0][:4]
    rows, batch_id = score_batch(
        model,
        day,
        model_version=2,
        release_id=report["release_id"],
        predicted_at=datetime(2026, 11, 23, 12, 0, tzinfo=UTC),
    )
    sql = merge_statement("slh-gcp-test:energy_ml.prediction", rows)
    assert "MERGE `slh-gcp-test:energy_ml.prediction` T" in sql
    assert "T.model_version = S.model_version AND T.interval_start = S.interval_start" in sql
    assert "WHEN MATCHED THEN UPDATE" in sql
    assert str(rows[0]["model_version"]) in sql


def test_verify_trace_passes_and_rejects(bundle):
    dataset, windows, features, report, model = bundle
    manifest = {"model_version": 2, "release_id": report["release_id"]}
    day = [r for r in features if windows.contains("holdout", r["interval_start"])][:4]
    rows, _batch_id = score_batch(
        model,
        day,
        model_version=2,
        release_id=report["release_id"],
        predicted_at=datetime(2026, 11, 23, 12, 0, tzinfo=UTC),
    )
    checks = verify_trace(rows[0], manifest=manifest, feature_rows=features, expected_model=model)
    assert checks == [
        "model_version_matches_manifest",
        "release_matches_manifest",
        "interval_in_feature_build",
        "prediction_reproducible",
    ]
    with pytest.raises(ValueError, match="version"):
        verify_trace({**rows[0], "model_version": 1}, manifest=manifest, feature_rows=features)
    with pytest.raises(ValueError, match="not in the feature build"):
        verify_trace(
            {**rows[0], "interval_start": rows[0]["interval_start"] - timedelta(days=365)},
            manifest=manifest,
            feature_rows=features,
        )


def test_table_ddl_matches_the_schema():
    names = [part.split(":")[0] for part in TABLE_DDL.split(",")]
    assert names == [name for name, _ in PREDICTION_SCHEMA]
