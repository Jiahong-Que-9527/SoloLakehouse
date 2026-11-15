from __future__ import annotations

from datetime import UTC, datetime

import pytest

from opensky_ingest.config import ConfigError, load_config
from opensky_ingest.reference import (
    hour_epoch_label,
    hour_gap_status,
    load_epochs,
    load_gaps,
)


def test_default_config_values(cfg):
    assert cfg.period.hours == 17_520
    assert cfg.period.days == 730
    assert cfg.username == "tester"
    assert cfg.region.bbox.south < cfg.region.bbox.north
    assert cfg.flights.day_end > cfg.period.end


def test_missing_username(cfg, monkeypatch):
    monkeypatch.delenv("OPENSKY_USERNAME")
    with pytest.raises(ConfigError):
        _ = cfg.username


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_hour_probes_are_on_hour_boundaries(cfg):
    assert all(h.minute == 0 for h in cfg.discovery.hour_probes)


def test_gap_status():
    gaps = load_gaps()
    inside = datetime(2026, 1, 3, 12, tzinfo=UTC)
    edge = datetime(2026, 1, 2, 18, tzinfo=UTC)
    normal = datetime(2026, 3, 1, 12, tzinfo=UTC)
    assert hour_gap_status(gaps, inside) == "inside"
    assert hour_gap_status(gaps, edge) == "none"
    assert hour_gap_status(gaps, datetime(2026, 1, 2, 19, tzinfo=UTC)) == "inside"
    assert hour_gap_status(gaps, normal) == "none"


def test_epoch_labels():
    epochs = load_epochs()
    assert hour_epoch_label(epochs, datetime(2026, 8, 1, tzinfo=UTC)) == ("A", False)
    assert hour_epoch_label(epochs, datetime(2026, 8, 13, 12, tzinfo=UTC)) == ("A", True)
    assert hour_epoch_label(epochs, datetime(2026, 8, 13, 13, tzinfo=UTC)) == ("B", False)
    assert hour_epoch_label(epochs, datetime(2026, 8, 14, 8, tzinfo=UTC)) == ("B", True)
    assert hour_epoch_label(epochs, datetime(2026, 8, 14, 9, tzinfo=UTC)) == ("C", False)
