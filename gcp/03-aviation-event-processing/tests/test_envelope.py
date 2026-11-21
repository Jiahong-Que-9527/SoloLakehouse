"""Envelope contract: everything rejected here is a permanent failure."""

import json
from datetime import UTC, datetime

import pytest

from aviation_events.envelope import EnvelopeError, parse_envelope
from conftest import envelope_body

FULL_BODY = envelope_body("evt-1", "LH1-2026-11-15", "on_stand", 1, {"stand": "A01"})


def test_valid_body_parses_to_an_aware_utc_time():
    event = parse_envelope(FULL_BODY)
    assert event.event_id == "evt-1"
    assert event.entity_id == "LH1-2026-11-15"
    assert event.event_type == "on_stand"
    assert event.revision == 1
    assert event.schema_version == "1"
    assert event.event_time == datetime(2026, 11, 15, 10, 30, tzinfo=UTC)


def test_canonical_payload_sorts_keys_so_equality_ignores_order():
    body = envelope_body("evt-1", "E", "on_stand", 1, {"stand": "A01", "gate": "G7"})
    event = parse_envelope(body)
    assert event.canonical_payload == '{"gate":"G7","stand":"A01"}'


def test_offset_time_is_normalised_to_utc():
    body = envelope_body("evt-1", "E", "on_stand", 1, {}, event_time="2026-11-15T12:30:00+02:00")
    assert parse_envelope(body).event_time == datetime(2026, 11, 15, 10, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    "field",
    [
        "event_id",
        "entity_id",
        "event_type",
        "event_time",
        "revision",
        "schema_version",
        "payload",
    ],
)
def test_missing_field_is_a_contract_failure(field):
    document = json.loads(FULL_BODY)
    del document[field]
    body = json.dumps(document).encode("utf-8")
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(body)
    assert raised.value.reason == f"missing_field:{field}"


def test_unknown_top_level_field_is_a_contract_failure():
    document = json.loads(FULL_BODY)
    document["trace_id"] = "t-1"
    body = json.dumps(document).encode("utf-8")
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(body)
    assert raised.value.reason == "unknown_field:trace_id"


def test_invalid_json_is_a_contract_failure():
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(b"{not json")
    assert raised.value.reason == "invalid_json"


def test_non_object_json_is_a_contract_failure():
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(b"[1, 2, 3]")
    assert raised.value.reason == "not_an_object"


@pytest.mark.parametrize("revision", [0, -1, True, "2", 1.5, None])
def test_bad_revision_is_a_contract_failure(revision):
    document = json.loads(FULL_BODY)
    document["revision"] = revision
    body = json.dumps(document).encode("utf-8")
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(body)
    assert raised.value.reason.startswith(("invalid_type:revision", "invalid_revision"))


@pytest.mark.parametrize("event_time", ["2026-11-15T10:30:00", "not-a-time", 1760000000, None])
def test_bad_event_time_is_a_contract_failure(event_time):
    document = json.loads(FULL_BODY)
    document["event_time"] = event_time
    body = json.dumps(document).encode("utf-8")
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(body)
    assert raised.value.reason.startswith(("invalid_type:event_time", "invalid_time:event_time"))


@pytest.mark.parametrize("field", ["event_id", "entity_id", "event_type", "schema_version"])
def test_empty_string_field_is_a_contract_failure(field):
    document = json.loads(FULL_BODY)
    document[field] = ""
    body = json.dumps(document).encode("utf-8")
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(body)
    assert raised.value.reason == f"empty_field:{field}"


@pytest.mark.parametrize("payload", [["stand"], "A01", None, 5])
def test_non_object_payload_is_a_contract_failure(payload):
    document = json.loads(FULL_BODY)
    document["payload"] = payload
    body = json.dumps(document).encode("utf-8")
    with pytest.raises(EnvelopeError) as raised:
        parse_envelope(body)
    assert raised.value.reason == "invalid_type:payload"


def test_unknown_event_type_is_valid_at_the_envelope_level():
    """Type filtering is the reducer's job, not the envelope's."""
    body = envelope_body("evt-1", "E", "baggage_loaded", 1, {})
    assert parse_envelope(body).event_type == "baggage_loaded"
