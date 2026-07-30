from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import psycopg2
import pytest


def _load_bootstrap_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-postgres.py"
    spec = importlib.util.spec_from_file_location("bootstrap_postgres", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connect_tcp_retries_a_transient_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_bootstrap_module()
    connection = MagicMock()
    attempts = iter([psycopg2.OperationalError("starting"), connection])

    def connect(**_: object) -> object:
        result = next(attempts)
        if isinstance(result, psycopg2.OperationalError):
            raise result
        return result

    monkeypatch.setattr(module.psycopg2, "connect", connect)
    sleeps: list[int] = []
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    assert module.connect_tcp(user="postgres", password="postgres", attempts=2) is connection
    assert sleeps == [1]


def test_connect_tcp_raises_after_bounded_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_bootstrap_module()
    monkeypatch.setattr(
        module.psycopg2,
        "connect",
        lambda **_: (_ for _ in ()).throw(psycopg2.OperationalError("starting")),
    )
    sleeps: list[int] = []
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    with pytest.raises(psycopg2.OperationalError):
        module.connect_tcp(user="postgres", password="postgres", attempts=3)
    assert sleeps == [1, 1]
