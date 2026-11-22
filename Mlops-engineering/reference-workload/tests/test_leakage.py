"""Leakage test suite (M02): the contract's four leakage tests.

Shift test, forecast-reference test, duplicate-materialization test and the
per-fold automated leak check, mirroring docs/feature-contract.md.
"""

from __future__ import annotations

import json
import shutil
from datetime import date

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from charging_forecast.contract import build_manifest, git_commit, issue_time_utc
from charging_forecast.features import FeatureBuilder, check_fold_leakage, load_issue_features

US = 1_000_000
US_HOUR = 3_600 * US
ISSUE = date(2025, 3, 11)


def _shift_timestamp_column(table: pa.Table, column: str, micros: int) -> pa.Table:
    ints = table[column].cast(pa.int64())
    shifted = pc.add(ints, pa.scalar(micros, type=pa.int64()))
    return table.set_column(
        table.schema.get_field_index(column),
        column,
        shifted.cast(pa.timestamp("us", tz="UTC")),
    )


def _rewrite_release_table(release, cfg, name: str, transform) -> None:
    """Apply one transform to every partition of a source table, in place,
    then re-pin the manifest so the modified copy is a consistent release."""
    for path in sorted((release / "data" / name).rglob("*.parquet")):
        pq.write_table(transform(pq.read_table(path)), path)
    manifest = build_manifest(release, cfg, git_commit(release))
    (release / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@pytest.fixture()
def tiny_features(tiny_release):
    release, cfg = tiny_release
    builder = FeatureBuilder(release, cfg)
    features_dir = release.parent / "features"
    builder.materialize(ISSUE, ISSUE, features_dir)
    return release, cfg, builder, features_dir


def test_shift_delay_makes_rows_unreadable_to_the_loader(tiny_features):
    _release, _cfg, _builder, features_dir = tiny_features
    assert load_issue_features(features_dir, ISSUE).num_rows == 6 * 24

    # Shift every feature row's available_at one step later, in place.
    for path in sorted(features_dir.rglob("*.parquet")):
        pq.write_table(_shift_timestamp_column(pq.read_table(path), "available_at", US_HOUR), path)

    assert load_issue_features(features_dir, ISSUE).num_rows == 0  # loader rejects

    raw = pq.read_table(sorted(features_dir.rglob("*.parquet"))[0])
    assert raw.num_rows > 0  # bypassing the loader would leak the shifted rows


def test_source_delay_turns_affected_lags_unreadable(tiny_release):
    release, cfg = tiny_release
    clean = FeatureBuilder(release, cfg).build_issue(ISSUE)

    shifted_release = release.parent / "release_delayed"
    shutil.copytree(release, shifted_release)
    _rewrite_release_table(
        shifted_release,
        cfg,
        "demand",
        lambda t: _shift_timestamp_column(t, "available_at", US_HOUR),
    )
    delayed = FeatureBuilder(shifted_release, cfg, verify_source=False).build_issue(ISSUE)

    # The most recent demand hour is no longer readable at T; earlier-anchored
    # columns keep their values because the windows are fixed clock ranges.
    assert all(np.isnan(delayed["demand_latest"].to_pylist()))
    for column in ("demand_lag_24h", "demand_lag_168h", "fcst_temperature_c", "price_current"):
        assert delayed[column].to_pylist() == clean[column].to_pylist(), column


def test_source_advance_changes_no_feature_value(tiny_release):
    release, cfg = tiny_release
    clean = FeatureBuilder(release, cfg).build_issue(ISSUE)

    shifted_release = release.parent / "release_advanced"
    shutil.copytree(release, shifted_release)
    _rewrite_release_table(
        shifted_release,
        cfg,
        "demand",
        lambda t: _shift_timestamp_column(t, "available_at", -US_HOUR),
    )
    advanced = FeatureBuilder(shifted_release, cfg, verify_source=False).build_issue(ISSUE)

    assert advanced.drop(["available_at"]).equals(clean.drop(["available_at"]))


def test_forecast_with_wrong_reference_time_fails_the_build(tiny_release):
    release, cfg = tiny_release
    shifted_release = release.parent / "release_badfcst"
    shutil.copytree(release, shifted_release)
    _rewrite_release_table(
        shifted_release,
        cfg,
        "weather_fcst",
        lambda t: _shift_timestamp_column(t, "reference_hour_utc", 2 * US_HOUR),
    )
    with pytest.raises(ValueError, match="day-ahead"):
        FeatureBuilder(shifted_release, cfg, verify_source=False).build_issue(ISSUE)


def test_duplicate_materialization_is_byte_identical(tiny_release):
    release, cfg = tiny_release
    builder = FeatureBuilder(release, cfg)
    out_a, out_b = release.parent / "feat_a", release.parent / "feat_b"
    manifest_a = builder.materialize(ISSUE, ISSUE, out_a)
    manifest_b = builder.materialize(ISSUE, ISSUE, out_b)

    assert manifest_a == manifest_b
    for entry in manifest_a["files"]:
        assert (out_a / entry["path"]).read_bytes() == (out_b / entry["path"]).read_bytes()
    assert (out_a / "manifest.json").read_bytes() == (out_b / "manifest.json").read_bytes()


def test_fold_check_passes_clean_features_and_detects_tampering(tiny_features):
    _release, _cfg, _builder, features_dir = tiny_features
    passed, detail = check_fold_leakage(features_dir, ISSUE)
    assert passed, detail

    path = sorted(features_dir.rglob("*.parquet"))[0]
    table = pq.read_table(path)
    stamps = table["available_at"].cast(pa.int64()).to_pylist()
    tampered = table.set_column(
        table.schema.get_field_index("available_at"),
        "available_at",
        pa.array([stamps[0] + US_HOUR] + stamps[1:], type=pa.timestamp("us", tz="UTC")),
    )
    pq.write_table(tampered, path)
    passed, detail = check_fold_leakage(features_dir, ISSUE)
    assert not passed and "stamped after T" in detail


def test_fold_check_flags_past_targets(tiny_features):
    _release, _cfg, _builder, features_dir = tiny_features
    path = sorted(features_dir.rglob("*.parquet"))[0]
    table = pq.read_table(path)
    hours = table["hour_utc"].cast(pa.int64()).to_pylist()
    past = int(issue_time_utc(ISSUE).timestamp() * US) - 5 * US_HOUR
    tampered = table.set_column(
        table.schema.get_field_index("hour_utc"),
        "hour_utc",
        pa.array([past] + hours[1:], type=pa.timestamp("us", tz="UTC")),
    )
    pq.write_table(tampered, path)
    passed, detail = check_fold_leakage(features_dir, ISSUE)
    assert not passed and "target hours at or before T" in detail


def test_loader_enforces_schema_version(tiny_features):
    _release, _cfg, _builder, features_dir = tiny_features
    manifest_path = features_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "charging-features-v2"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="schema mismatch"):
        load_issue_features(features_dir, ISSUE)
