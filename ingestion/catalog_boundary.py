"""Iceberg catalog backend selection for v2.7 openness work."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Literal, Mapping

from pyiceberg.catalog import Catalog

CatalogBackend = Literal["hive", "rest"]
_SUPPORTED_BACKENDS: frozenset[str] = frozenset({"hive", "rest"})


@dataclass(frozen=True)
class CatalogConnectionSettings:
    """Environment-driven connection settings for one Iceberg catalog backend."""

    backend: CatalogBackend
    catalog_name: str
    hive_metastore_uri: str
    warehouse_uri: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    rest_uri: str | None = None
    rest_credential: str | None = None
    rest_oauth2_uri: str | None = None
    rest_scope: str | None = None


def _normalize_warehouse_uri(raw_warehouse: str) -> str:
    return raw_warehouse.replace("s3a://", "s3://")


def load_catalog_settings(environ: Mapping[str, str] | None = None) -> CatalogConnectionSettings:
    """Load catalog settings from environment variables with v2.5 defaults."""
    env = os.environ if environ is None else environ
    backend = env.get("ICEBERG_CATALOG_BACKEND", "hive").strip().lower()
    if backend not in _SUPPORTED_BACKENDS:
        raise ValueError(
            f"ICEBERG_CATALOG_BACKEND must be one of {sorted(_SUPPORTED_BACKENDS)!r}, "
            f"received {backend!r}"
        )

    minio_ep = env.get("MINIO_ENDPOINT", "localhost:9000")
    data_bucket = env.get("DATA_BUCKET", env.get("BUCKET_NAME", "sololakehouse"))
    raw_warehouse = env.get("WAREHOUSE_URI", f"s3://{data_bucket}/warehouse/")
    rest_uri = env.get("ICEBERG_REST_URI", "").strip() or None
    rest_credential = env.get("ICEBERG_REST_CREDENTIAL", "").strip() or None
    rest_oauth2_uri = env.get("ICEBERG_REST_OAUTH2_URI", "").strip() or None
    rest_scope = env.get("ICEBERG_REST_SCOPE", "").strip() or None
    if backend == "rest" and rest_uri is None:
        raise ValueError("ICEBERG_REST_URI is required when ICEBERG_CATALOG_BACKEND=rest")

    return CatalogConnectionSettings(
        backend=backend,  # type: ignore[arg-type]
        catalog_name=env.get("ICEBERG_CATALOG_NAME", "hive"),
        hive_metastore_uri=env.get("HIVE_METASTORE_URI", "thrift://localhost:9083"),
        warehouse_uri=_normalize_warehouse_uri(raw_warehouse),
        s3_endpoint=f"http://{minio_ep}" if "://" not in minio_ep else minio_ep,
        s3_access_key=env.get("S3_ACCESS_KEY", "sololakehouse"),
        s3_secret_key=env.get("S3_SECRET_KEY", "sololakehouse123"),
        rest_uri=rest_uri,
        rest_credential=rest_credential,
        rest_oauth2_uri=rest_oauth2_uri,
        rest_scope=rest_scope,
    )


def build_catalog(settings: CatalogConnectionSettings) -> Catalog:
    """Construct a pyiceberg catalog for the selected backend."""
    if settings.backend == "hive":
        return _build_hive_catalog(settings)
    return _build_rest_catalog(settings)


def _build_hive_catalog(settings: CatalogConnectionSettings) -> Catalog:
    from pyiceberg.catalog.hive import HiveCatalog

    props = {
        "uri": settings.hive_metastore_uri,
        "warehouse": settings.warehouse_uri,
        "s3.endpoint": settings.s3_endpoint,
        "s3.access-key-id": settings.s3_access_key,
        "s3.secret-access-key": settings.s3_secret_key,
        "s3.path-style-access": "true",
    }
    return HiveCatalog(settings.catalog_name, **props)


def _build_rest_catalog(settings: CatalogConnectionSettings) -> Catalog:
    from pyiceberg.catalog.rest import RestCatalog

    if settings.rest_uri is None:
        raise ValueError("rest_uri is required for REST catalog construction")

    props = {
        "uri": settings.rest_uri,
        "warehouse": settings.warehouse_uri,
        "s3.endpoint": settings.s3_endpoint,
        "s3.access-key-id": settings.s3_access_key,
        "s3.secret-access-key": settings.s3_secret_key,
        "s3.path-style-access": "true",
    }
    if settings.rest_credential is not None:
        props["credential"] = settings.rest_credential
    if settings.rest_oauth2_uri is not None:
        props["oauth2-server-uri"] = settings.rest_oauth2_uri
    if settings.rest_scope is not None:
        props["scope"] = settings.rest_scope
    return RestCatalog(settings.catalog_name, **props)


def get_catalog_from_settings(
    settings: CatalogConnectionSettings,
    *,
    name: str | None = None,
    uri: str | None = None,
    warehouse: str | None = None,
    s3_endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
) -> Catalog:
    """Apply optional overrides, then build the configured catalog backend."""
    effective = settings
    if name is not None:
        effective = replace(effective, catalog_name=name)
    if uri is not None:
        effective = replace(effective, hive_metastore_uri=uri)
    if warehouse is not None:
        effective = replace(effective, warehouse_uri=_normalize_warehouse_uri(warehouse))
    if s3_endpoint is not None:
        effective = replace(effective, s3_endpoint=s3_endpoint)
    if access_key is not None:
        effective = replace(effective, s3_access_key=access_key)
    if secret_key is not None:
        effective = replace(effective, s3_secret_key=secret_key)
    return build_catalog(effective)
