"""Consumer flow: the design section 7 acceptance matrix, locally."""

from aviation_events.consumer import EventConsumer, FakeDeadLetterSink
from aviation_events.store import InMemoryStore
from conftest import envelope_body, frozen_clock

ENTITY = "LH1-2026-11-15"


def make_consumer(store=None, sink=None):
    store = store if store is not None else InMemoryStore()
    sink = sink if sink is not None else FakeDeadLetterSink()
    consumer = EventConsumer(store, sink, clock=frozen_clock)
    return consumer, store, sink


def process_all(consumer, store, bodies):
    return [consumer.process(body, f"m-{index:04d}") for index, body in enumerate(bodies, 1)]


def test_same_event_id_delivered_three_times_leaves_one_receipt_and_one_change():
    body = envelope_body("evt-1", ENTITY, "on_stand", 1, {"stand": "A01"})
    consumer, store, sink = make_consumer()
    outcomes = process_all(consumer, store, [body, body, body])
    assert all(o.status == "ack" for o in outcomes)
    assert len(store.receipts) == 1
    assert len(store.history) == 1
    assert store.states[ENTITY].event_id == "evt-1"
    assert sink.published == []


def test_higher_revision_first_then_older_keeps_the_higher_state():
    higher = envelope_body("evt-2", ENTITY, "on_stand", 2, {"stand": "A02"})
    older = envelope_body("evt-1", ENTITY, "on_stand", 1, {"stand": "A01"})
    consumer, store, _ = make_consumer()
    outcomes = process_all(consumer, store, [higher, older])
    assert [o.status for o in outcomes] == ["ack", "ack"]
    assert store.states[ENTITY].revision == 2
    assert [row.outcome for row in store.history] == ["applied", "ignored"]


def test_missing_required_field_goes_to_quarantine_and_dead_letter():
    body = b'{"event_id": "evt-1", "entity_id": "LH1-2026-11-15"}'
    consumer, store, sink = make_consumer()
    outcome = consumer.process(body, "m-1")
    assert outcome.status == "dead_lettered"
    assert outcome.reason == "missing_field:event_type,event_time,revision,schema_version,payload"
    assert store.states == {}
    assert store.receipts == {}
    assert len(store.quarantine) == 1
    assert store.quarantine[0].body == body.decode("utf-8")
    assert sink.published == [(body, outcome.reason)]


def test_warehouse_unavailable_once_nacks_then_applies_on_retry():
    body = envelope_body("evt-1", ENTITY, "on_stand", 1, {"stand": "A01"})
    consumer, store, _ = make_consumer(store=InMemoryStore(fail_commits=1))
    first = consumer.process(body, "m-1")
    assert first.status == "nack"
    assert store.receipts == {} and store.states == {}
    second = consumer.process(body, "m-2")
    assert second.status == "ack"
    assert len(store.receipts) == 1
    assert store.states[ENTITY].event_id == "evt-1"


def test_crash_after_commit_before_ack_is_safe_on_redelivery():
    body = envelope_body("evt-1", ENTITY, "on_stand", 1, {"stand": "A01"})
    consumer, store, _ = make_consumer()
    consumer.process(body, "m-1")  # commit succeeds, ack never sent
    redelivery = consumer.process(body, "m-1")
    assert redelivery.status == "ack"
    assert len(store.receipts) == 1
    assert len(store.history) == 1
    assert store.states[ENTITY].event_id == "evt-1"


def test_unknown_event_type_is_stored_without_moving_state():
    body = envelope_body("evt-1", ENTITY, "baggage_loaded", 5, {"cart": "C3"})
    consumer, store, sink = make_consumer()
    outcome = consumer.process(body, "m-1")
    assert outcome.status == "ack"
    assert store.states == {}
    assert store.history[0].outcome == "stored"
    assert sink.published == []


def test_conflicting_revision_under_a_new_id_dead_letters_without_retry():
    stored = envelope_body("evt-1", ENTITY, "on_stand", 2, {"stand": "A01"})
    conflicting = envelope_body("evt-2", ENTITY, "on_stand", 2, {"stand": "A02"})
    consumer, store, sink = make_consumer()
    assert consumer.process(stored, "m-1").status == "ack"
    outcome = consumer.process(conflicting, "m-2")
    assert outcome.status == "dead_lettered"
    assert "different payload" in outcome.reason
    assert store.states[ENTITY].event_id == "evt-1"  # state untouched
    assert store.receipts["evt-2"].outcome == "conflict"
    assert [row.outcome for row in store.history] == ["applied", "conflict"]
    assert [body for body, _ in sink.published] == [conflicting]


def test_dead_letter_publish_failure_nacks_but_quarantine_row_is_durable():
    body = b'{"event_id": "evt-1"}'  # malformed
    consumer, store, sink = make_consumer(sink=FakeDeadLetterSink(failures=1))
    first = consumer.process(body, "m-1")
    assert first.status == "nack"
    assert len(store.quarantine) == 1  # durable before any ack
    assert sink.published == []
    second = consumer.process(body, "m-1")
    assert second.status == "dead_lettered"
    assert store.quarantine[0].occurrences == 2
    # Only the successful publish is recorded; both attempts used the
    # original contract reason, not the transient nack reason.
    assert [reason for _, reason in sink.published] == [
        "missing_field:entity_id,event_type,event_time,revision,schema_version,payload"
    ]
