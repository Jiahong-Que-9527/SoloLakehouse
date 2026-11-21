"""GCP adapter contract tests for the G03 event path.

The fakes mirror exactly the slice of the real clients that cloud_gcp.py
uses, in the G01 test style. SQL semantics themselves are proven against
the real service during cloud verification; these tests pin the wiring:
one transactional decision script, correct parameters, outcome mapping.
"""

import sys
import types

from aviation_events.cloud_gcp import (
    BigQueryEventStore,
    Delivery,
    PubSubDeadLetters,
    PubSubPublisher,
    PubSubPuller,
    decision_script,
    quarantine_script,
)
from aviation_events.envelope import parse_envelope
from conftest import envelope_body, frozen_clock


class FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return iter(self._rows)


class FakeBigQueryClient:
    """Mirrors the slice of the real client that BigQueryEventStore uses."""

    project = "test-project"

    def __init__(self, result_rows=None):
        self.queries = []  # (sql, job_config)
        self._result_rows = result_rows or []

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        return FakeQueryJob(list(self._result_rows))


class FakeScalarQueryParameter:
    def __init__(self, name, type_, value):
        self.name = name
        self.type_ = type_
        self.value = value


def _install_fake_bigquery(monkeypatch, client):
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    bigquery = types.ModuleType("google.cloud.bigquery")
    bigquery.Client = lambda: client
    bigquery.QueryJobConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
    bigquery.ScalarQueryParameter = FakeScalarQueryParameter
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery)


def _params(client):
    _, job_config = client.queries[0]
    return {p.name: (p.type_, p.value) for p in job_config.query_parameters}


# --- Decision script ----------------------------------------------------------


def test_decision_script_encodes_the_whole_transaction():
    script = decision_script("proj", "aviation_events")
    assert "BEGIN TRANSACTION;" in script
    assert "COMMIT TRANSACTION;" in script
    # rule 1: committed event id is a no-write acknowledgement
    assert (
        "SELECT COUNT(*) FROM `proj.aviation_events.event_receipt` WHERE event_id = @event_id"
        in script
    )
    assert "'redelivered'" in script
    # rules 3-6 compare against the stored revision and canonical payload
    assert (
        "SELECT revision FROM `proj.aviation_events.entity_state` WHERE entity_id = @entity_id"
        in script
    )
    assert "current_payload = @canonical_payload" in script
    assert "'applied'" in script and "'ignored'" in script and "'duplicate'" in script
    # rule 6: the conflict branch receipts, records and quarantines
    assert "`proj.aviation_events.event_quarantine`" in script
    assert "already stored with a different payload" in script
    # unknown types never touch entity_state inside the stored branch:
    # the stored branch only inserts receipt + history rows.
    stored_branch = script.split("'stored'")[1].split("ELSE")[0]
    assert "entity_state" not in stored_branch
    # the final row exposes the outcome and the dead-letter reason
    assert script.strip().endswith("SELECT outcome, IFNULL(quarantine_reason, '') AS reason;")


def test_commit_delivery_passes_envelope_parameters_and_returns_outcome(monkeypatch):
    client = FakeBigQueryClient(result_rows=[{"outcome": "applied", "reason": ""}])
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryEventStore("aviation_events", client=client)
    event = parse_envelope(envelope_body("evt-1", "LH1", "on_stand", 2, {"stand": "A01"}))

    outcome, reason = store.commit_delivery(
        event, "m-1", frozen_clock(), moves_state=True, body=b"..."
    )

    assert (outcome, reason) == ("applied", "")
    params = _params(client)
    assert params["event_id"] == ("STRING", "evt-1")
    assert params["entity_id"] == ("STRING", "LH1")
    assert params["revision"] == ("INT64", 2)
    assert params["canonical_payload"] == ("STRING", '{"stand":"A01"}')
    assert params["moves_state"] == ("BOOL", True)
    assert params["received_at"][0] == "TIMESTAMP"


def test_commit_delivery_returns_the_conflict_reason(monkeypatch):
    reason = "revision 2 of LH1 already stored with a different payload (stored event evt-0)"
    client = FakeBigQueryClient(result_rows=[{"outcome": "conflict", "reason": reason}])
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryEventStore("aviation_events", client=client)
    event = parse_envelope(envelope_body("evt-9", "LH1", "on_stand", 2, {"stand": "B14"}))

    outcome, returned = store.commit_delivery(
        event, "m-2", frozen_clock(), moves_state=True, body=b"..."
    )
    assert (outcome, returned) == ("conflict", reason)


def test_commit_delivery_without_an_outcome_row_is_a_warehouse_error(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryEventStore("aviation_events", client=client)
    event = parse_envelope(envelope_body("evt-1", "LH1", "on_stand", 1, {}))

    import pytest

    with pytest.raises(OSError, match="no outcome row"):
        store.commit_delivery(event, "m-1", frozen_clock(), moves_state=True, body=b"...")


# --- Quarantine upsert ----------------------------------------------------------


def test_quarantine_script_merges_on_delivery_and_reason():
    script = quarantine_script("proj", "aviation_events")
    assert "MERGE `proj.aviation_events.event_quarantine` AS target" in script
    assert (
        "ON target.delivery_key = source.delivery_key AND target.reason = source.reason" in script
    )
    assert "occurrences = target.occurrences + 1" in script


def test_record_quarantine_passes_the_reason_and_body(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    store = BigQueryEventStore("aviation_events", client=client)

    store.record_quarantine("m-1", "missing_field:payload", "{...}", frozen_clock())

    params = _params(client)
    assert params["delivery_key"] == ("STRING", "m-1")
    assert params["reason"] == ("STRING", "missing_field:payload")
    assert params["body"] == ("STRING", "{...}")


# --- Pub/Sub adapters -------------------------------------------------------------


class FakePublisherClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, data, **attributes):
        self.published.append((topic, data, attributes))
        return types.SimpleNamespace(result=lambda: f"ps-{len(self.published)}")


def _install_fake_pubsub(monkeypatch, subscriber, publisher):
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    pubsub_v1 = types.ModuleType("google.cloud.pubsub_v1")
    pubsub_v1.SubscriberClient = lambda: subscriber
    pubsub_v1.PublisherClient = lambda: publisher
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.pubsub_v1", pubsub_v1)


def _subscriber_with(batch):
    return types.SimpleNamespace(
        pull=lambda request: types.SimpleNamespace(
            received_messages=[
                types.SimpleNamespace(
                    ack_id=f"ack-{index}",
                    message=types.SimpleNamespace(
                        message_id=f"m-{index}", data=body, attributes=attributes or {}
                    ),
                )
                for index, (body, attributes) in enumerate(batch, 1)
            ]
        ),
        acknowledge=lambda request: requests_log.append(("ack", request)),
        modify_ack_deadline=lambda request: requests_log.append(("nack", request)),
    )


requests_log: list = []


def test_pull_batch_maps_received_messages(monkeypatch):
    subscriber = _subscriber_with([(b"body", {"reason": "r"})])
    _install_fake_pubsub(monkeypatch, subscriber, FakePublisherClient())
    puller = PubSubPuller("projects/p/subscriptions/aviation-events-pull")

    batch = puller.pull_batch(10)

    assert len(batch) == 1
    delivery = batch[0]
    assert delivery.ack_id == "ack-1"
    assert delivery.message_id == "m-1"
    assert delivery.body == b"body"
    assert delivery.attributes == {"reason": "r"}


def test_acknowledge_and_nack_target_the_subscription(monkeypatch):
    requests_log.clear()
    subscriber = _subscriber_with([])
    _install_fake_pubsub(monkeypatch, subscriber, FakePublisherClient())
    puller = PubSubPuller("projects/p/subscriptions/aviation-events-pull")

    puller.acknowledge(["a1", "a2"])
    puller.nack(["a3"])
    puller.acknowledge([])  # no-op

    assert [
        (
            "ack",
            {
                "subscription": "projects/p/subscriptions/aviation-events-pull",
                "ack_ids": ["a1", "a2"],
            },
        ),
        (
            "nack",
            {
                "subscription": "projects/p/subscriptions/aviation-events-pull",
                "ack_ids": ["a3"],
                "ack_deadline_seconds": 0,
            },
        ),
    ] == requests_log


def test_pull_batch_with_zero_cap_pulls_nothing(monkeypatch):
    subscriber = _subscriber_with([(b"body", {})])
    _install_fake_pubsub(monkeypatch, subscriber, FakePublisherClient())
    assert PubSubPuller("s", client=subscriber).pull_batch(0) == []


def test_dead_letters_publish_with_reason_attribute(monkeypatch):
    publisher = FakePublisherClient()
    _install_fake_pubsub(monkeypatch, _subscriber_with([]), publisher)

    PubSubDeadLetters("projects/p/topics/aviation-events-dlq", client=publisher).publish(
        b"body", "missing_field:payload"
    )

    ((topic, data, attributes),) = publisher.published
    assert topic == "projects/p/topics/aviation-events-dlq"
    assert data == b"body"
    assert attributes == {"reason": "missing_field:payload"}


def test_publisher_returns_the_pubsub_message_id(monkeypatch):
    publisher = FakePublisherClient()
    _install_fake_pubsub(monkeypatch, _subscriber_with([]), publisher)

    message_id = PubSubPublisher("projects/p/topics/aviation-events", client=publisher).publish(
        b"body"
    )

    assert message_id == "ps-1"


def test_delivery_holds_the_wire_shape():
    delivery = Delivery("a1", "m-1", b"x", {"k": "v"})
    assert (delivery.ack_id, delivery.message_id, delivery.body, delivery.attributes) == (
        "a1",
        "m-1",
        b"x",
        {"k": "v"},
    )
