"""Release-manifest helpers from the template: determinism and drift."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from district_forecast.releases import (
    build_file_manifest,
    publish_release,
    read_json,
    sha256_file,
    verify_release,
)


def test_manifest_is_deterministic_and_verify_passes(tmp_path: Path):
    first, second = tmp_path / "a", tmp_path / "b"
    for release in (first, second):
        data = release / "data" / "demand"
        data.mkdir(parents=True)
        table = pa_table()
        pq.write_table(table, data / "part-0000.parquet")
        publish_release(
            release,
            build_file_manifest(release, release_id="r1", schema_version="v1", kind="dataset"),
        )
    assert sha256_file(first / "manifest.json") == sha256_file(second / "manifest.json")
    verify_release(first)


def test_verify_release_refuses_drift(tmp_path: Path):
    release = tmp_path / "r"
    data = release / "data" / "demand"
    data.mkdir(parents=True)
    pq.write_table(pa_table(), data / "part-0000.parquet")
    publish_release(
        release, build_file_manifest(release, release_id="r1", schema_version="v1", kind="dataset")
    )
    drifted = pa.table({"value": pa.array([1.0, 2.0, 999.0])})
    pq.write_table(drifted, data / "part-0000.parquet")
    with pytest.raises(ValueError, match="missing or changed"):
        verify_release(release)


def test_verify_release_requires_the_marker(tmp_path: Path):
    release = tmp_path / "r"
    (release / "data" / "demand").mkdir(parents=True)
    pq.write_table(pa_table(), release / "data/demand/part-0000.parquet")
    build_file_manifest(release, release_id="r1", schema_version="v1", kind="dataset")
    with pytest.raises(ValueError, match="_SUCCESS"):
        verify_release(release)


def pa_table():
    return pa.table({"value": pa.array([1.0, 2.0, 3.0])})


def test_json_roundtrip_is_sorted(tmp_path: Path):
    from district_forecast.releases import write_json

    path = tmp_path / "x" / "payload.json"
    write_json(path, {"b": 1, "a": {"d": 2, "c": 3}})
    text = path.read_text()
    assert text.index('"a"') < text.index('"b"')
    assert read_json(path) == {"b": 1, "a": {"d": 2, "c": 3}}


def test_read_json_rejects_missing(tmp_path: Path):

    with pytest.raises(FileNotFoundError):
        read_json(tmp_path / "missing.json")


def test_instantiate_placeholder_substitution(tmp_path: Path):
    """The template instantiates a fresh workload with placeholders replaced
    in file bodies and paths (gap #2 regression: the .tmpl suffix is stripped)."""
    import subprocess
    import sys

    template = Path(__file__).resolve().parents[2] / "09-platform-factory" / "template"
    target = tmp_path / "demo-workload"
    subprocess.run(
        [
            sys.executable,
            str(template / "instantiate.py"),
            "--target",
            str(target),
            "--package",
            "demo_pkg",
            "--workload-id",
            "demo-workload",
            "--entity",
            "site",
            "--entity-plural",
            "sites",
        ],
        check=True,
        capture_output=True,
    )
    assert (target / "pyproject.toml").exists()
    assert (target / "src/demo_pkg/releases.py").exists()
    assert "{{package}}" not in (target / "pyproject.toml").read_text()
    assert "demo-workload" in (target / "pyproject.toml").read_text()
