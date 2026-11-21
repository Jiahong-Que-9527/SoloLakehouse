"""Transactional store: buffered writes, all-or-nothing commit, transient failure."""

from datetime import UTC, datetime

import pytest

from aviation_events.envelope import parse_envelope
from aviation_events.reducer import EntityState
from aviation_events.store import InMemoryStore, TransientError
from conftest import envelope_body, frozen_clock


def _event(event_id="evt-1", entity_id="LH1", revision=1):
    return parse_envelope(envelope_body(event_id, entity_id, "on_stand", revision, {}))


def _state(entity_id="LH1", revision=1):
    return EntityState(
        entity_id=entity_id,
        revision=revision,
        event_id="evt-1",
        event_type="on_stand",
        event_time=datetime(2026, 11, 15, 10, 30, tzinfo=UTC),
        payload="{}",
    )


def test_commit_applies_every_write_in_one_transaction():
    store = InMemoryStore()
    with store.transaction() as tx:
        tx.put_state(_state())
        tx.record_receipt(_event(), "applied", "m-1", frozen_clock())
    assert list(store.states) == ["LH1"]
    assert list(store.receipts) == ["evt-1"]
    assert len(store.history) == 1


def test_exception_discards_the_whole_transaction():
    store = InMemoryStore()
    with pytest.raises(RuntimeError, match="boom"):
        with store.transaction() as tx:
            tx.put_state(_state())
            tx.record_receipt(_event(), "applied", "m-1", frozen_clock())
            raise RuntimeError("boom")
    assert store.states == {}
    assert store.receipts == {}
    assert store.history == ()


def test_failed_commit_is_transient_and_applies_nothing():
    store = InMemoryStore(fail_commits=1)
    with pytest.raises(TransientError):
        with store.transaction() as tx:
            tx.put_state(_state())
    assert store.states == {}
    with store.transaction() as tx:
        tx.put_state(_state())
    assert list(store.states) == ["LH1"]


def test_receipt_check_sees_pending_writes_inside_the_same_transaction():
    store = InMemoryStore()
    with store.transaction() as tx:
        assert not tx.receipt_exists("evt-1")
        tx.record_receipt(_event(), "applied", "m-1", frozen_clock())
        assert tx.receipt_exists("evt-1")


def test_quarantine_row_deduplicates_by_delivery_and_reason():
    store = InMemoryStore()
    for _ in range(2):
        with store.transaction() as tx:
            tx.record_quarantine("m-1", "missing_field:payload", "{...}", frozen_clock())
    assert len(store.quarantine) == 1
    assert store.quarantine[0].occurrences == 2


def test_nested_transactions_are_rejected():
    store = InMemoryStore()
    with store.transaction():
        with pytest.raises(RuntimeError, match="nested"):
            with store.transaction():
                pass
