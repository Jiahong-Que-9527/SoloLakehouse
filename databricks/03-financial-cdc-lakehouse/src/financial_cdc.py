"""Deterministic event classification shared by the streaming and batch writers."""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import PurePosixPath

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class Change:
    kind: str
    key: str
    sequence_number: int
    operation: str
    amount: Decimal | None
    status: str | None
    currency: str | None
    event_time: str

    def __post_init__(self):
        if self.kind not in {"transaction", "observation"} or not self.key:
            raise ValueError("expected a nonempty transaction or observation key")
        if self.sequence_number is None or self.sequence_number <= 0:
            raise ValueError("sequence_number must be positive")
        if self.operation not in {"INSERT", "UPDATE", "DELETE"}:
            raise ValueError("unsupported CDC operation")
        if self.operation == "DELETE":
            if any(value is not None for value in (self.amount, self.status, self.currency)):
                raise ValueError("DELETE payload must be empty")
        elif (
            self.amount is None
            or not self.amount.is_finite()
            or self.amount < 0
            or abs(self.amount) >= Decimal("1000000000000")
            or self.amount != self.amount.quantize(Decimal("0.000001"))
            or not self.status
            or not self.currency
        ):
            raise ValueError("an active event requires a bounded amount, status and currency")
        if datetime.fromisoformat(self.event_time).utcoffset() is None:
            raise ValueError("event_time must have a timezone")

    @property
    def identity(self):
        return self.kind, self.key

    @property
    def version(self):
        return *self.identity, self.sequence_number

    @property
    def fingerprint(self):
        amount = None if self.amount is None else str(self.amount.quantize(Decimal("0.000001")))
        return digest([self.operation, amount, self.status, self.currency, self.event_time])


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Delivery:
    file: str
    ordinal: int
    change: Change

    def __post_init__(self):
        if not self.file.endswith(".json") or PurePosixPath(self.file).name != self.file:
            raise ValueError("expected an immutable input file name")
        if self.ordinal is None or self.ordinal <= 0:
            raise ValueError("expected a positive file ordinal")

    @property
    def id(self):
        return "event_" + digest([self.file, self.ordinal])


def reduce_batch(deliveries, highest, seen, recorded):
    """Return delivery outcomes and only the state rows changed by this micro-batch.

    The caller commits both collections in the same Delta MERGE. Existing delivery
    identifiers are skipped, so redelivery after commit cannot add an outcome.
    """
    outcomes, updates = [], {}
    for delivery in sorted(deliveries, key=lambda item: (item.file, item.ordinal)):
        change = delivery.change
        previous = recorded.get(delivery.id)
        if previous is not None:
            if previous != (change.version, change.fingerprint):
                raise ValueError(f"immutable delivery changed: {delivery.file}:{delivery.ordinal}")
            continue
        recorded[delivery.id] = (change.version, change.fingerprint)
        seen_payload = seen.get(change.version)
        if seen_payload is not None:
            outcome = "duplicate" if seen_payload == change.fingerprint else "conflict"
        elif change.sequence_number <= highest.get(change.identity, 0):
            outcome = "ignored"
        else:
            outcome = "applied"
            highest[change.identity] = change.sequence_number
            updates[change.identity] = delivery
        if outcome in {"applied", "ignored"}:
            seen[change.version] = change.fingerprint
        outcomes.append((delivery, outcome))
    return outcomes, list(updates.values())
