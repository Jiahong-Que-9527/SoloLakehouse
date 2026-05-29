"""Tests for the Trino SQL execution helper (mocked HTTP)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from ingestion.trino_sql import execute_trino_sql


def test_execute_trino_sql_polls_next_uri() -> None:
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"nextUri": "http://trino/next1", "stats": {"state": "RUNNING"}}

    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {"stats": {"state": "FINISHED"}}

    with patch("ingestion.trino_sql.requests.post", return_value=post_resp):
        with patch("ingestion.trino_sql.requests.get", return_value=get_resp):
            out = execute_trino_sql("http://localhost:8080", "SELECT 1")
    assert "stats" in out


def test_execute_trino_sql_uses_runtime_identity_user() -> None:
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"stats": {"state": "FINISHED"}}

    env = {**os.environ, "PRODUCT_ID": "aviation-lakehouse"}
    env.pop("TRINO_USER", None)
    with patch.dict(os.environ, env, clear=True):
        with patch("ingestion.trino_sql.requests.post", return_value=post_resp) as post_mock:
            execute_trino_sql("http://localhost:8080", "SELECT 1")

    assert post_mock.call_args.kwargs["headers"]["X-Trino-User"] == "aviation_lakehouse"


def test_execute_trino_sql_raises_on_error_payload() -> None:
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"error": {"message": "syntax error near 'FROM'"}}

    with patch("ingestion.trino_sql.requests.post", return_value=post_resp):
        try:
            execute_trino_sql("http://localhost:8080", "SELECT FROM")
        except ValueError as exc:
            assert "syntax error" in str(exc)
        else:
            raise AssertionError("Expected ValueError")
