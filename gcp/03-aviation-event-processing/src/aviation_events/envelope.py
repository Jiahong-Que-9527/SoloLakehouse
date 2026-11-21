"""Envelope wire contract (design section 4).

``parse_envelope`` is the single gate between the wire format and the
reducer. Every rejection is a permanent contract failure: the consumer
records the body in quarantine and routes it to the dead-letter path
instead of retrying it. The field set is closed — unknown top-level keys
mean the producer does not speak this schema version, and ``schema_version``
exists precisely so producers bump it instead of growing the object.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

REQUIRED_FIELDS = (
    "event_id",
    "entity_id",
    "event_type",
    "event_time",
    "revision",
    "schema_version",
    "payload",
)

_STRING_FIELDS = ("event_id", "entity_id", "event_type", "schema_version")


class EnvelopeError(ValueError):
    """A body is not a valid event envelope; the reason is a stable code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Envelope:
    event_id: str
    entity_id: str
    event_type: str
    event_time: datetime
    revision: int
    schema_version: str
    payload: dict

    @property
    def canonical_payload(self) -> str:
        """Canonical JSON of the payload; equality of revisions compares this."""
        return _canonical(self.payload)


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _reject(reason: str) -> None:
    raise EnvelopeError(reason)


def parse_envelope(body: bytes) -> Envelope:
    """Parse one wire body into an envelope or raise :class:`EnvelopeError`."""
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _reject("invalid_json")
    if not isinstance(document, dict):
        _reject("not_an_object")

    missing = [field for field in REQUIRED_FIELDS if field not in document]
    if missing:
        _reject("missing_field:" + ",".join(missing))
    unknown = sorted(set(document) - set(REQUIRED_FIELDS))
    if unknown:
        _reject("unknown_field:" + ",".join(unknown))

    for field in _STRING_FIELDS:
        value = document[field]
        if not isinstance(value, str):
            _reject(f"invalid_type:{field}")
        if not value:
            _reject(f"empty_field:{field}")

    revision = document["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int):
        _reject("invalid_type:revision")
    if revision <= 0:
        _reject("invalid_revision")

    raw_time = document["event_time"]
    if not isinstance(raw_time, str):
        _reject("invalid_type:event_time")
    try:
        event_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except ValueError:
        _reject("invalid_time:event_time")
    if event_time.tzinfo is None:
        _reject("invalid_time:event_time")

    payload = document["payload"]
    if not isinstance(payload, dict):
        _reject("invalid_type:payload")

    return Envelope(
        event_id=document["event_id"],
        entity_id=document["entity_id"],
        event_type=document["event_type"],
        event_time=event_time.astimezone(UTC),
        revision=revision,
        schema_version=document["schema_version"],
        payload=payload,
    )
