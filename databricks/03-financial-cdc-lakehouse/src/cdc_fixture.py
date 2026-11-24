"""Seeded immutable JSONL deliveries and an independently constructed final state."""

from decimal import Decimal
from random import Random

from financial_cdc import CENTS

SEED = 20261124
OBSERVATION = "EXR.D.USD.EUR.SP00.A/2025-02-05"
FILES = tuple(f"{n:02}.json" for n in range(1, 5))


def event(key, seq, operation, amount=None, kind="transaction"):
    return {
        "kind": kind,
        "key": key,
        "sequence_number": seq,
        "operation": operation,
        "amount": amount,
        "status": "POSTED" if amount is not None else None,
        "currency": ("EUR" if kind == "transaction" else "USD_PER_EUR") if amount else None,
        "event_time": f"2025-02-05T10:00:{seq:02}Z",
    }


def fixture():
    insert = event("tx-focus", 1, "INSERT", "10.00")
    update = event("tx-focus", 2, "UPDATE", "12.00")
    obs = event(OBSERVATION, 1, "INSERT", "1.0412", "observation")
    files = [
        [insert, update, event("tx-withdrawn", 1, "INSERT", "20.00"), obs],
        [update, event("tx-focus", 2, "UPDATE", "99.00"), event("tx-focus", 4, "DELETE")],
        [
            event("tx-focus", 3, "UPDATE", "14.00"),
            event("tx-withdrawn", 3, "DELETE"),
            event("tx-withdrawn", 2, "UPDATE", "21.00"),
            event(OBSERVATION, 2, "UPDATE", "1.0425", "observation"),
            obs,
        ],
        [event("tx-focus", 5, "INSERT", "17.00"), event("tx-focus", 5, "INSERT", "99.00")],
    ]
    oracle = {
        ("transaction", "tx-focus"): (5, "17.00", False),
        ("transaction", "tx-withdrawn"): (3, None, True),
        ("observation", OBSERVATION): (2, "1.0425", False),
    }
    random = Random(SEED)
    for index in range(160):
        amount = str((Decimal(random.randint(500, 50000)) / 100).quantize(CENTS))
        key = f"tx-seed-{index:04}"
        files[0].append(event(key, 1, "INSERT", amount))
        if index % 10 == 0:
            files[3].append(event(key, 3, "DELETE"))
            oracle["transaction", key] = (3, None, True)
        else:
            oracle["transaction", key] = (1, amount, False)
    return {
        name: [row | {"ordinal": i} for i, row in enumerate(rows, 1)]
        for name, rows in zip(FILES, files, strict=True)
    }, oracle
