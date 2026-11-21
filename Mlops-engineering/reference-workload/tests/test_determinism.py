"""Acceptance check 1: the same seed and config regenerate byte-identical data."""

from __future__ import annotations

from charging_forecast.contract import load_config, sha256_file
from charging_forecast.generator import ChargingGenerator
from conftest import write_config


def test_same_seed_and_config_produce_identical_bytes(tmp_path):
    config_a = write_config(tmp_path / "a.yaml")
    config_b = write_config(tmp_path / "b.yaml")

    out_a, out_b = tmp_path / "release_a", tmp_path / "release_b"
    ChargingGenerator(load_config(config_a)).generate(out_a)
    ChargingGenerator(load_config(config_b)).generate(out_b)

    files_a = sorted(p.relative_to(out_a).as_posix() for p in out_a.rglob("*.parquet"))
    files_b = sorted(p.relative_to(out_b).as_posix() for p in out_b.rglob("*.parquet"))
    assert files_a == files_b and files_a, "both runs must write the same partitions"

    for rel in files_a:
        assert sha256_file(out_a / rel) == sha256_file(out_b / rel), rel


def test_different_seed_changes_output(tmp_path):
    config_a = write_config(tmp_path / "a.yaml")
    config_b = write_config(tmp_path / "b.yaml", overrides={"seed": 8})

    out_a, out_b = tmp_path / "release_a", tmp_path / "release_b"
    ChargingGenerator(load_config(config_a)).generate(out_a)
    ChargingGenerator(load_config(config_b)).generate(out_b)

    rel = "data/demand/year=2025/part-0000.parquet"
    assert sha256_file(out_a / rel) != sha256_file(out_b / rel)
