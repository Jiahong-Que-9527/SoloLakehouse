import hashlib
import json
import shutil

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from energy_pipeline.audit import build_report
from energy_pipeline.cli import main
from energy_pipeline.normalize import SCHEMA, STEP, ValidationError
from test_normalize import encode, sample_rows


def completed_runs(tmp_path, start="2026-06-08", until="2026-06-09", count=2):
    source = tmp_path / "source.csv"
    source.write_bytes(encode(sample_rows(start, until)))
    root = tmp_path / "runs"
    for _ in range(count):
        assert (
            main(
                [
                    "normalize",
                    "--input",
                    str(source),
                    "--from",
                    start,
                    "--until",
                    until,
                    "--output",
                    str(root),
                ]
            )
            == 0
        )
    return root


def rewrite_parquet(directory, rows):
    parquet = directory / "observations.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), parquet, compression="zstd")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["output_sha256"] = hashlib.sha256(parquet.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))


@pytest.mark.parametrize(
    "start,until,expected",
    [
        ("2026-06-01", "2026-07-01", 2880),
        ("2026-03-29", "2026-03-30", 92),
        ("2026-10-25", "2026-10-26", 100),
    ],
)
def test_complete_windows_and_daily_coverage(tmp_path, start, until, expected):
    report = build_report(completed_runs(tmp_path, start, until))
    assert report["status"] == "passed"
    assert report["windows"][0]["repeat_equal"] is True
    assert report["windows"][0]["expected_rows"] == expected
    assert sum(day["actual_rows"] for day in report["runs"][0]["daily_coverage"]) == expected
    assert all(all(run["checks"].values()) for run in report["runs"])


@pytest.mark.parametrize(
    "fault",
    ["duplicate", "missing", "order", "duration", "null", "infinite", "dimension", "outside"],
)
def test_audit_detects_bad_data_even_with_updated_parquet_checksum(tmp_path, fault):
    root = completed_runs(tmp_path)
    directory = sorted(root.iterdir())[0]
    rows = pq.read_table(directory / "observations.parquet").to_pylist()
    if fault == "duplicate":
        rows[10] = rows[9].copy()
    elif fault == "missing":
        rows.pop(10)
    elif fault == "order":
        rows[9], rows[10] = rows[10], rows[9]
    elif fault == "duration":
        rows[10]["interval_end"] += STEP
    elif fault == "null":
        rows[10]["value"] = None
    elif fault == "infinite":
        rows[10]["value"] = float("inf")
    elif fault == "dimension":
        rows[10]["unit"] = "MW"
    else:
        rows[10]["interval_start"] = rows[-1]["interval_end"]
    rewrite_parquet(directory, rows)
    report = build_report(root)
    assert report["status"] == "failed"
    changed = next(run for run in report["runs"] if run["run_dir"] == str(directory))
    assert changed["checks"]["parquet_checksum"] is True
    assert changed["status"] == "failed"


def test_missing_repeat_does_not_pass(tmp_path):
    report = build_report(completed_runs(tmp_path, count=1))
    assert report["status"] == "failed"
    assert report["windows"][0]["repeat_equal"] is False


def test_copying_same_run_does_not_count_as_replay(tmp_path):
    root = completed_runs(tmp_path, count=1)
    shutil.copytree(next(root.iterdir()), root / "copied-run")
    assert build_report(root)["status"] == "failed"


def test_different_valid_values_fail_replay(tmp_path):
    root = completed_runs(tmp_path)
    directory = next(root.iterdir())
    rows = pq.read_table(directory / "observations.parquet").to_pylist()
    rows[0]["value"] += 1
    rewrite_parquet(directory, rows)
    report = build_report(root)
    assert all(run["status"] == "passed" for run in report["runs"])
    assert report["status"] == "failed"
    assert report["windows"][0]["repeat_equal"] is False


@pytest.mark.parametrize("fault", ["checksum", "metadata", "schema", "missing_artifact"])
def test_corrupt_artifacts_are_reported_not_silently_skipped(tmp_path, fault):
    root = completed_runs(tmp_path)
    directory = next(root.iterdir())
    if fault == "checksum":
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["output_sha256"] = "0" * 64
        (directory / "manifest.json").write_text(json.dumps(manifest))
    elif fault == "metadata":
        (directory / "manifest.json").write_text("[]")
    elif fault == "schema":
        pq.write_table(pa.table({"different": [1]}), directory / "observations.parquet")
    else:
        (directory / "quality.json").unlink()
    assert build_report(root)["status"] == "failed"


def test_cli_publishes_reports_without_overwrite(tmp_path, capsys):
    root = completed_runs(tmp_path)
    output = tmp_path / "reports"
    args = ["audit", "--runs-root", str(root), "--output", str(output)]
    assert main(args) == 0
    first = next(output.iterdir())
    original = (first / "report.json").read_bytes()
    assert main(args) == 0
    assert (first / "report.json").read_bytes() == original
    assert len(list(output.iterdir())) == 2
    assert "CC BY 4.0" in (first / "report.md").read_text()
    assert '"status": "passed"' in capsys.readouterr().out


def test_cli_failed_audit_retains_report_and_returns_nonzero(tmp_path):
    root = completed_runs(tmp_path, count=1)
    output = tmp_path / "reports"
    assert main(["audit", "--runs-root", str(root), "--output", str(output)]) == 1
    assert json.loads(next(output.glob("*/report.json")).read_text())["status"] == "failed"


def test_empty_root_and_incomplete_runs_fail(tmp_path):
    with pytest.raises(ValidationError, match="no completed"):
        build_report(tmp_path)
    (tmp_path / "incomplete").mkdir()
    report = build_report(tmp_path)
    assert report["status"] == "failed"
    assert len(report["errors"]) == 1


def test_hidden_partial_directory_is_not_a_completed_run(tmp_path):
    root = completed_runs(tmp_path)
    (root / ".pending-test").mkdir()
    assert build_report(root)["status"] == "passed"
