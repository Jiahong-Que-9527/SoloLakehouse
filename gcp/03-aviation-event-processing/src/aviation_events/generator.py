"""Seeded fixture batches (sequence step 1: expected state before publishing).

Two independently generated batches exercise the same envelope: synthetic
airport ground events (primary) and synthetic energy revisions in the G01
field style (comparison fixture). The scenario content is fixed so the
expected final state is known before anything is published — the
expectations live in ``tests/test_fixtures.py``, not here.

The seed only shuffles what is safe to shuffle: the order of independent
entities and the order of deliveries inside one phase. Phases stay
ordered because revision and conflict expectations depend on them. Any
seed therefore yields the same envelope multiset, the same final state
and the same outcome counts, with different delivery orders.
"""

import json
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    """One publishable delivery, as Pub/Sub would carry it."""

    message_id: str
    body: bytes


def _body(
    event_id: str,
    entity_id: str,
    event_type: str,
    event_time: str,
    revision: int,
    payload: dict,
) -> bytes:
    document = {
        "event_id": event_id,
        "entity_id": entity_id,
        "event_type": event_type,
        "event_time": event_time,
        "revision": revision,
        "schema_version": "1",
        "payload": payload,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _emit(phases_per_entity: list[list[list[bytes]]], seed: int) -> list[Message]:
    rng = random.Random(seed)
    entity_order = list(range(len(phases_per_entity)))
    rng.shuffle(entity_order)
    messages: list[Message] = []
    counter = 1
    for entity_index in entity_order:
        for phase in phases_per_entity[entity_index]:
            deliveries = list(phase)
            rng.shuffle(deliveries)
            for body in deliveries:
                messages.append(Message(f"m-{counter:04d}", body))
                counter += 1
    return messages


def airport_batch(seed: int) -> list[Message]:
    """Synthetic Frankfurt ground events for three flight legs, 2026-11-15.

    - ``LH123``: one clean revision chain, 1 to 4.
    - ``LH456``: the sequence from the implementation plan — revision 2
      applied, its event ID delivered a second time, an older revision 1,
      a conflicting revision 2 under a new event ID, a malformed envelope
      and a valid correction at revision 3.
    - ``LH789``: a revision 4 delivered before revisions 1-3, then an
      unknown event type at revision 5 that must not move state.
    """
    day = "2026-11-15"
    leg123 = "LH123-2026-11-15"
    leg456 = "LH456-2026-11-15"
    leg789 = "LH789-2026-11-15"

    # The malformed delivery: a structurally plausible body missing `payload`.
    malformed = json.dumps(
        {
            "event_id": "evt-456-e",
            "entity_id": leg456,
            "event_type": "unloading_started",
            "event_time": f"{day}T10:35:00Z",
            "revision": 2,
            "schema_version": "1",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    scenarios: list[list[list[bytes]]] = [
        [
            [_body("evt-123-a", leg123, "on_stand", f"{day}T05:55:00Z", 1, {"stand": "A01"})],
            [
                _body(
                    "evt-123-b",
                    leg123,
                    "unloading_started",
                    f"{day}T06:10:00Z",
                    2,
                    {"stand": "A01"},
                )
            ],
            [
                _body(
                    "evt-123-c",
                    leg123,
                    "cargo_unloading_complete",
                    f"{day}T06:40:00Z",
                    3,
                    {"stand": "A01"},
                )
            ],
            [
                _body(
                    "evt-123-d", leg123, "equipment_clear", f"{day}T06:50:00Z", 4, {"stand": "A01"}
                )
            ],
        ],
        [
            [
                _body(
                    "evt-456-b",
                    leg456,
                    "cargo_unloading_complete",
                    f"{day}T10:30:00Z",
                    2,
                    {"stand": "B12"},
                ),
                _body(
                    "evt-456-b",
                    leg456,
                    "cargo_unloading_complete",
                    f"{day}T10:30:00Z",
                    2,
                    {"stand": "B12"},
                ),
            ],
            [
                _body(
                    "evt-456-c",
                    leg456,
                    "unloading_started",
                    f"{day}T10:10:00Z",
                    1,
                    {"stand": "B12"},
                )
            ],
            [
                _body(
                    "evt-456-d",
                    leg456,
                    "cargo_unloading_complete",
                    f"{day}T10:30:00Z",
                    2,
                    {"stand": "B14"},
                )
            ],
            [malformed],
            [
                _body(
                    "evt-456-f", leg456, "equipment_clear", f"{day}T11:05:00Z", 3, {"stand": "B12"}
                )
            ],
        ],
        [
            [
                _body(
                    "evt-789-a", leg789, "equipment_clear", f"{day}T08:50:00Z", 4, {"stand": "A08"}
                )
            ],
            [
                _body("evt-789-b", leg789, "on_stand", f"{day}T08:00:00Z", 1, {"stand": "A08"}),
                _body(
                    "evt-789-c",
                    leg789,
                    "unloading_started",
                    f"{day}T08:15:00Z",
                    2,
                    {"stand": "A08"},
                ),
                _body(
                    "evt-789-d",
                    leg789,
                    "cargo_unloading_complete",
                    f"{day}T08:40:00Z",
                    3,
                    {"stand": "A08"},
                ),
            ],
            [_body("evt-789-z", leg789, "baggage_loaded", f"{day}T08:55:00Z", 5, {"cart": "C3"})],
        ],
    ]
    return _emit(scenarios, seed)


def energy_batch(seed: int) -> list[Message]:
    """Synthetic SMARD-style revisions; entity is ``area|metric|interval_start``."""
    metric = "DE|actual_load_mwh|2026-06-08T00:00:00Z"
    metric_b = "DE|actual_load_mwh|2026-06-08T00:15:00Z"
    metric_c = "DE|actual_load_mwh|2026-06-08T00:30:00Z"
    stamp = "2026-06-08T00:35:00Z"

    def revision_event(event_id: str, entity_id: str, revision: int, value: float) -> bytes:
        return _body(event_id, entity_id, "observation_revision", stamp, revision, {"value": value})

    scenarios: list[list[list[bytes]]] = [
        [
            [revision_event("evt-e-a1", metric, 2, 40125.5)],
            [revision_event("evt-e-a2", metric, 1, 40100.0)],
        ],
        [
            [revision_event("evt-e-b1", metric_b, 1, 39800.0)],
            [revision_event("evt-e-b2", metric_b, 1, 39800.0)],
        ],
        [
            [revision_event("evt-e-c1", metric_c, 1, 40200.0)],
            [revision_event("evt-e-c2", metric_c, 2, 40300.0)],
            [revision_event("evt-e-c3", metric_c, 3, 40350.0)],
            [revision_event("evt-e-c4", metric_c, 3, 40999.0)],
        ],
    ]
    return _emit(scenarios, seed)
