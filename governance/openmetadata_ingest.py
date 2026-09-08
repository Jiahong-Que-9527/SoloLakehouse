"""Trino metadata ingestion helpers for OpenMetadata automation."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from governance.openmetadata_auth import OpenMetadataAuthError, resolve_bearer_token

_INGEST_YAML_TEMPLATE = """\
source:
  type: trino
  serviceName: {service_name}
  serviceConnection:
    config:
      type: Trino
      hostPort: {trino_host_port}
      username: {trino_user}
      catalog: {trino_catalog}
      connectionArguments:
        http_scheme: http
  sourceConfig:
    config:
      type: DatabaseMetadata
      markDeletedTables: true
      includeTables: true
      includeViews: true
sink:
  type: metadata-rest
  config: {{}}
workflowConfig:
  loggerLevel: INFO
  openMetadataServerConfig:
    hostPort: {om_api_url}
    authProvider: openmetadata
    securityConfig:
      jwtToken: "{jwt_token}"
"""


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def sync_enabled(environ: Mapping[str, str]) -> bool:
    return _truthy(environ.get("OPENMETADATA_SYNC_ENABLED", "1"))


def build_trino_ingest_yaml(environ: Mapping[str, str], jwt_token: str) -> str:
    service_name = environ.get("OPENMETADATA_TRINO_SERVICE_NAME", "sololakehouse-trino")
    trino_user = environ.get("TRINO_USER", "sololakehouse")
    trino_catalog = environ.get("TRINO_CATALOG", "iceberg")
    trino_host_port = environ.get("OPENMETADATA_TRINO_HOST_PORT", "trino:8080")
    om_api_url = environ.get(
        "OPENMETADATA_INGEST_API_URL",
        "http://openmetadata-server:8585/api",
    )
    return _INGEST_YAML_TEMPLATE.format(
        service_name=service_name,
        trino_host_port=trino_host_port,
        trino_user=trino_user,
        trino_catalog=trino_catalog,
        om_api_url=om_api_url,
        jwt_token=jwt_token,
    )


def _docker_network(environ: Mapping[str, str]) -> str:
    explicit = environ.get("OPENMETADATA_DOCKER_NETWORK", "").strip()
    if explicit:
        return explicit
    project = environ.get("COMPOSE_PROJECT_NAME", "sololakehouse").strip() or "sololakehouse"
    return f"{project}_default"


def _run_docker_ingest(config_path: Path, environ: Mapping[str, str]) -> dict[str, Any]:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("docker CLI not found; run `make om-ingest-trino` on the host")

    image = environ.get(
        "OPENMETADATA_INGEST_IMAGE",
        "docker.getcollate.io/openmetadata/ingestion:1.5.6",
    )
    network = _docker_network(environ)
    command = [
        docker,
        "run",
        "--rm",
        f"--network={network}",
        "-v",
        f"{config_path}:/config.yaml:ro",
        "--entrypoint",
        "/home/airflow/.local/bin/metadata",
        image,
        "ingest",
        "-c",
        "/config.yaml",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=int(environ.get("OPENMETADATA_INGEST_TIMEOUT_SECONDS", "600")),
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-1200:]
        raise RuntimeError(f"metadata ingest failed (exit {completed.returncode}): {tail}")
    return {
        "mode": "docker",
        "network": network,
        "image": image,
        "log_tail": (completed.stdout or "").strip()[-500:],
    }


def run_trino_metadata_ingest(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run Trino metadata ingestion into OpenMetadata when enabled."""
    env = os.environ if environ is None else environ
    if not sync_enabled(env):
        return {
            "status": "skipped",
            "reason": "OPENMETADATA_SYNC_ENABLED is off",
        }

    try:
        jwt_token = resolve_bearer_token(env)
    except OpenMetadataAuthError as exc:
        return {"status": "skipped", "reason": str(exc)}

    yaml_text = build_trino_ingest_yaml(env, jwt_token)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_text)
        config_path = Path(handle.name)
    config_path.chmod(0o644)

    try:
        details = _run_docker_ingest(config_path, env)
    except RuntimeError as exc:
        return {"status": "skipped", "reason": str(exc)}
    finally:
        config_path.unlink(missing_ok=True)

    return {
        "status": "ok",
        "service_name": env.get("OPENMETADATA_TRINO_SERVICE_NAME", "sololakehouse-trino"),
        **details,
    }


def load_ingest_config_dict(environ: Mapping[str, str], jwt_token: str) -> dict[str, Any]:
    """Parse the generated ingestion YAML for tests and diagnostics."""
    return yaml.safe_load(build_trino_ingest_yaml(environ, jwt_token))
