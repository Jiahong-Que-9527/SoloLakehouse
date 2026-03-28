"""Tests for Trino SQL helpers (mocked HTTP)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ingestion.trino_sql import execute_trino_sql, register_gold_tables_trino


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


def test_register_gold_tables_trino_calls_sequence() -> None:
    calls: list[str] = []

    def fake_exec(url: str, sql: str, **_k) -> dict:
        calls.append(sql.strip())
        return {}

    with patch("ingestion.trino_sql.execute_trino_sql", side_effect=fake_exec):
        register_gold_tables_trino("http://localhost:8080", "sololakehouse")

    assert len(calls) >= 4
    assert any("CREATE SCHEMA" in c for c in calls)
    assert any("DROP TABLE IF EXISTS iceberg.gold.ecb_dax_features_iceberg" in c for c in calls)
