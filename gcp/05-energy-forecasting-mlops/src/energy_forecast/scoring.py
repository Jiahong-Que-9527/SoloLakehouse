"""Batch scoring and the serving record (step 5).

Scores the holdout window with a pinned registry version and writes the
serving record to ``energy_ml.prediction`` (design §4): one row per
predicted interval with ``interval_start``, ``predicted_mw``,
``model_version``, ``release_id``, ``predicted_at`` and ``batch_id``.
A second batch for the same version and interval replaces those keys —
the upsert is a BigQuery MERGE keyed on (model_version, interval_start).

The prediction traces to its model, evaluation, dataset release and code
revision: the scored rows are recomputed from the feature build of the
pinned dataset, and ``verify_trace`` re-checks the lineage end to end.
"""

from datetime import datetime

from energy_forecast.canonical import canonical_checksum

PREDICTION_SCHEMA = [
    ("interval_start", "TIMESTAMP"),
    ("predicted_mw", "FLOAT64"),
    ("model_version", "INT64"),
    ("release_id", "STRING"),
    ("predicted_at", "TIMESTAMP"),
    ("batch_id", "STRING"),
]

# bq mk parses "name:TYPE" pairs; a space-separated DDL would create
# column names like "interval_start TIMESTAMP" (type STRING).
TABLE_DDL = (
    "interval_start:TIMESTAMP,predicted_mw:FLOAT64,model_version:INT64,"
    "release_id:STRING,predicted_at:TIMESTAMP,batch_id:STRING"
)


def score_batch(
    model,
    feature_rows: list[dict],
    *,
    model_version: int,
    release_id: str,
    predicted_at: datetime,
) -> tuple[list[dict], str]:
    """Score the feature rows with one pinned model version; returns the
    prediction rows and the batch id (content + issue time, not wall clock)."""
    rows = [
        {
            "interval_start": row["interval_start"],
            "predicted_mw": round(float(pred), 6),
            "model_version": int(model_version),
            "release_id": release_id,
            "predicted_at": predicted_at,
        }
        for row, pred in zip(
            feature_rows, model.predict(_feature_matrix(feature_rows)), strict=True
        )
    ]
    batch_id = batch_identifier(rows)
    for row in rows:
        row["batch_id"] = batch_id
    return rows, batch_id


def batch_identifier(rows: list[dict]) -> str:
    """Deterministic batch id: the canonical checksum of the scored rows
    plus the issue timestamp, so the same version over the same window
    replays to the same batch id."""
    payload = [
        {
            "interval_start": row["interval_start"].isoformat(),
            "predicted_mw": row["predicted_mw"],
            "model_version": row["model_version"],
            "predicted_at": row["predicted_at"].isoformat(),
        }
        for row in rows
    ]
    return "batch-" + canonical_checksum(payload)[:16]


def merge_statement(table: str, rows: list[dict]) -> str:
    """The BigQuery MERGE that replaces (model_version, interval_start) keys."""

    def _struct(row: dict, aliased: bool) -> str:
        # Timestamps are cast explicitly: untyped string literals would make
        # the UNNEST fields STRING and break the ON comparison.

        def stamp(value) -> str:
            return f"CAST('{value.isoformat()}' AS TIMESTAMP)"

        parts = [
            stamp(row["interval_start"]) + (" AS interval_start" if aliased else ""),
            f"{row['predicted_mw']}" + (" AS predicted_mw" if aliased else ""),
            f"{row['model_version']}" + (" AS model_version" if aliased else ""),
            f"'{row['release_id']}'" + (" AS release_id" if aliased else ""),
            stamp(row["predicted_at"]) + (" AS predicted_at" if aliased else ""),
            f"'{row['batch_id']}'" + (" AS batch_id" if aliased else ""),
        ]
        return "STRUCT(" + ", ".join(parts) + ")"

    # The first struct carries the field aliases; UNNEST of anonymous
    # structs yields f0_/f1_ names the MERGE cannot reference.
    values = ",\n  ".join(
        [_struct(rows[0], aliased=True)] + [_struct(row, aliased=False) for row in rows[1:]]
    )
    return f"""MERGE `{table}` T
USING (
  SELECT * FROM UNNEST([
  {values}
  ])
) S
ON T.model_version = S.model_version AND T.interval_start = S.interval_start
WHEN MATCHED THEN UPDATE SET
  predicted_mw = S.predicted_mw, release_id = S.release_id,
  predicted_at = S.predicted_at, batch_id = S.batch_id
WHEN NOT MATCHED THEN INSERT
  (interval_start, predicted_mw, model_version, release_id, predicted_at, batch_id)
VALUES
  (S.interval_start, S.predicted_mw, S.model_version, S.release_id, S.predicted_at, S.batch_id)"""


def _feature_matrix(rows: list[dict]) -> "list[list[float]]":
    from energy_forecast.evaluation import FEATURES

    return [[row[name] for name in FEATURES] for row in rows]


def verify_trace(
    prediction_row: dict,
    *,
    manifest: dict,
    feature_rows: list[dict],
    expected_model=None,
) -> list[str]:
    """Re-check one prediction's lineage; returns the passed check names.

    Traces: model version and release id match the manifest, the scored
    interval exists in the feature build, and re-scoring that interval
    with the same model reproduces the recorded value (determinism)."""
    checks = []
    if prediction_row["model_version"] != manifest["model_version"]:
        raise ValueError(
            f"prediction names version {prediction_row['model_version']} but the "
            f"manifest pins {manifest['model_version']}"
        )
    checks.append("model_version_matches_manifest")
    if prediction_row["release_id"] != manifest["release_id"]:
        raise ValueError("prediction release id differs from the manifest")
    checks.append("release_matches_manifest")

    by_start = {row["interval_start"]: row for row in feature_rows}
    feature_row = by_start.get(prediction_row["interval_start"])
    if feature_row is None:
        raise ValueError(
            f"prediction interval {prediction_row['interval_start']} is not in the feature build"
        )
    checks.append("interval_in_feature_build")

    if expected_model is not None:
        from energy_forecast.evaluation import candidate_predictions

        rescored = candidate_predictions(expected_model, [feature_row])[0]
        if abs(float(rescored) - prediction_row["predicted_mw"]) > 1e-6:
            raise ValueError("re-scoring the interval does not reproduce the prediction")
        checks.append("prediction_reproducible")
    return checks
