"""Shared builders for the G03 contract tests."""

import json
from datetime import UTC, datetime

DEFAULT_EVENT_TIME = "2026-11-15T10:30:00Z"


def frozen_clock() -> datetime:
    """Deterministic receive timestamp for every consumer in the tests."""
    return datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def envelope_body(
    event_id: str,
    entity_id: str,
    event_type: str,
    revision: int,
    payload: dict,
    *,
    event_time: str = DEFAULT_EVENT_TIME,
    schema_version: str = "1",
) -> bytes:
    document = {
        "event_id": event_id,
        "entity_id": entity_id,
        "event_type": event_type,
        "event_time": event_time,
        "revision": revision,
        "schema_version": schema_version,
        "payload": payload,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
