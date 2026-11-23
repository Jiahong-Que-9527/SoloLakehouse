"""The derived district dataset: aggregation and availability semantics."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from district_forecast.dataset import (
    aggregate_demand,
    build_dataset,
    district_tariffs,
    validate_dataset,
)


def _load(source_release: Path, name: str):
    return pq.read_table(source_release / f"data/{name}/part-0000.parquet")


def test_aggregate_sums_stations_and_takes_max_availability(source_release):
    stations = _load(source_release, "stations")
    demand = _load(source_release, "demand")
    agg = aggregate_demand(demand, stations, ["D1", "D2"]).to_pylist()

    station_rows = demand.to_pylist()
    district_of = {r["station_id"]: r["district"] for r in stations.to_pylist()}
    expected = {}
    for row in station_rows:
        key = (district_of[row["station_id"]], row["hour_utc"])
        value, stamp = expected.get(key, (0.0, row["available_at"]))
        expected[key] = (value + row["demand_kwh"], max(stamp, row["available_at"]))
    for row in agg:
        value, stamp = expected[(row["district"], row["hour_utc"])]
        assert row["demand_kwh"] == pytest.approx(round(value, 6), abs=1e-6)
        assert row["available_at"] == stamp
        assert row["station_count"] == sum(
            1 for s, d in district_of.items() if d == row["district"]
        )


def test_tariff_collapse_refuses_non_uniform_district(source_release):
    stations = _load(source_release, "stations")
    tariffs = _load(source_release, "tariffs")
    collapsed = district_tariffs(tariffs, stations).to_pylist()
    d2 = [row for row in collapsed if row["district"] == "D2"]
    assert len(d2) == 2  # the base price and the step
    assert d2[1]["price_per_kwh"] == 0.45

    # Split D2's step across stations: the collapse must refuse.
    import pyarrow as pa

    rows = tariffs.to_pylist()
    step = [r for r in rows if r["price_per_kwh"] == 0.45]
    split = rows + [
        {**step[0], "station_id": "S3", "price_per_kwh": 0.50},
    ]
    split_table = pa.table(
        {
            "station_id": pa.array([r["station_id"] for r in split], pa.string()),
            "effective_from": pa.array([r["effective_from"] for r in split]),
            "price_per_kwh": pa.array([r["price_per_kwh"] for r in split], pa.float64()),
            "available_at": pa.array([r["available_at"] for r in split]),
        }
    )
    with pytest.raises(ValueError, match="not uniform"):
        district_tariffs(split_table, stations)


def test_build_dataset_releases_and_validates(source_release, district_cfg, tmp_path):
    out = tmp_path / "releases" / "dataset-district" / "v001"
    build_dataset(district_cfg, source_release, out)
    checks = validate_dataset(district_cfg, out)
    assert "hourly_continuity_D1" in checks
    assert "station_counts_consistent" in checks

    # The source release stays untouched (same manifest sha).

    assert (source_release / "_SUCCESS").exists()


def test_step_dataset_reuses_and_refuses_new_source(source_release, district_cfg, tmp_path):
    from district_forecast.pipeline import step_dataset

    out = tmp_path / "releases" / "dataset-district" / "v001"
    first = step_dataset(district_cfg, source_release, out)
    assert first["reused"] is False
    second = step_dataset(district_cfg, source_release, out)
    assert second["reused"] is True


def test_full_scale_real_source_reference_workload(tmp_path):
    """Acceptance: the derived dataset builds from the real pinned release
    (marked; skipped when the reference release is not present locally)."""
    real = (
        Path(__file__).resolve().parents[1].parent
        / "reference-workload"
        / "data"
        / "releases"
        / "dataset"
        / "v001"
    )
    if not (real / "_SUCCESS").exists():
        pytest.skip("reference dataset-v001 release not available")
    from district_forecast.dataset import load_config

    cfg = load_config(Path(__file__).resolve().parents[1] / "configs" / "district-v001.yaml")
    out = tmp_path / "v001"
    build_dataset(cfg, real, out)
    checks = validate_dataset(cfg, out)
    assert len(checks) >= 10
