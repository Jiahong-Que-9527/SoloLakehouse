"""CLI wiring for publish-cloud: argument surface and pre-cloud validation."""

import pytest

from energy_pipeline.cli import main


def publish_args(**overrides):
    args = [
        "publish-cloud",
        "--mode",
        "sample",
        "--from",
        "2026-06-08",
        "--until",
        "2026-06-15",
        "--bucket",
        "some-bucket",
        "--project",
        "some-project",
    ]
    for key, value in overrides.items():
        flag = "--" + key.replace("_", "-")
        if value is None:
            index = args.index(flag)
            del args[index : index + 2]
        else:
            args[args.index(flag) + 1] = value
    return args


def test_unknown_sample_window_fails_before_any_cloud_access(capsys):
    args = publish_args(**{"from": "2030-01-01", "until": "2030-01-02"})
    assert main(args) == 1
    assert "no packaged sample" in capsys.readouterr().err


def test_bucket_is_required():
    with pytest.raises(SystemExit) as exit_code:
        main(publish_args(bucket=None))
    assert exit_code.value.code == 2


def test_mode_accepts_sample_only():
    with pytest.raises(SystemExit) as exit_code:
        main(publish_args(mode="live"))
    assert exit_code.value.code == 2
