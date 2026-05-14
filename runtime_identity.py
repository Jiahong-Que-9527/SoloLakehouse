"""Runtime identity helpers for SoloLakehouse-derived product entities."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from typing import Mapping

DEFAULT_PRODUCT_ID = "sololakehouse"
DEFAULT_DISPLAY_NAME = "SoloLakehouse"
DEFAULT_DOMAIN = "financial_markets"
DEFAULT_ENVIRONMENT = "local"
DEFAULT_RUNTIME_VERSION = "slh-v2.5.1"


@dataclass(frozen=True)
class RuntimeIdentity:
    """Environment-driven identity for the current lakehouse runtime."""

    product_id: str
    display_name: str
    domain: str
    environment: str
    runtime_version: str
    compose_project_name: str
    trino_user: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def get_runtime_identity(environ: Mapping[str, str] | None = None) -> RuntimeIdentity:
    """Resolve product/runtime identity from environment variables.

    Defaults preserve the v2.5 SoloLakehouse local reference behavior.
    """
    env = os.environ if environ is None else environ
    product_id = _env(env, "PRODUCT_ID", DEFAULT_PRODUCT_ID).lower()
    display_name = _env(env, "PRODUCT_DISPLAY_NAME", _default_display_name(product_id))
    domain = _env(env, "PRODUCT_DOMAIN", DEFAULT_DOMAIN)
    environment = _env(env, "ENVIRONMENT", DEFAULT_ENVIRONMENT)
    runtime_version = _env(env, "RUNTIME_VERSION", DEFAULT_RUNTIME_VERSION)
    compose_project_name = _env(env, "COMPOSE_PROJECT_NAME", product_id)
    trino_user = _env(env, "TRINO_USER", _default_trino_user(product_id))
    return RuntimeIdentity(
        product_id=product_id,
        display_name=display_name,
        domain=domain,
        environment=environment,
        runtime_version=runtime_version,
        compose_project_name=compose_project_name,
        trino_user=trino_user,
    )


def get_trino_user(environ: Mapping[str, str] | None = None) -> str:
    """Return the effective Trino user for this runtime identity."""
    return get_runtime_identity(environ).trino_user


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


def _default_display_name(product_id: str) -> str:
    if product_id == DEFAULT_PRODUCT_ID:
        return DEFAULT_DISPLAY_NAME
    words = re.split(r"[-_]+", product_id)
    return " ".join(word.capitalize() for word in words if word) or DEFAULT_DISPLAY_NAME


def _default_trino_user(product_id: str) -> str:
    user = re.sub(r"[^a-zA-Z0-9_]", "_", product_id).strip("_").lower()
    return user or DEFAULT_PRODUCT_ID
