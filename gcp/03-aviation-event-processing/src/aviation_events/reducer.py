"""Pure revision decision for one event against one state (design section 5).

The reducer is the local specification of the future BigQuery script's
rules 3–6. It never sees receipts: event-ID deduplication happens in the
consumer before the decision (rule 1), and envelope validity happens in
:mod:`aviation_events.envelope` (rule 2).

Decided here, per the implementation sequence:

- **Unknown event types** are recorded (receipt plus history row with
  outcome ``stored``) and never move state, whatever their revision.
- **Equal revision with an equal payload** is a duplicate of the business
  change under a new event ID: ack, no state change.
- **Equal revision with a different payload** is a conflict: record it,
  leave the state untouched, and dead-letter the body. It must not retry.
- Revisions are assigned by the fixture, so delivery order does not
  matter; a higher revision wins whenever it arrives.
"""

from dataclasses import dataclass
from datetime import datetime

from aviation_events.envelope import Envelope

AIRPORT_EVENT_TYPES = (
    "on_stand",
    "unloading_started",
    "cargo_unloading_complete",
    "equipment_clear",
)
ENERGY_EVENT_TYPES = ("observation_revision",)
KNOWN_EVENT_TYPES = frozenset(AIRPORT_EVENT_TYPES) | frozenset(ENERGY_EVENT_TYPES)

OUTCOME_APPLIED = "applied"
OUTCOME_IGNORED = "ignored"
OUTCOME_DUPLICATE = "duplicate"
OUTCOME_CONFLICT = "conflict"
OUTCOME_STORED = "stored"


@dataclass(frozen=True)
class EntityState:
    """One current row per entity: the winning event and its payload."""

    entity_id: str
    revision: int
    event_id: str
    event_type: str
    event_time: datetime
    payload: str  # canonical JSON of the winning payload


@dataclass(frozen=True)
class Decision:
    """What the store should do with one event.

    ``state`` is the replacement row for ``applied`` and ``None``
    otherwise. ``dead_letter`` marks a permanent failure that the
    consumer must publish to the dead-letter path before acknowledging.
    """

    outcome: str
    state: EntityState | None
    dead_letter: bool = False
    reason: str | None = None


def decide(event: Envelope, state: EntityState | None) -> Decision:
    """Fold one event into the current state of its entity."""
    if event.event_type not in KNOWN_EVENT_TYPES:
        return Decision(OUTCOME_STORED, None)

    if state is None or event.revision > state.revision:
        return Decision(
            OUTCOME_APPLIED,
            EntityState(
                entity_id=event.entity_id,
                revision=event.revision,
                event_id=event.event_id,
                event_type=event.event_type,
                event_time=event.event_time,
                payload=event.canonical_payload,
            ),
        )
    if event.revision < state.revision:
        return Decision(OUTCOME_IGNORED, None)
    if event.canonical_payload == state.payload:
        return Decision(OUTCOME_DUPLICATE, None)
    return Decision(
        OUTCOME_CONFLICT,
        None,
        dead_letter=True,
        reason=(
            f"revision {event.revision} of {event.entity_id} already stored "
            f"with a different payload (stored event {state.event_id})"
        ),
    )
