from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

DAGSTER_DIR = Path(__file__).resolve().parent.parent / "dagster"
if str(DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(DAGSTER_DIR))

from assets import _governed_asset_metadata, _metadata_row_count  # noqa: E402
from definitions import defs  # noqa: E402

from dagster import DefaultSensorStatus  # noqa: E402
from governance.contracts import governed_pipeline_asset_keys, load_contracts  # noqa: E402


def test_metadata_row_count_coerces_supported_values() -> None:
    assert _metadata_row_count({"row_count": 12}) == 12
    assert _metadata_row_count({"row_count": "7"}) == 7
    assert _metadata_row_count({}) == 0


def test_lineage_evidence_sensor_defaults_to_running() -> None:
    sensor_def = defs.get_sensor_def("lineage_evidence_sensor")
    assert sensor_def.default_status == DefaultSensorStatus.RUNNING


def test_governed_asset_metadata_adds_current_snapshot_id(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = object()
    monkeypatch.setattr(
        "assets.iceberg_io.current_snapshot_id",
        lambda _catalog, namespace, table: f"{namespace}.{table}:1001",
    )

    metadata = _governed_asset_metadata(
        catalog,
        "ecb_german_equity_proxy_features",
        {"table": "iceberg:gold.ecb_german_equity_proxy_features"},
    )

    assert metadata["iceberg_snapshot_id"] == "gold.ecb_german_equity_proxy_features:1001"
    assert metadata["table"] == "iceberg:gold.ecb_german_equity_proxy_features"


def test_definitions_register_all_governed_pipeline_assets() -> None:
    asset_keys = {
        ".".join(asset.key.path)
        for asset in defs.assets
        if hasattr(asset, "key")
    }
    expected = set(governed_pipeline_asset_keys(load_contracts()))

    assert expected.issubset(asset_keys)


def test_emit_pending_lineage_evidence_for_run_emits_pending_datasets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from governance.emission import (
        PendingLineageEvidenceRunResult,
        emit_pending_lineage_evidence_for_run,
    )

    class _Adapter:
        def get_successful_run_materializations(
            self,
            run_id: str,
        ) -> tuple[tuple[str, ...], datetime]:
            assert run_id == "run-1"
            return ("ecb_german_equity_proxy_features",), datetime(2026, 7, 30, tzinfo=UTC)

    monkeypatch.setattr(
        "governance.emission.audit_manifest_exists",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "governance.emission.emit_lineage_evidence",
        lambda dataset_id, run_id, **kwargs: (
            SimpleNamespace(record_sha256="abc123"),
            f"lineage/{dataset_id}/2026-07-30/{run_id}/manifest.json",
        ),
    )

    result = emit_pending_lineage_evidence_for_run(
        "run-1",
        environ={"DAGSTER_URL": "http://dagster:3000"},
        dagster_adapter=_Adapter(),
        contracts=load_contracts(),
    )

    assert isinstance(result, PendingLineageEvidenceRunResult)
    assert result.skip_reason is None
    assert len(result.emissions) == 1
    assert result.emissions[0].dataset_id == "fin.ecb_german_equity_proxy_features_gold"
