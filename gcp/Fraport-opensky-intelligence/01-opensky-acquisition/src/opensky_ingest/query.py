"""SQL for one state-vector hour or one flight day.

The text and its hash are part of the contract.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from .config import Config, ConfigError
from .schema import FLIGHT_COLUMNS, STATE_VECTOR_COLUMNS
from .util import day_epoch, epoch


def _number(value: float) -> str:
    return format(value, ".10g")


def state_vector_sql(cfg: Config, hour: datetime) -> str:
    """One hour, no ORDER BY and no row limit. `serials` is not part of v1."""
    box = cfg.region.bbox
    columns = ", ".join(STATE_VECTOR_COLUMNS)
    table = cfg.source.table(cfg.state_vectors.table)
    return (
        f"SELECT {columns} FROM {table} "
        f"WHERE hour = {epoch(hour)} "
        f"AND lat BETWEEN {_number(box.south)} AND {_number(box.north)} "
        f"AND lon BETWEEN {_number(box.west)} AND {_number(box.east)}"
    )


def flight_sql(cfg: Config, day: date) -> str:
    """One source day, airport filter, no ORDER BY and no row limit."""
    airport = cfg.region.airport
    if not airport.isascii() or not airport.isalnum():
        raise ConfigError("airport code is not a simple identifier")
    columns = ", ".join(FLIGHT_COLUMNS)
    table = cfg.source.table(cfg.flights.table)
    return (
        f"SELECT {columns} FROM {table} "
        f"WHERE day = {day_epoch(day)} "
        f"AND (estdepartureairport = '{airport}' OR estarrivalairport = '{airport}')"
    )


def sql_sha256(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()
