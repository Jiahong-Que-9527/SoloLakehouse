"""Resolve OpenMetadata bearer tokens for automation without committing secrets."""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Mapping
from typing import Any
from urllib import error, request


class OpenMetadataAuthError(RuntimeError):
    """OpenMetadata authentication could not be completed."""


def _jwt_expiry_epoch(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get("exp")
        return int(exp) if exp is not None else None
    except (IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None


def token_is_usable(token: str, *, skew_seconds: int = 120) -> bool:
    """Return whether a JWT is present and not imminently expired."""
    if not token.strip():
        return False
    exp = _jwt_expiry_epoch(token)
    if exp is None:
        return False
    return exp > int(time.time()) + skew_seconds


def login_access_token(
    *,
    base_url: str,
    email: str,
    password: str,
    timeout_seconds: float = 15,
) -> str:
    """Exchange Basic-auth credentials for a short-lived OM access token."""
    encoded_password = base64.b64encode(password.encode("utf-8")).decode("ascii")
    body = json.dumps({"email": email, "password": encoded_password}).encode("utf-8")
    url = f"{base_url.rstrip('/')}/api/v1/users/login"
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise OpenMetadataAuthError(f"login failed ({exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise OpenMetadataAuthError(f"login request failed: {exc}") from exc

    token = payload.get("accessToken")
    if not isinstance(token, str) or not token:
        raise OpenMetadataAuthError("login response did not include accessToken")
    return token


def resolve_bearer_token(environ: Mapping[str, str] | None = None) -> str:
    """Return a usable bearer token from env or a fresh admin login."""
    env = os.environ if environ is None else environ
    existing = env.get("OPENMETADATA_AUTH_TOKEN", "").strip()
    if token_is_usable(existing):
        return existing

    principal = env.get("OPENMETADATA_ADMIN_PRINCIPAL", "admin").strip() or "admin"
    email = env.get("OPENMETADATA_ADMIN_EMAIL", f"{principal}@open-metadata.org")
    password = env.get("OPENMETADATA_ADMIN_PASSWORD")
    if not password:
        raise OpenMetadataAuthError(
            "OPENMETADATA_AUTH_TOKEN is missing or expired and "
            "OPENMETADATA_ADMIN_PASSWORD is not set for refresh"
        )

    base_url = env.get("OPENMETADATA_URL", "http://localhost:8585")
    return login_access_token(base_url=base_url, email=email, password=password)
