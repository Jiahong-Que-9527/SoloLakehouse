"""Reducer decision table: design section 5, rules 3-6, plus unknown types."""

from datetime import UTC, datetime

from aviation_events.envelope import parse_envelope
from aviation_events.reducer import (
    KNOWN_EVENT_TYPES,
    OUTCOME_APPLIED,
    OUTCOME_CONFLICT,
    OUTCOME_DUPLICATE,
    OUTCOME_IGNORED,
    OUTCOME_STORED,
    EntityState,
    decide,
)
from conftest import envelope_body


def event(event_id, revision, payload, event_type="cargo_unloading_complete"):
    return parse_envelope(envelope_body(event_id, "LH1", event_type, revision, payload))


def state(revision, payload, event_id="evt-0"):
    return EntityState(
        entity_id="LH1",
        revision=revision,
        event_id=event_id,
        event_type="cargo_unloading_complete",
        event_time=datetime(2026, 11, 15, 10, 0, tzinfo=UTC),
        payload='{"stand":"B12"}' if payload is None else payload,
    )


def test_no_state_applies_the_event():
    decision = decide(event("evt-1", 1, {"stand": "B12"}), None)
    assert decision.outcome == OUTCOME_APPLIED
    assert decision.state.revision == 1
    assert decision.state.event_id == "evt-1"
    assert decision.state.payload == '{"stand":"B12"}'
    assert not decision.dead_letter


def test_higher_revision_replaces_the_state():
    decision = decide(event("evt-3", 3, {"stand": "B14"}), state(2, '{"stand":"B12"}'))
    assert decision.outcome == OUTCOME_APPLIED
    assert decision.state.revision == 3
    assert decision.state.payload == '{"stand":"B14"}'


def test_older_revision_is_ignored_and_keeps_the_state():
    decision = decide(event("evt-1", 1, {"stand": "B12"}), state(2, '{"stand":"B12"}'))
    assert decision.outcome == OUTCOME_IGNORED
    assert decision.state is None


def test_equal_revision_with_equal_payload_is_a_duplicate():
    stored = state(2, '{"stand":"B12"}')
    decision = decide(event("evt-9", 2, {"stand": "B12"}), stored)
    assert decision.outcome == OUTCOME_DUPLICATE
    assert decision.state is None
    assert not decision.dead_letter


def test_equal_revision_with_different_payload_is_a_conflict():
    decision = decide(event("evt-9", 2, {"stand": "B14"}), state(2, '{"stand":"B12"}'))
    assert decision.outcome == OUTCOME_CONFLICT
    assert decision.state is None
    assert decision.dead_letter
    assert decision.reason is not None and "different payload" in decision.reason


def test_payload_key_order_does_not_change_equality():
    # The stored payload is canonical JSON, so key order is already sorted.
    stored = state(2, '{"gate":"G7","stand":"B12"}')
    decision = decide(event("evt-9", 2, {"gate": "G7", "stand": "B12"}), stored)
    assert decision.outcome == OUTCOME_DUPLICATE


def test_unknown_type_is_stored_and_never_moves_state():
    decision = decide(
        event("evt-5", 5, {"cart": "C3"}, event_type="baggage_loaded"), state(2, None)
    )
    assert decision.outcome == OUTCOME_STORED
    assert decision.state is None


def test_unknown_type_stays_stored_even_without_a_state():
    decision = decide(event("evt-5", 1, {}, event_type="baggage_loaded"), None)
    assert decision.outcome == OUTCOME_STORED
    assert decision.state is None


def test_known_types_cover_the_airport_and_energy_fixtures():
    assert KNOWN_EVENT_TYPES == frozenset(
        {
            "on_stand",
            "unloading_started",
            "cargo_unloading_complete",
            "equipment_clear",
            "observation_revision",
        }
    )
