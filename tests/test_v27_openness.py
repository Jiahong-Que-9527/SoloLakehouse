from __future__ import annotations

from datetime import UTC, datetime

import pytest

from governance.interoperability import (
    CatalogBackendBinding,
    build_catalog_interoperability_proof,
    count_rest_namespaces,
)
from governance.sovereignty import build_sovereignty_report, render_sovereignty_markdown
from ingestion.catalog_boundary import (
    CatalogConnectionSettings,
    build_catalog,
    load_catalog_settings,
)


def test_build_catalog_interoperability_proof_binds_shared_warehouse() -> None:
    hive = CatalogBackendBinding(
        backend="hive",
        catalog_name="hive",
        connection_uri="thrift://localhost:9083",
        warehouse_uri="s3://sololakehouse/warehouse/",
        s3_endpoint="http://localhost:9000",
    )
    rest = CatalogBackendBinding(
        backend="rest",
        catalog_name="polaris",
        connection_uri="http://localhost:8181/api/catalog",
        warehouse_uri="s3://sololakehouse/warehouse/",
        s3_endpoint="http://localhost:9000",
    )

    proof = build_catalog_interoperability_proof(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        hive_binding=hive,
        rest_binding=rest,
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )

    assert proof.proof_sha256 == proof.compute_digest(
        {
            "schema_version": proof.schema_version,
            "product_id": proof.product_id,
            "runtime_version": proof.runtime_version,
            "environment": proof.environment,
            "shared_warehouse_uri": proof.shared_warehouse_uri,
            "shared_s3_endpoint": proof.shared_s3_endpoint,
            "backends": [binding.model_dump(mode="json") for binding in proof.backends],
            "live_rest_namespace_count": proof.live_rest_namespace_count,
            "generated_at": proof.generated_at.isoformat(),
        }
    )


def test_interoperability_proof_rejects_mismatched_warehouse() -> None:
    hive = CatalogBackendBinding(
        backend="hive",
        catalog_name="hive",
        connection_uri="thrift://localhost:9083",
        warehouse_uri="s3://sololakehouse/warehouse/",
        s3_endpoint="http://localhost:9000",
    )
    rest = CatalogBackendBinding(
        backend="rest",
        catalog_name="polaris",
        connection_uri="http://localhost:8181/api/catalog",
        warehouse_uri="s3://other/warehouse/",
        s3_endpoint="http://localhost:9000",
    )

    with pytest.raises(ValueError, match="same warehouse_uri"):
        build_catalog_interoperability_proof(
            product_id="sololakehouse",
            runtime_version="slh-v2.6.1",
            environment="local",
            hive_binding=hive,
            rest_binding=rest,
        )


def test_count_rest_namespaces_uses_catalog_list() -> None:
    class _Catalog:
        def list_namespaces(self) -> list[tuple[str]]:
            return [("bronze",), ("silver",), ("gold",)]

    assert count_rest_namespaces(_Catalog()) == 3


def test_build_rest_catalog_uses_rest_uri_and_s3_props(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _RestCatalog:
        def __init__(self, name: str, **props: str) -> None:
            captured["name"] = name
            captured["props"] = props

    monkeypatch.setattr("pyiceberg.catalog.rest.RestCatalog", _RestCatalog)

    settings = CatalogConnectionSettings(
        backend="rest",
        catalog_name="polaris",
        hive_metastore_uri="thrift://unused:9083",
        warehouse_uri="s3://sololakehouse/warehouse/",
        s3_endpoint="http://localhost:9000",
        s3_access_key="key",
        s3_secret_key="secret",
        rest_uri="http://localhost:8181/api/catalog",
        rest_credential="root:secret",
    )
    build_catalog(settings)

    assert captured["name"] == "polaris"
    props = captured["props"]
    assert isinstance(props, dict)
    assert props["uri"] == "http://localhost:8181/api/catalog"
    assert props["warehouse"] == "s3://sololakehouse/warehouse/"
    assert props["credential"] == "root:secret"


def test_sovereignty_report_from_repository_root() -> None:
    from pathlib import Path

    report = build_sovereignty_report(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        repository_root=Path(__file__).resolve().parents[1],
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    names = {component.name for component in report.components}
    assert "minio" in names
    assert "trino" in names
    assert "pyiceberg" in names
    markdown = render_sovereignty_markdown(report)
    assert "SoloLakehouse Sovereignty Report" in markdown
    assert report.report_sha256 in markdown


def test_load_catalog_settings_includes_rest_auth_fields() -> None:
    settings = load_catalog_settings(
        {
            "ICEBERG_CATALOG_BACKEND": "rest",
            "ICEBERG_REST_URI": "http://localhost:8181/api/catalog",
            "ICEBERG_REST_CREDENTIAL": "root:secret",
            "ICEBERG_REST_OAUTH2_URI": "http://localhost:8181/api/catalog/v1/oauth/tokens",
            "ICEBERG_REST_SCOPE": "PRINCIPAL_ROLE:ALL",
            "S3_ACCESS_KEY": "key",
            "S3_SECRET_KEY": "secret",
        }
    )
    assert settings.rest_credential == "root:secret"
    assert settings.rest_oauth2_uri == "http://localhost:8181/api/catalog/v1/oauth/tokens"
    assert settings.rest_scope == "PRINCIPAL_ROLE:ALL"
