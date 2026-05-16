"""Storage configuration helpers for SoloLakehouse-derived product entities."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Mapping

DEFAULT_DATA_BUCKET = "sololakehouse"
DEFAULT_WAREHOUSE_PREFIX = "warehouse"


@dataclass(frozen=True)
class StorageConfig:
    """Environment-driven object storage locations for the current runtime."""

    data_bucket: str
    warehouse_uri: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def get_storage_config(environ: Mapping[str, str] | None = None) -> StorageConfig:
    """Resolve storage locations from environment variables.

    `DATA_BUCKET` is the entity-level setting. `BUCKET_NAME` remains supported
    for v2.5 compatibility while existing deployments migrate.
    """
    env = os.environ if environ is None else environ
    data_bucket = _env(env, "DATA_BUCKET", _env(env, "BUCKET_NAME", DEFAULT_DATA_BUCKET))
    warehouse_uri = _env(env, "WAREHOUSE_URI", default_warehouse_uri(data_bucket))
    return StorageConfig(
        data_bucket=data_bucket,
        warehouse_uri=_ensure_trailing_slash(warehouse_uri),
    )


def get_data_bucket(environ: Mapping[str, str] | None = None) -> str:
    """Return the effective entity data bucket."""
    return get_storage_config(environ).data_bucket


def get_warehouse_uri(environ: Mapping[str, str] | None = None) -> str:
    """Return the effective Hive/Trino warehouse URI."""
    return get_storage_config(environ).warehouse_uri


def default_warehouse_uri(data_bucket: str) -> str:
    """Return the default warehouse URI for a data bucket."""
    return f"s3a://{data_bucket}/{DEFAULT_WAREHOUSE_PREFIX}/"


def _env(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name)
    if value is None:
        return default
    cleaned = _strip_optional_quotes(value.strip())
    return cleaned or default


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _ensure_trailing_slash(uri: str) -> str:
    return uri if uri.endswith("/") else f"{uri}/"
