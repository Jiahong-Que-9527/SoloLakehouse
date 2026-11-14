from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from opensky_ingest.config import Config, load_config

STATE_VECTOR_COLUMNS = [
    ("time", "integer"),
    ("icao24", "varchar"),
    ("lat", "double"),
    ("lon", "double"),
    ("velocity", "double"),
    ("heading", "double"),
    ("vertrate", "double"),
    ("callsign", "varchar"),
    ("onground", "boolean"),
    ("alert", "boolean"),
    ("spi", "boolean"),
    ("squawk", "varchar"),
    ("baroaltitude", "double"),
    ("geoaltitude", "double"),
    ("lastposupdate", "double"),
    ("lastcontact", "double"),
    ("serials", "array(integer)"),
    ("hour", "integer"),
]
FLIGHT_COLUMNS = [
    (name, "varchar")
    for name in (
        "icao24 firstseen estdepartureairport lastseen estarrivalairport callsign track "
        "estdepartureairporthorizdistance estdepartureairportvertdistance "
        "estarrivalairporthorizdistance estarrivalairportvertdistance "
        "departureairportcandidatescount arrivalairportcandidatescount "
        "otherdepartureairportcandidates otherarrivalairportcandidates day"
    ).split()
]


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self.description: list[tuple] | None = None
        self.stats: dict[str, Any] = {"processedBytes": 700_000_000}
        self.query_id = "q-1"
        self._rows: list[tuple] = []
        self.cancelled = False

    def execute(self, sql: str) -> None:
        self._connection.queries.append(sql)
        self.description, self._rows = self._connection.handle(sql)

    def __iter__(self):
        return iter(self._rows)

    def cancel(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        pass


class FakeConnection:
    """Answers the discovery queries. `empty_hours` are hour epochs without rows."""

    def __init__(self, empty_hours: set[int] | None = None, tables: list[str] | None = None):
        self.queries: list[str] = []
        self.empty_hours = empty_hours or set()
        self.tables = tables or ["state_vectors_data4", "flights_data4", "other"]
        self.columns = list(STATE_VECTOR_COLUMNS)

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        pass

    def handle(self, sql: str):
        if sql.startswith("SHOW TABLES"):
            return [("Table",)], [(t,) for t in self.tables]
        if sql.startswith("DESCRIBE") and "state_vectors_data4" in sql:
            return [("Column",)], [(n, t, "", "") for n, t in self.columns]
        if sql.startswith("DESCRIBE"):
            return [("Column",)], [(n, t, "", "") for n, t in FLIGHT_COLUMNS]
        if sql.startswith("SELECT 1 FROM"):
            hour = int(sql.split("hour = ")[1].split()[0])
            return [("_col0",)], ([] if hour in self.empty_hours else [(1,)])
        if "count(DISTINCT icao24)" in sql:
            return [("c",)], [(250_000, 400, 90_000, 1_700_000_000, 1_700_003_599)]
        if "FROM minio.osky.flights_data4" in sql:
            return [("c",)], [(1300, 650, 650)]
        raise AssertionError(f"unexpected query: {sql}")


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("SLH_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SLH_BACKUP_ROOT", str(tmp_path / "backup"))
    monkeypatch.setenv("SLH_TOKEN_DIR", str(tmp_path / "token"))
    monkeypatch.setenv("OPENSKY_USERNAME", "Tester")
    return load_config()
