"""Cloud Run job loop: the ack/nack/dead-letter decisions around the script."""

from aviation_events.cloud_gcp import Delivery
from aviation_events.job import EventJob
from aviation_events.store import TransientError
from conftest import frozen_clock


class FakeStore:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [])
        self.commits = []
        self.quarantined = []

    def commit_delivery(self, event, message_id, received_at, *, moves_state, body):
        self.commits.append((event.event_id, message_id, moves_state))
        return self.outcomes.pop(0)

    def record_quarantine(self, delivery_key, reason, body, seen_at):
        self.quarantined.append((delivery_key, reason))


class FakeDeadLetters:
    def __init__(self):
        self.published = []

    def publish(self, body, reason):
        self.published.append((body, reason))


class FakePuller:
    def __init__(self, batches):
        self.batches = [list(batch) for batch in batches]
        self.acked = []
        self.nacked = []

    def pull_batch(self, max_messages):
        return self.batches.pop(0) if self.batches else []

    def acknowledge(self, ack_ids):
        self.acked.extend(ack_ids)

    def nack(self, ack_ids):
        self.nacked.extend(ack_ids)


def _delivery(message_id, body):
    return Delivery(f"ack-{message_id}", message_id, body, {})


GOOD_BODY = (
    b'{"event_id": "evt-1", "entity_id": "LH1", "event_type": "on_stand",'
    b' "event_time": "2026-11-15T10:30:00Z", "revision": 1,'
    b' "schema_version": "1", "payload": {}}'
)
MALFORMED_BODY = b'{"event_id": "evt-x"}'


def test_redelivered_commit_is_a_plain_ack_without_dead_letter():
    store = FakeStore(outcomes=[("redelivered", "")])
    dead_letters = FakeDeadLetters()
    job = EventJob(store, FakePuller([]), dead_letters)

    status = job.process(GOOD_BODY, "m-1", frozen_clock())

    assert status == "ack"
    assert dead_letters.published == []
    assert store.commits == [("evt-1", "m-1", True)]


def test_conflict_outcome_publishes_the_body_with_the_script_reason():
    reason = "revision 2 of LH1 already stored with a different payload (stored event evt-0)"
    store = FakeStore(outcomes=[("conflict", reason)])
    dead_letters = FakeDeadLetters()
    job = EventJob(store, FakePuller([]), dead_letters)

    status = job.process(GOOD_BODY, "m-2", frozen_clock())

    assert status == "dead_lettered"
    assert dead_letters.published == [(GOOD_BODY, reason)]


def test_unparseable_body_quarantines_first_then_dead_letters():
    store = FakeStore()
    dead_letters = FakeDeadLetters()
    job = EventJob(store, FakePuller([]), dead_letters)

    status = job.process(MALFORMED_BODY, "m-3", frozen_clock())

    assert status == "dead_lettered"
    assert store.quarantined == [
        ("m-3", "missing_field:entity_id,event_type,event_time,revision,schema_version,payload")
    ]
    assert dead_letters.published == [(MALFORMED_BODY, store.quarantined[0][1])]
    assert store.commits == []  # nothing reached the decision script


def test_unknown_event_type_commits_without_moving_state():
    body = GOOD_BODY.replace(b'"on_stand"', b'"baggage_loaded"')
    store = FakeStore(outcomes=[("stored", "")])
    job = EventJob(store, FakePuller([]), FakeDeadLetters())

    status = job.process(body, "m-4", frozen_clock())

    assert status == "ack"
    assert store.commits == [("evt-1", "m-4", False)]


def test_warehouse_error_nacks_the_delivery():
    class FlakyStore(FakeStore):
        def commit_delivery(self, *args, **kwargs):
            raise TransientError("warehouse unavailable")

    job = EventJob(FlakyStore(), FakePuller([]), FakeDeadLetters())
    assert job.process(GOOD_BODY, "m-5", frozen_clock()) == "nack"


def test_drain_processes_until_the_backlog_empties():
    store = FakeStore(outcomes=[("applied", ""), ("redelivered", ""), ("applied", "")])
    puller = FakePuller(
        [
            [_delivery("m-1", GOOD_BODY), _delivery("m-2", GOOD_BODY)],
            [_delivery("m-3", GOOD_BODY)],
            [],
        ]
    )
    dead_letters = FakeDeadLetters()
    job = EventJob(store, puller, dead_letters)

    summary = job.drain(100)

    assert summary == {"processed": 3, "nacked": 0, "dead_lettered": 0}
    assert puller.acked == ["ack-m-1", "ack-m-2", "ack-m-3"]
    assert puller.nacked == []


def test_drain_stops_at_the_message_cap():
    store = FakeStore(outcomes=[("applied", ""), ("applied", "")])
    puller = FakePuller(
        [[_delivery("m-1", GOOD_BODY), _delivery("m-2", GOOD_BODY), _delivery("m-3", GOOD_BODY)]]
    )
    job = EventJob(store, puller, FakeDeadLetters())

    summary = job.drain(2)

    assert summary["processed"] == 2
    assert puller.acked == ["ack-m-1", "ack-m-2"]
    assert puller.batches == []  # the unacked third delivery redelivers later


def test_drain_counts_dead_letters_and_nacks():
    store = FakeStore(outcomes=[("applied", "")])
    puller = FakePuller([[_delivery("m-1", GOOD_BODY), _delivery("m-2", MALFORMED_BODY)]])

    # m-2 is malformed: quarantine path, no commit; make quarantine fail once
    # by wrapping the store for the second delivery only.
    dead_letters = FakeDeadLetters()
    job = EventJob(store, puller, dead_letters)

    original = store.record_quarantine

    def flaky_quarantine(*args, **kwargs):
        original(*args, **kwargs)
        raise TransientError("warehouse hiccup after recording")

    store.record_quarantine = flaky_quarantine

    # m-1 processes fine; m-2 raises after the durable record -> nack.
    summary = job.drain(10)

    # m-1 acks; m-2 records its quarantine row durably, then fails and nacks;
    # the dead-letter publish happens on the redelivery, not in this pass.
    assert summary == {"processed": 2, "nacked": 1, "dead_lettered": 0}
    assert puller.acked == ["ack-m-1"]
    assert puller.nacked == ["ack-m-2"]
    assert [q[0] for q in store.quarantined] == ["m-2"]
    assert dead_letters.published == []
