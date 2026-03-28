"""Integration checks for Trino Iceberg and optional OpenMetadata services."""

from __future__ import annotations

import pytest
import requests

pytestmark = pytest.mark.integration


def _trino_up() -> bool:
    try:
        r = requests.get("http://localhost:8080/v1/info", timeout=2)
        return r.status_code == 200 and not r.json().get("starting", True)
    except OSError:
        return False


def _openmetadata_up() -> bool:
    try:
        health = requests.get("http://localhost:8586/healthcheck", timeout=2)
        if health.status_code != 200:
            return False
        return bool(
            health.json().get("OpenMetadataServerHealthCheck", {}).get("healthy", False)
        )
    except OSError:
        return False


@pytest.mark.skipif(not _trino_up(), reason="Trino not reachable on localhost:8080")
def test_trino_lists_iceberg_catalog() -> None:
    headers = {"X-Trino-User": "test", "Content-Type": "text/plain; charset=utf-8"}
    r = requests.post(
        "http://localhost:8080/v1/statement",
        data=b"SHOW CATALOGS",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    chunks: list[str] = []
    while True:
        chunks.append(str(payload))
        if "error" in payload:
            pytest.fail(payload["error"].get("message", "trino error"))
        nxt = payload.get("nextUri")
        if not nxt:
            break
        n = requests.get(nxt, timeout=30)
        n.raise_for_status()
        payload = n.json()
    assert any("iceberg" in c.lower() for c in chunks)


@pytest.mark.skipif(not _openmetadata_up(), reason="OpenMetadata not reachable on localhost:8586")
def test_openmetadata_version_endpoint() -> None:
    r = requests.get("http://localhost:8585/api/v1/system/version", timeout=5)
    assert r.status_code == 200
