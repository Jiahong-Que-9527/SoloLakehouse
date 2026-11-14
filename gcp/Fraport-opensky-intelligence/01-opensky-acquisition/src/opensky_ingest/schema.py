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


# All flights_data4 columns, in the order DESCRIBE returned on 2026-11-14.
FLIGHT_COLUMNS = (
    "icao24",
    "firstseen",
    "estdepartureairport",
    "lastseen",
    "estarrivalairport",
    "callsign",
    "track",
    "estdepartureairporthorizdistance",
    "estdepartureairportvertdistance",
    "estarrivalairporthorizdistance",
    "estarrivalairportvertdistance",
    "departureairportcandidatescount",
    "arrivalairportcandidatescount",
    "otherdepartureairportcandidates",
    "otherarrivalairportcandidates",
    "day",
)

FLIGHT_TRINO_TYPES = {
    "icao24": "varchar",
    "firstseen": "integer",
    "estdepartureairport": "varchar",
    "lastseen": "integer",
    "estarrivalairport": "varchar",
    "callsign": "varchar",
    "track": (
        "array(row(time integer, latitude double, longitude double, altitude double, "
        "heading real, onground boolean))"
    ),
    "estdepartureairporthorizdistance": "integer",
    "estdepartureairportvertdistance": "integer",
    "estarrivalairporthorizdistance": "integer",
    "estarrivalairportvertdistance": "integer",
    "departureairportcandidatescount": "integer",
    "arrivalairportcandidatescount": "integer",
    "otherdepartureairportcandidates": (
        "array(row(icao24 varchar, horizdistance integer, vertdistance integer))"
    ),
    "otherarrivalairportcandidates": (
        "array(row(icao24 varchar, horizdistance integer, vertdistance integer))"
    ),
    "day": "integer",
}

TRACK_FIELDS = ("time", "latitude", "longitude", "altitude", "heading", "onground")
CANDIDATE_FIELDS = ("icao24", "horizdistance", "vertdistance")

_TRACK = pa.list_(
    pa.struct(
        [
            pa.field("time", pa.int64()),
            pa.field("latitude", pa.float64()),
            pa.field("longitude", pa.float64()),
            pa.field("altitude", pa.float64()),
            pa.field("heading", pa.float32()),
            pa.field("onground", pa.bool_()),
        ]
    )
)
_CANDIDATES = pa.list_(
    pa.struct(
        [
            pa.field("icao24", pa.string()),
            pa.field("horizdistance", pa.int64()),
            pa.field("vertdistance", pa.int64()),
        ]
    )
)
_FLIGHT_ARROW = {
    "icao24": pa.string(),
    "firstseen": pa.int64(),
    "estdepartureairport": pa.string(),
    "lastseen": pa.int64(),
    "estarrivalairport": pa.string(),
    "callsign": pa.string(),
    "track": _TRACK,
    "estdepartureairporthorizdistance": pa.int64(),
    "estdepartureairportvertdistance": pa.int64(),
    "estarrivalairporthorizdistance": pa.int64(),
    "estarrivalairportvertdistance": pa.int64(),
    "departureairportcandidatescount": pa.int64(),
    "arrivalairportcandidatescount": pa.int64(),
    "otherdepartureairportcandidates": _CANDIDATES,
    "otherarrivalairportcandidates": _CANDIDATES,
    "day": pa.int64(),
}


def flight_schema() -> pa.Schema:
    """Nullable Arrow schema for one flights_data4 day."""
    return pa.schema(
        [pa.field(name, _FLIGHT_ARROW[name], nullable=True) for name in FLIGHT_COLUMNS]
    )
