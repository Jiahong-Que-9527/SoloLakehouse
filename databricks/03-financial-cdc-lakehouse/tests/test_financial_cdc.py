from collections import Counter
from decimal import Decimal

import pytest
from cdc_fixture import FILES, OBSERVATION, fixture
from financial_cdc import Change, Delivery, reduce_batch


def input_rows():
    files, _ = fixture()
    return {
        file: [
            Delivery(
                file,
                row["ordinal"],
                Change(
                    **{
                        k: (Decimal(v) if k == "amount" and v is not None else v)
                        for k, v in row.items()
                        if k != "ordinal"
                    }
                ),
            )
            for row in rows
        ]
        for file, rows in files.items()
    }


def test_replayed_committed_batch_is_a_noop():
    deliveries = input_rows()
    highest, seen, recorded = {}, {}, {}
    reduce_batch(deliveries[FILES[0]], highest, seen, recorded)
    outcomes, updates = reduce_batch(deliveries[FILES[1]], highest, seen, recorded)
    assert [result for _, result in outcomes] == ["duplicate", "conflict", "applied"]
    assert updates[0].change.operation == "DELETE"
    assert highest["transaction", "tx-focus"] == 4
    assert reduce_batch(deliveries[FILES[1]], highest, seen, recorded) == ([], [])
    outcomes, updates = reduce_batch(deliveries[FILES[2]], highest, seen, recorded)
    assert [result for _, result in outcomes] == [
        "ignored",
        "applied",
        "ignored",
        "applied",
        "duplicate",
    ]
    assert ("transaction", "tx-focus") not in [delivery.change.identity for delivery in updates]
    assert highest["transaction", "tx-withdrawn"] == 3


def test_one_microbatch_matches_independent_oracle():
    records = input_rows()
    unordered = [item for file in reversed(FILES) for item in reversed(records[file])]
    outcomes, current = reduce_batch(unordered, {}, {}, {})
    _, expected = fixture()
    actual = {
        row.change.identity: (
            row.change.sequence_number,
            row.change.amount,
            row.change.operation == "DELETE",
        )
        for row in current
    }
    assert actual == {
        key: (seq, Decimal(amount) if amount else None, tombstone)
        for key, (seq, amount, tombstone) in expected.items()
    }
    assert actual["observation", OBSERVATION] == (2, Decimal("1.0425"), False)
    assert Counter(result for _, result in outcomes) == {
        "applied": 184,
        "duplicate": 2,
        "ignored": 2,
        "conflict": 2,
    }


def test_change_to_an_immutable_delivery_is_detected():
    records = input_rows()
    delivery = records[FILES[0]][0]
    highest, seen, recorded = {}, {}, {}
    reduce_batch([delivery], highest, seen, recorded)
    changed = Delivery(delivery.file, delivery.ordinal, records[FILES[0]][1].change)
    with pytest.raises(ValueError, match="immutable delivery changed"):
        reduce_batch([changed], highest, seen, recorded)


@pytest.mark.parametrize("sequence", [0, -1])
def test_bad_sequence_is_rejected(sequence):
    with pytest.raises(ValueError, match="positive"):
        Change("transaction", "tx", sequence, "DELETE", None, None, None, "2025-02-05T10:00:00Z")
