"""G03 · Aviation Event Processing, local contract phase.

The package implements the decision semantics of the [design](../../docs/design.md)
against a transactional store port, so the BigQuery script and the Cloud Run
consumer can later be checked against the same fixtures:

- [envelope][]     wire contract; anything it rejects is a permanent failure
- [reducer][]      pure revision decision for one event against one state
- [store][]        the transactional write port and its in-memory fake
- [consumer][]     message-level flow: parse, dedup, decide, commit, ack
- [generator][]    seeded airport and energy fixture batches
"""

from aviation_events.consumer import EventConsumer, Outcome
from aviation_events.envelope import Envelope, EnvelopeError, parse_envelope
from aviation_events.reducer import (
    KNOWN_EVENT_TYPES,
    Decision,
    EntityState,
    decide,
)
from aviation_events.store import InMemoryStore, QuarantineRow, TransientError

__all__ = [
    "KNOWN_EVENT_TYPES",
    "Decision",
    "Envelope",
    "EnvelopeError",
    "EntityState",
    "EventConsumer",
    "InMemoryStore",
    "Outcome",
    "QuarantineRow",
    "TransientError",
    "decide",
    "parse_envelope",
]
