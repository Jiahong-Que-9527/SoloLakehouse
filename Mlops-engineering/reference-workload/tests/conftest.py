"""Shared fixtures: a tiny frozen config and a generated release in tmp."""

from __future__ import annotations

import json

import pytest
import yaml

from charging_forecast.contract import build_manifest, git_commit, load_config
from charging_forecast.generator import ChargingGenerator

TINY_CONFIG: dict = {
    "release_id": "dataset-test",
    "schema_version": "charging-dataset-v1",
    "seed": 7,
    "window": {"start": "2025-03-01T00:00:00Z", "end": "2025-03-21T23:00:00Z"},
    "ingestion_delay_hours": 1,
    "forecast_issue_time": "06:00",
    "forecast_error_rho": 0.6,
    "forecast_temp_sigma_c": 1.2,
    "stations": {
        "count": 6,
        "districts": {"D1": 2, "D2": 2, "D3": 2},
        "poi_mix": {"office": 2, "retail": 2, "residential": 1, "highway": 1},
        "capacity_kw": {
            "office": [150, 350],
            "retail": [100, 250],
            "residential": [50, 150],
            "highway": [150, 350],
        },
        "active_from_default": "2025-01-01",
        "active_from_late": {},
    },
    "tariff": {
        "base_price_by_district": {"D1": 0.35, "D2": 0.33, "D3": 0.37},
        "step": {
            "date": "2025-03-10",
            "districts": ["D2"],
            "surcharge_eur_kwh": 0.15,
            "elasticity": -0.12,
            "ramp_days": 5,
        },
    },
    "heatwave": {"start": "2026-07-14", "end": "2026-07-20", "temp_offset_c": [8.0, 12.0]},
    "anomaly_mode": False,
}


def write_config(path, overrides: dict | None = None):
    import copy

    cfg = copy.deepcopy(TINY_CONFIG)
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def publish_manifest(release, cfg) -> None:
    """Write the release manifest (the FeatureBuilder's consumption gate)."""
    manifest = build_manifest(release, cfg, git_commit(release))
    (release / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@pytest.fixture()
def tiny_release(tmp_path):
    config_path = write_config(tmp_path / "config.yaml")
    cfg = load_config(config_path)
    out = tmp_path / "release"
    ChargingGenerator(cfg).generate(out)
    publish_manifest(out, cfg)
    return out, cfg
