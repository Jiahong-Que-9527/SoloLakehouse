from __future__ import annotations

import pytest

from ingestion.catalog_boundary import (
    CatalogConnectionSettings,
    build_catalog,
    get_catalog_from_settings,
    load_catalog_settings,
)


def test_load_catalog_settings_defaults_to_hive() -> None:
    settings = load_catalog_settings(
        {
            "MINIO_ENDPOINT": "localhost:9000",
            "S3_ACCESS_KEY": "key",
            "S3_SECRET_KEY": "secret",
        }
    )

    assert settings.backend == "hive"
    assert settings.catalog_name == "hive"
    assert settings.hive_metastore_uri == "thrift://localhost:9083"
    assert settings.warehouse_uri == "s3://sololakehouse/warehouse/"


def test_rest_backend_requires_rest_uri() -> None:
    with pytest.raises(ValueError, match="ICEBERG_REST_URI is required"):
        load_catalog_settings({"ICEBERG_CATALOG_BACKEND": "rest"})


def test_build_catalog_rest_backend_fails_loudly() -> None:
    settings = CatalogConnectionSettings(
        backend="rest",
        catalog_name="rest",
        hive_metastore_uri="thrift://unused:9083",
        warehouse_uri="s3://sololakehouse/warehouse/",
        s3_endpoint="http://localhost:9000",
        s3_access_key="key",
        s3_secret_key="secret",
        rest_uri="http://localhost:8181",
    )

    with pytest.raises(NotImplementedError, match="REST catalog wiring"):
        build_catalog(settings)


def test_get_catalog_from_settings_applies_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _HiveCatalog:
        def __init__(self, name: str, **props: object) -> None:
            captured["name"] = name
            captured["props"] = props

    monkeypatch.setattr("pyiceberg.catalog.hive.HiveCatalog", _HiveCatalog)

    settings = load_catalog_settings({"S3_ACCESS_KEY": "key", "S3_SECRET_KEY": "secret"})
    get_catalog_from_settings(settings, uri="thrift://override:9083", name="custom")

    assert captured["name"] == "custom"
    assert captured["props"]["uri"] == "thrift://override:9083"
