from __future__ import annotations

import json
import os
import stat

import pytest

from opensky_ingest import auth, cli
from opensky_ingest.discover import discover, save_record
from opensky_ingest.errors import EXIT_AUTH_REQUIRED, EXIT_ERROR, EXIT_OK, AuthRequired
from opensky_ingest.util import epoch

from .conftest import FakeConnection


def test_discover_ok(cfg):
    conn = FakeConnection()
    record = discover(conn, cfg, progress=lambda _m: None)
    assert record["window_available"] is True
    assert record["issues"] == []
    sv = record["schemas"]["state_vectors_data4"]
    assert sv["missing_expected"] == []
    assert sv["optional_present"] == ["serials"]
    assert len(record["rowcount_probes"]) == len(cfg.discovery.rowcount_probe_hours)
    assert record["row_estimates"]["mean_rows_per_hour"] == 250_000
    gap_probe = [p for p in record["hour_probes"] if p["known_gap"] == "inside"]
    assert gap_probe


def test_discover_reports_empty_hour_outside_gap(cfg):
    normal = next(h for h in cfg.discovery.hour_probes if h.year == 2024)
    conn = FakeConnection(empty_hours={epoch(normal)})
    record = discover(conn, cfg, progress=lambda _m: None)
    assert record["window_available"] is False
    assert any(i.startswith("HOUR_PARTITION_EMPTY") for i in record["issues"])


def test_discover_empty_hour_inside_gap_is_expected(cfg):
    gap_hour = next(h for h in cfg.discovery.hour_probes if h.year == 2026 and h.month == 1)
    conn = FakeConnection(empty_hours={epoch(gap_hour)})
    record = discover(conn, cfg, progress=lambda _m: None)
    assert record["window_available"] is True


def test_discover_detects_schema_drift(cfg):
    conn = FakeConnection()
    conn.columns = [c for c in conn.columns if c[0] != "squawk"]
    record = discover(conn, cfg, progress=lambda _m: None)
    assert record["window_available"] is False
    assert any(i.startswith("SCHEMA_DRIFT") for i in record["issues"])


def test_discover_queries_are_bounded_and_use_partition_filters(cfg):
    conn = FakeConnection()
    discover(conn, cfg, progress=lambda _m: None)
    for sql in conn.queries:
        if sql.startswith("SELECT"):
            assert "hour = " in sql or "day = " in sql


def test_record_written_atomically(cfg):
    record = discover(FakeConnection(), cfg, progress=lambda _m: None)
    path = save_record(cfg, record)
    assert path.parent.name == "schemas"
    assert json.loads(path.read_text())["window_available"] is True
    assert not list(path.parent.glob("*.tmp"))


def test_token_cache_roundtrip_and_permissions(tmp_path):
    cache = auth.DiskTokenCache(tmp_path / "tokens")
    assert cache.get_token_from_cache("k") is None
    cache.store_token_to_cache("k", "secret")
    assert cache.get_token_from_cache("k") == "secret"
    assert cache.get_token_from_cache("other") is None
    mode = stat.S_IMODE(os.stat(tmp_path / "tokens" / auth.TOKEN_FILE).st_mode)
    assert mode == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "tokens").st_mode) == 0o700


def test_noninteractive_handler_raises_without_leaking_url():
    handler = auth.noninteractive_redirect_handler()
    with pytest.raises(AuthRequired) as info:
        handler("https://login.example/secret-path")
    assert "secret-path" not in str(info.value)


def test_interactive_handler_stores_url_privately_and_prints_nothing_sensitive(tmp_path, capsys):
    opened = []
    handler = auth.interactive_redirect_handler(tmp_path, opener=lambda u: opened.append(u) or True)
    handler("https://login.example/secret-path")
    out = capsys.readouterr().out
    assert "secret-path" not in out
    assert opened == ["https://login.example/secret-path"]
    path = tmp_path / auth.LOGIN_URL_FILE
    assert path.read_text() == "https://login.example/secret-path"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_cli_discover_success(cfg, capsys):
    code = cli.main(["discover"], connection_factory=lambda _c, interactive: FakeConnection())
    assert code == EXIT_OK
    assert "Whole window available: yes" in capsys.readouterr().out


def test_cli_discover_exit_code_when_window_incomplete(cfg):
    conn = FakeConnection(tables=["flights_data4"])
    assert cli.main(["discover"], connection_factory=lambda _c, interactive: conn) == EXIT_ERROR


def test_cli_discover_auth_required_exit_code(cfg, capsys):
    def factory(_cfg, interactive):
        raise AuthRequired("AUTH_REQUIRED: renew the OpenSky session with `login`")

    assert cli.main(["discover"], connection_factory=factory) == EXIT_AUTH_REQUIRED
    assert "AUTH_REQUIRED" in capsys.readouterr().err


def test_cli_login_uses_interactive_connection(cfg, capsys):
    seen = {}

    def factory(_cfg, interactive):
        seen["interactive"] = interactive
        return FakeConnection()

    assert cli.main(["login"], connection_factory=factory) == EXIT_OK
    assert seen["interactive"] is True
    assert "authentication verified" in capsys.readouterr().out


def test_cli_missing_username(cfg, monkeypatch, capsys):
    monkeypatch.delenv("OPENSKY_USERNAME")
    code = cli.main(["discover"], connection_factory=lambda _c, interactive: FakeConnection())
    assert code == EXIT_ERROR
    assert "OPENSKY_USERNAME" in capsys.readouterr().err
