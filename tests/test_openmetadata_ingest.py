from __future__ import annotations

import base64
import json
import time
from unittest.mock import patch

import pytest

from governance.openmetadata_auth import (
    OpenMetadataAuthError,
    login_access_token,
    resolve_bearer_token,
    token_is_usable,
)
from governance.openmetadata_ingest import (
    build_trino_ingest_yaml,
    load_ingest_config_dict,
    run_trino_metadata_ingest,
    sync_enabled,
)


def _jwt(exp_offset_seconds: int) -> str:
    payload = {
        "exp": int(time.time()) + exp_offset_seconds,
        "sub": "admin",
    }
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


def test_token_is_usable_rejects_expired_token() -> None:
    assert not token_is_usable(_jwt(-120))


def test_token_is_usable_accepts_fresh_token() -> None:
    assert token_is_usable(_jwt(3600))


def test_resolve_bearer_token_uses_existing_token() -> None:
    token = _jwt(3600)
    assert resolve_bearer_token({"OPENMETADATA_AUTH_TOKEN": token}) == token


def test_resolve_bearer_token_requires_password_when_token_missing() -> None:
    with pytest.raises(OpenMetadataAuthError, match="OPENMETADATA_ADMIN_PASSWORD"):
        resolve_bearer_token({})


@patch("governance.openmetadata_auth.request.urlopen")
def test_login_access_token_returns_access_token(mock_urlopen) -> None:
    mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
        {"accessToken": "fresh-token"}
    ).encode()

    token = login_access_token(
        base_url="http://localhost:8585",
        email="admin@open-metadata.org",
        password="admin",
    )

    assert token == "fresh-token"


def test_sync_enabled_defaults_true() -> None:
    assert sync_enabled({})


def test_build_trino_ingest_yaml_contains_service_and_trino_host() -> None:
    yaml_text = build_trino_ingest_yaml(
        {
            "OPENMETADATA_TRINO_SERVICE_NAME": "sololakehouse-trino",
            "TRINO_USER": "sololakehouse",
            "OPENMETADATA_INGEST_API_URL": "http://openmetadata-server:8585/api",
        },
        "token-123",
    )
    assert "serviceName: sololakehouse-trino" in yaml_text
    assert "hostPort: trino:8080" in yaml_text
    assert "jwtToken: \"token-123\"" in yaml_text


def test_load_ingest_config_dict_parses_yaml() -> None:
    config = load_ingest_config_dict(
        {"OPENMETADATA_TRINO_SERVICE_NAME": "sololakehouse-trino"},
        "token-123",
    )
    assert config["source"]["serviceName"] == "sololakehouse-trino"


def test_run_trino_metadata_ingest_skips_when_disabled() -> None:
    result = run_trino_metadata_ingest({"OPENMETADATA_SYNC_ENABLED": "0"})
    assert result == {
        "status": "skipped",
        "reason": "OPENMETADATA_SYNC_ENABLED is off",
    }


@patch("governance.openmetadata_ingest._run_docker_ingest")
@patch("governance.openmetadata_ingest.resolve_bearer_token", return_value="token-123")
def test_run_trino_metadata_ingest_runs_docker_mode(mock_token, mock_docker) -> None:
    mock_docker.return_value = {"mode": "docker", "network": "sololakehouse_default"}
    result = run_trino_metadata_ingest(
        {
            "OPENMETADATA_SYNC_ENABLED": "1",
            "OPENMETADATA_TRINO_SERVICE_NAME": "sololakehouse-trino",
        }
    )
    assert result["status"] == "ok"
    assert result["mode"] == "docker"
    mock_docker.assert_called_once()
