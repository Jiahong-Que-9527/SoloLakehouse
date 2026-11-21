"""Sequence step 1: the expected state, written before anything is published.

The generator produces two independently seeded batches (airport and
energy). For every seed the final state, receipt counts, history outcome
counts and dead-letter bodies must match the expectations below — only
the delivery order may differ.
"""

from collections import Counter

from aviation_events.consumer import EventConsumer, FakeDeadLetterSink
from aviation_events.generator import airport_batch, energy_batch
from aviation_events.store import InMemoryStore
from conftest import frozen_clock

SEEDS = (1, 7, 42)

LEG123 = "LH123-2026-11-15"
LEG456 = "LH456-2026-11-15"
LEG789 = "LH789-2026-11-15"
INTERVAL_A = "DE|actual_load_mwh|2026-06-08T00:00:00Z"
INTERVAL_B = "DE|actual_load_mwh|2026-06-08T00:15:00Z"
INTERVAL_C = "DE|actual_load_mwh|2026-06-08T00:30:00Z"


def run_batch(messages):
    store = InMemoryStore()
    sink = FakeDeadLetterSink()
    consumer = EventConsumer(store, sink, clock=frozen_clock)
    outcomes = [consumer.process(message.body, message.message_id) for message in messages]
    return store, sink, outcomes


def test_generator_is_deterministic_for_a_fixed_seed():
    assert airport_batch(5) == airport_batch(5)
    assert energy_batch(5) == energy_batch(5)


def test_seed_only_changes_delivery_order_not_the_envelope_set():
    first = [message.body for message in airport_batch(1)]
    second = [message.body for message in airport_batch(7)]
    assert Counter(first) == Counter(second)
    assert first != second  # the shuffle must actually reorder something


def test_airport_expected_state_holds_for_every_seed():
    expected_states = {
        LEG123: ("evt-123-d", 4, "equipment_clear", '{"stand":"A01"}'),
        # The correction at revision 3 wins over the applied revision 2 and
        # the conflicting revision 2 under a new event ID.
        LEG456: ("evt-456-f", 3, "equipment_clear", '{"stand":"B12"}'),
        # Revision 4 arrived first; revisions 1-3 stay ignored, the unknown
        # type at revision 5 is stored but never moves state.
        LEG789: ("evt-789-a", 4, "equipment_clear", '{"stand":"A08"}'),
    }
    for seed in SEEDS:
        store, sink, outcomes = run_batch(airport_batch(seed))
        assert set(store.states) == set(expected_states)
        for entity_id, (event_id, revision, event_type, payload) in expected_states.items():
            state = store.states[entity_id]
            assert (state.event_id, state.revision, state.event_type, state.payload) == (
                event_id,
                revision,
                event_type,
                payload,
            ), f"seed {seed}, entity {entity_id}"

        assert len(store.receipts) == 13
        assert Counter(row.outcome for row in store.history) == Counter(
            {"applied": 7, "ignored": 4, "conflict": 1, "stored": 1}
        )
        assert len(store.quarantine) == 2
        reasons = sorted(row.reason for row in store.quarantine)
        assert reasons[0].startswith("missing_field:")
        assert reasons[1].startswith("revision 2 of LH456-2026-11-15")
        assert len(sink.published) == 2
        assert all(outcome.status in {"ack", "dead_lettered"} for outcome in outcomes)
        assert sum(o.status == "dead_lettered" for o in outcomes) == 2


def test_airport_conflicting_and_malformed_bodies_reach_the_dead_letter_path():
    for seed in SEEDS:
        store, sink, _ = run_batch(airport_batch(seed))
        dead_bodies = [body.decode("utf-8") for body, _ in sink.published]
        conflicting = next(body for body in dead_bodies if '"B14"' in body)
        assert '"evt-456-d"' in conflicting
        malformed = next(body for body in dead_bodies if "evt-456-e" in body)
        assert '"payload"' not in malformed
        quarantined = {row.delivery_key: row for row in store.quarantine}
        assert len(quarantined) == 2
        assert all(row.occurrences == 1 for row in quarantined.values())


def test_energy_expected_final_values_per_interval_for_every_seed():
    expected_values = {INTERVAL_A: 40125.5, INTERVAL_B: 39800.0, INTERVAL_C: 40350.0}
    for seed in SEEDS:
        store, sink, outcomes = run_batch(energy_batch(seed))
        assert set(store.states) == set(expected_values)
        for entity_id, value in expected_values.items():
            state = store.states[entity_id]
            assert state.payload == f'{{"value":{value}}}', f"seed {seed}, entity {entity_id}"

        assert len(store.receipts) == 8
        assert Counter(row.outcome for row in store.history) == Counter(
            {"applied": 5, "ignored": 1, "duplicate": 1, "conflict": 1}
        )
        assert len(store.quarantine) == 1
        assert len(sink.published) == 1
        assert sum(o.status == "dead_lettered" for o in outcomes) == 1


def test_energy_correction_wins_and_late_older_revisions_are_ignored():
    store, _, _ = run_batch(energy_batch(7))
    # INTERVAL_A: revision 2 (40125.5) was applied first, revision 1 ignored.
    a_history = [row for row in store.history if row.entity_id == INTERVAL_A]
    assert [(row.outcome, row.revision) for row in a_history] == [
        ("applied", 2),
        ("ignored", 1),
    ]
    # INTERVAL_C: revisions 1, 2, 3 all applied in order; the conflicting
    # revision 3 under a new event ID is dead-lettered, state untouched.
    c_history = [row for row in store.history if row.entity_id == INTERVAL_C]
    assert [(row.outcome, row.revision) for row in c_history] == [
        ("applied", 1),
        ("applied", 2),
        ("applied", 3),
        ("conflict", 3),
    ]
    assert store.states[INTERVAL_C].event_id == "evt-e-c3"
