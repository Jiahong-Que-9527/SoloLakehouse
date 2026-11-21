"""Transactional write port for the event state (sequence step 2).

The consumer persists the receipt, the history outcome and the state
mutation in one explicit transaction and acknowledges only after the
commit succeeds. The cloud delivery implements this port with one
BigQuery script; :class:`InMemoryStore` is the local fake the contract
tests run against. It can also simulate warehouse unavailability with
``fail_commits`` so retry behaviour is testable without Google Cloud.
"""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from aviation_events.envelope import Envelope
from aviation_events.reducer import EntityState

Clock = Callable[[], datetime]


class TransientError(RuntimeError):
    """The warehouse (or dead-letter sink) is temporarily unavailable."""


@dataclass(frozen=True)
class Receipt:
    """One row per processed event ID; the at-least-once dedup key."""

    event_id: str
    message_id: str
    outcome: str
    received_at: datetime


@dataclass(frozen=True)
class HistoryRow:
    """One row per accepted or ignored delivery (design section 3)."""

    event_id: str
    entity_id: str
    revision: int
    outcome: str
    message_id: str
    received_at: datetime


@dataclass(frozen=True)
class QuarantineRow:
    """A body routed to the dead-letter path, with its stable reason.

    Keyed by delivery (message ID) and reason, so a redelivered poison
    message bumps ``occurrences`` instead of adding rows — the record of
    repeated failure notifications the acceptance evidence asks for.
    """

    delivery_key: str
    reason: str
    body: str
    occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime


class _Transaction:
    """Buffers writes; :meth:`InMemoryStore.transaction` applies or discards."""

    def __init__(self, store: "InMemoryStore") -> None:
        self._store = store
        self._receipts: dict[str, Receipt] = {}
        self._states: dict[str, EntityState] = {}
        self._history: list[HistoryRow] = []
        self._quarantine: dict[tuple[str, str], QuarantineRow] = {}

    def receipt_exists(self, event_id: str) -> bool:
        return event_id in self._receipts or event_id in self._store._receipts

    def fetch_state(self, entity_id: str) -> EntityState | None:
        if entity_id in self._states:
            return self._states[entity_id]
        return self._store._states.get(entity_id)

    def put_state(self, state: EntityState) -> None:
        self._states[state.entity_id] = state

    def record_receipt(
        self, event: Envelope, outcome: str, message_id: str, received_at: datetime
    ) -> None:
        self._receipts[event.event_id] = Receipt(event.event_id, message_id, outcome, received_at)
        self._history.append(
            HistoryRow(
                event_id=event.event_id,
                entity_id=event.entity_id,
                revision=event.revision,
                outcome=outcome,
                message_id=message_id,
                received_at=received_at,
            )
        )

    def record_quarantine(
        self, delivery_key: str, reason: str, body: str, seen_at: datetime
    ) -> None:
        key = (delivery_key, reason)
        existing = self._quarantine.get(key) or self._store._quarantine.get(key)
        if existing is None:
            self._quarantine[key] = QuarantineRow(
                delivery_key=delivery_key,
                reason=reason,
                body=body,
                occurrences=1,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            )
            return
        bumped = QuarantineRow(
            delivery_key=existing.delivery_key,
            reason=existing.reason,
            body=existing.body,
            occurrences=existing.occurrences + 1,
            first_seen_at=existing.first_seen_at,
            last_seen_at=seen_at,
        )
        self._quarantine[key] = bumped


class InMemoryStore:
    """In-memory fake of the BigQuery script: buffered, all-or-nothing commits."""

    def __init__(self, *, fail_commits: int = 0) -> None:
        self._states: dict[str, EntityState] = {}
        self._receipts: dict[str, Receipt] = {}
        self._history: list[HistoryRow] = []
        self._quarantine: dict[tuple[str, str], QuarantineRow] = {}
        self._fail_commits = fail_commits
        self._depth = 0

    @contextmanager
    def transaction(self):
        if self._depth:
            raise RuntimeError("nested transactions are not supported")
        tx = _Transaction(self)
        self._depth += 1
        try:
            yield tx
        except BaseException:
            raise  # pending buffer is discarded; nothing was applied
        else:
            if self._fail_commits > 0:
                self._fail_commits -= 1
                raise TransientError("simulated warehouse commit failure")
            self._states.update(tx._states)
            self._receipts.update(tx._receipts)
            self._history.extend(tx._history)
            self._quarantine.update(tx._quarantine)
        finally:
            self._depth -= 1

    # Read views for tests and evidence queries.

    @property
    def states(self) -> dict[str, EntityState]:
        return dict(self._states)

    @property
    def receipts(self) -> dict[str, Receipt]:
        return dict(self._receipts)

    @property
    def history(self) -> tuple[HistoryRow, ...]:
        return tuple(self._history)

    @property
    def quarantine(self) -> tuple[QuarantineRow, ...]:
        return tuple(self._quarantine.values())


def system_clock() -> datetime:
    """Default receive timestamp source; tests inject a frozen clock."""
    return datetime.now(UTC)
