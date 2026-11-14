"""SQL for one state-vector hour. The text and its hash are part of the contract."""

from __future__ import annotations

import hashlib
from datetime import datetime

from .config import Config
from .schema import STATE_VECTOR_COLUMNS
from .util import epoch


def _number(value: float) -> str:
    return format(value, ".10g")


def state_vector_sql(cfg: Config, hour: datetime) -> str:
    """One hour, no ORDER BY and no row limit. `serials` is not selected."""
    box = cfg.region.bbox
    columns = ", ".join(STATE_VECTOR_COLUMNS)
    table = cfg.source.table(cfg.state_vectors.table)
    return (
        f"SELECT {columns} FROM {table} "
        f"WHERE hour = {epoch(hour)} "
        f"AND lat BETWEEN {_number(box.south)} AND {_number(box.north)} "
        f"AND lon BETWEEN {_number(box.west)} AND {_number(box.east)}"
    )


def sql_sha256(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()
