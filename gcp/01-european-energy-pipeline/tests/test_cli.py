import json

import pyarrow.parquet as pq

from energy_pipeline.cli import main
from test_normalize import encode, sample_rows


def command(tmp_path, raw=None):
    source = tmp_path / "source.csv"
    source.write_bytes(encode(sample_rows()) if raw is None else raw)
    return [
        "normalize",
        "--input",
        str(source),
        "--from",
        "2026-06-08",
        "--until",
        "2026-06-09",
        "--output",
        str(tmp_path / "output"),
    ]


def test_repeat_runs_preserve_data_and_prior_outputs(tmp_path, capsys):
    args = command(tmp_path)
    assert main(args) == 0
    capsys.readouterr()
    first_dir = next((tmp_path / "output").iterdir())
    original = {p.name: p.read_bytes() for p in first_dir.iterdir()}
    assert main(args) == 0
    assert {p.name: p.read_bytes() for p in first_dir.iterdir()} == original
    directories = list((tmp_path / "output").iterdir())
    assert len(directories) == 2
    manifests = [json.loads((d / "manifest.json").read_text()) for d in directories]
    assert manifests[0]["run_id"] != manifests[1]["run_id"]
    for key in ("input_sha256", "output_sha256", "row_count"):
        assert manifests[0][key] == manifests[1][key]
    manifest = manifests[0]
    assert manifest["row_count"] == 96
    assert manifest["license"] == "CC-BY-4.0"
    assert manifest["attribution"] == "Bundesnetzagentur | SMARD.de"
    assert "git_sha" in manifest and "git_dirty" in manifest
    assert "retrieved_at" not in manifest  # Processing time is not source retrieval time.
    assert pq.read_table(first_dir / "observations.parquet").num_rows == 96


def test_failed_input_writes_report_without_parquet_or_altering_success(tmp_path, capsys):
    args = command(tmp_path)
    assert main(args) == 0
    good_dir = next((tmp_path / "output").iterdir())
    original = {p.name: p.read_bytes() for p in good_dir.iterdir()}
    rows = sample_rows()
    rows[15][2] = ""
    assert main(command(tmp_path, encode(rows))) == 1
    assert {p.name: p.read_bytes() for p in good_dir.iterdir()} == original
    failed_dir = next(d for d in (tmp_path / "output").iterdir() if d != good_dir)
    assert not (failed_dir / "observations.parquet").exists()
    quality = json.loads((failed_dir / "quality.json").read_text())
    assert quality["status"] == "failed"
    assert "line 17" in quality["errors"][0]
    assert json.loads((failed_dir / "manifest.json").read_text())["quality_status"] == "failed"
    assert "validation failed" in capsys.readouterr().err


def test_missing_file_has_clear_error(tmp_path, capsys):
    args = command(tmp_path)
    (tmp_path / "source.csv").unlink()
    assert main(args) == 1
    assert "error:" in capsys.readouterr().err
    assert not (tmp_path / "output").exists()


def test_invalid_window_has_clear_error(tmp_path, capsys):
    args = command(tmp_path)
    args[args.index("--until") + 1] = "2026-06-08"
    assert main(args) == 1
    assert "--from must be earlier" in capsys.readouterr().err


def test_git_sha_env_override(monkeypatch):
    from energy_pipeline.cli import revision

    monkeypatch.setenv("GIT_SHA", "abc123def4567890")
    assert revision() == {"git_sha": "abc123def4567890", "git_dirty": None}


def test_git_sha_env_blank_falls_back_to_git(monkeypatch):
    from energy_pipeline.cli import revision

    monkeypatch.setenv("GIT_SHA", "   ")
    result = revision()
    assert set(result) == {"git_sha", "git_dirty"}
