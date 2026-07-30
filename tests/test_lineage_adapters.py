from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from governance.contracts import DatasetContract
from governance.lineage import (
    DagsterRunAdapter,
    DagsterRunEvidence,
    EvidenceSourceError,
    IcebergSnapshotAdapter,
    IcebergSnapshotEvidence,
    LineageEvidenceJoiner,
    OpenMetadataAdapter,
    OpenMetadataEvidence,
)


def _contract() -> DatasetContract:
    return DatasetContract.model_validate(
        {
            "dataset_id": "fin.ecb_dax_features_gold",
            "owner": "data-platform",
            "business_purpose": "feature output",
            "refresh_sla": "daily",
            "quality_class": "demo_critical",
            "consumers": ["analytics"],
            "retention": "1 year",
            "classification": "internal",
            "source_of_truth": "iceberg",
            "approved_consumer_class": ["analyst"],
            "access_policy_hint": "read-only",
            "layer": "gold",
            "physical_location": {
                "catalog": "hive",
                "namespace": "gold",
                "table": "ecb_dax_features",
            },
            "dagster_asset_key": "gold_features",
            "upstream_dataset_ids": ["fin.ecb_rates_silver"],
            "quality_rules": {"required_columns": ["date"], "min_row_count": 1},
        }
    )


class _Response:
    def __init__(self, payload: object, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self) -> object:
        return self.payload


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self.response

    def post(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _openmetadata_evidence() -> OpenMetadataEvidence:
    return OpenMetadataEvidence(
        "fin.ecb_dax_features_gold",
        "finlakehouse-trino.gold.ecb_dax_features",
        ("data-platform",),
        ("Tier.Tier1",),
    )


def _iceberg_evidence() -> IcebergSnapshotEvidence:
    return IcebergSnapshotEvidence(
        "fin.ecb_dax_features_gold",
        "hive",
        "gold",
        "ecb_dax_features",
        "1001",
        "sololakehouse",
        "warehouse/gold/ecb_dax_features/metadata/v1.metadata.json",
    )


def _dagster_evidence() -> DagsterRunEvidence:
    return DagsterRunEvidence(
        "fin.ecb_dax_features_gold", "run-1", ("gold_features",), datetime(2026, 7, 30, tzinfo=UTC)
    )


def test_openmetadata_adapter_reads_exact_table_and_requires_owner() -> None:
    session = _Session(
        _Response(
            {
                "fullyQualifiedName": "finlakehouse-trino.gold.ecb_dax_features",
                "owners": [{"name": "data-platform"}],
                "tags": [{"tagFQN": "Tier.Tier1"}],
            }
        )
    )

    evidence = OpenMetadataAdapter(
        "http://openmetadata:8585", "finlakehouse-trino", session
    ).collect(_contract())

    assert evidence == _openmetadata_evidence()
    assert session.calls[0]["url"].endswith("finlakehouse-trino.gold.ecb_dax_features")


def test_openmetadata_adapter_fails_on_unowned_or_wrong_table() -> None:
    session = _Session(
        _Response({"fullyQualifiedName": "wrong.gold.ecb_dax_features", "owners": []})
    )

    with pytest.raises(EvidenceSourceError, match="expected table"):
        OpenMetadataAdapter("http://openmetadata:8585", "finlakehouse-trino", session).collect(
            _contract()
        )


def test_openmetadata_adapter_sends_configured_bearer_token() -> None:
    session = _Session(
        _Response(
            {
                "fullyQualifiedName": "finlakehouse-trino.gold.ecb_dax_features",
                "owners": [{"name": "data-platform"}],
                "tags": [{"tagFQN": "Tier.Tier1"}],
            }
        )
    )

    OpenMetadataAdapter(
        "http://openmetadata:8585", "finlakehouse-trino", session, auth_token="token-value"
    ).collect(_contract())

    assert session.calls[0]["headers"] == {"Authorization": "Bearer token-value"}


def test_iceberg_adapter_requires_current_snapshot_and_s3_metadata_location() -> None:
    table = SimpleNamespace(
        current_snapshot=lambda: SimpleNamespace(snapshot_id=1001),
        metadata_location="s3://sololakehouse/warehouse/gold/ecb_dax_features/metadata/v1.metadata.json",
    )
    catalog = SimpleNamespace(load_table=lambda identifier: table)

    assert IcebergSnapshotAdapter(catalog).collect(_contract()) == _iceberg_evidence()


def test_iceberg_adapter_fails_loudly_without_snapshot() -> None:
    table = SimpleNamespace(
        current_snapshot=lambda: None, metadata_location="s3://bucket/metadata.json"
    )
    catalog = SimpleNamespace(load_table=lambda identifier: table)

    with pytest.raises(EvidenceSourceError, match="no current snapshot"):
        IcebergSnapshotAdapter(catalog).collect(_contract())


def test_dagster_adapter_requires_successful_run_selecting_contract_asset() -> None:
    payload = {
        "data": {
            "runOrError": {
                "__typename": "Run",
                "runId": "run-1",
                "status": "SUCCESS",
                "startTime": 1785369600.0,
                "assetMaterializations": [{"assetKey": {"path": ["gold_features"]}}],
            }
        }
    }
    session = _Session(_Response(payload))

    evidence = DagsterRunAdapter("http://dagster:3000", session).collect(_contract(), "run-1")

    assert evidence.dataset_id == "fin.ecb_dax_features_gold"
    assert evidence.asset_keys == ("gold_features",)
    assert evidence.started_at.tzinfo is UTC


@pytest.mark.parametrize("source", ["openmetadata", "iceberg", "dagster"])
def test_joiner_fails_when_a_required_source_is_missing(source: str) -> None:
    evidence: dict[str, object | None] = {
        "openmetadata": _openmetadata_evidence(),
        "iceberg": _iceberg_evidence(),
        "dagster": _dagster_evidence(),
    }
    evidence[source] = None

    with pytest.raises(EvidenceSourceError, match="required source is missing"):
        LineageEvidenceJoiner("sololakehouse", "slh-v2.6", "local").join(
            _contract(),
            evidence["openmetadata"],  # type: ignore[arg-type]
            evidence["iceberg"],  # type: ignore[arg-type]
            evidence["dagster"],  # type: ignore[arg-type]
        )


def test_joiner_joins_exact_dataset_and_physical_evidence() -> None:
    record = LineageEvidenceJoiner("sololakehouse", "slh-v2.6", "local").join(
        _contract(), _openmetadata_evidence(), _iceberg_evidence(), _dagster_evidence()
    )

    assert record.dataset_id == "fin.ecb_dax_features_gold"
    assert record.openmetadata_table_fqn == "finlakehouse-trino.gold.ecb_dax_features"
    assert record.iceberg_snapshot_id == "1001"


def test_joiner_rejects_dataset_id_mismatch() -> None:
    wrong = OpenMetadataEvidence(
        "fin.other", "finlakehouse-trino.gold.ecb_dax_features", ("owner",), ()
    )

    with pytest.raises(EvidenceSourceError, match="dataset_id does not match"):
        LineageEvidenceJoiner("sololakehouse", "slh-v2.6", "local").join(
            _contract(), wrong, _iceberg_evidence(), _dagster_evidence()
        )
