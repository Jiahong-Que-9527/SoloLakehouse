"""Explicit state-vector schema. Types are not inferred from a sample."""

from __future__ import annotations

import pyarrow as pa

SCHEMA_VERSION = "1.0"

# Selected columns, in query order. `serials` is excluded until the pilot A/B test.
STATE_VECTOR_COLUMNS = (
    "time",
    "icao24",
    "lat",
    "lon",
    "velocity",
    "heading",
    "vertrate",
    "callsign",
    "onground",
    "alert",
    "spi",
    "squawk",
    "baroaltitude",
    "geoaltitude",
    "lastposupdate",
    "lastcontact",
    "hour",
)

# Trino types observed by discovery on 2026-11-14. A difference stops the run.
TRINO_TYPES = {
    "time": "integer",
    "icao24": "varchar",
    "lat": "double",
    "lon": "double",
    "velocity": "double",
    "heading": "double",
    "vertrate": "double",
    "callsign": "varchar",
    "onground": "boolean",
    "alert": "boolean",
    "spi": "boolean",
    "squawk": "varchar",
    "baroaltitude": "double",
    "geoaltitude": "double",
    "lastposupdate": "double",
    "lastcontact": "double",
    "hour": "integer",
}

_ARROW = {
    "time": pa.int64(),
    "icao24": pa.string(),
    "lat": pa.float64(),
    "lon": pa.float64(),
    "velocity": pa.float64(),
    "heading": pa.float64(),
    "vertrate": pa.float64(),
    "callsign": pa.string(),
    "onground": pa.bool_(),
    "alert": pa.bool_(),
    "spi": pa.bool_(),
    "squawk": pa.string(),
    "baroaltitude": pa.float64(),
    "geoaltitude": pa.float64(),
    "lastposupdate": pa.float64(),
    "lastcontact": pa.float64(),
    "hour": pa.int64(),
}


def state_vector_schema() -> pa.Schema:
    """Nullable Arrow schema for the columns this version collects."""
    return pa.schema([pa.field(name, _ARROW[name], nullable=True) for name in STATE_VECTOR_COLUMNS])
