# Design: Aviation Event Processing

**G03 · Design only.** No application code in this directory yet.

Accept synthetic operational events that may be duplicated, delayed, or invalid, and fold them into one current state per entity. The project proves idempotency, revision ordering, retry, and a dead-letter path. It does not prove throughput.

The project [brief](../README.md) adds a second fixture on the same envelope.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Transport | Pub/Sub topic, push or pull to a Cloud Run consumer. v1 uses pull so the test can nack on purpose. |
| Payload | One envelope for every fixture. Airport ground events are the primary fixture. Energy-metric revisions are the second. |
| Effect | At most one business change per `event_id`. State changes only when `revision` is strictly greater than the stored revision. |
| Exactly-once | Pub/Sub delivery is at-least-once. The consumer commits `event_id` and the state change in one BigQuery script. A retry of a committed id is an acknowledgement with no further write. |
| Permanent failure | Schema and contract failures go to the dead-letter topic with the error attached. They are not retried until they succeed. |
| Transient failure | A BigQuery error nacks the message. The subscription retries with a limit, then dead-letters. |
| Order | The design does not require ordered delivery. Tests pass when a later revision is delivered first. |
| Data | Synthetic only. No OpenSky connection and no production airport feed. |

## 2. Boundary

In scope: the envelope, a generator with a fixed seed, the consumer, current state, history, the dead-letter topic, and a replay command that republishes selected dead-letter messages.

Out of scope: a live ADS-B feed, a user interface, and cross-project coupling to the energy pipeline. The energy fixture reuses field names from G01 so a revision can be compared with a batch release. That comparison is a test, not a runtime dependency.

## 3. Architecture

```text
Seeded generator
       |
       v
Pub/Sub topic events
       |
       v
Cloud Run consumer
       |
       +--> BigQuery event_receipt      one row per event_id
       +--> BigQuery entity_state        one row per entity_id
       +--> BigQuery event_history       one row per accepted or ignored delivery
       |
       v
subscription retry, then dead-letter topic
       |
       v
replay command republishes the same event_id
```

## 4. Envelope

```json
{
  "event_id": "evt-000123",
  "entity_id": "LH123-2026-11-15",
  "event_type": "cargo_unloading_complete",
  "event_time": "2026-11-15T10:30:00Z",
  "revision": 3,
  "schema_version": "1",
  "payload": {}
}
```

`event_id` is unique in the producer's intent. `revision` is a positive integer for that `entity_id`, assigned by the fixture, not by arrival order. `event_time` is when the operation happened. The consumer also stores `received_at`.

Airport payload types for v1: `on_stand`, `unloading_started`, `cargo_unloading_complete`, `equipment_clear`. The energy fixture uses `entity_id` = `area|metric|interval_start` and a numeric `payload.value`. Unknown `event_type` values that match the envelope are stored and do not move state. A missing required field is a contract failure.

## 5. Behaviour

One BigQuery script does the whole decision:

1. If `event_id` is already in `event_receipt`, stop and ack.
2. If the envelope is invalid, write an error row and route the message to the dead-letter path. Do not change `entity_state`.
3. If there is no state, or `revision` is greater than the stored revision, replace `entity_state` and append history with `outcome=applied`.
4. If `revision` is lower, append history with `outcome=ignored` and leave state. Ack.
5. If `revision` is equal and the payload matches, treat it as a duplicate. Ack.
6. If `revision` is equal and the payload differs, append history with `outcome=conflict`, leave state, and dead-letter. Do not retry that body.

A crash after the script commits and before ack is safe: the redelivery finds `event_id` and acks. A crash before the script commits is safe: the retry runs the script again.

The dead-letter subscription keeps the original body and the error. Replay publishes that body back to `events`. The same `event_id` is the dedup key, so a replay after a successful commit does not apply twice.

## 6. Delivery and cost

Terraform creates the topics, subscriptions, dead-letter policy, consumer, tables, and the consumer identity. The generator is a test command, not a scheduled publisher. Experiments use tens of messages and then stop. Subscription retention is long enough to replay a failed test, not a permanent archive.

## 7. Acceptance

| Case | Required result |
|------|-----------------|
| Same `event_id` delivered three times | One receipt, one state change |
| Higher revision arrives first, then an older one | State stays on the higher revision |
| Missing required field | No state change, message on the dead-letter topic, error row kept |
| BigQuery unavailable once | Message is nacked, then applied once when the write succeeds |
| Poison message | Dead-lettered after the retry limit |
| Replay of an already applied id | State unchanged |
| Energy revision fixture | Same rules, expected final value per interval |

Record the subscription id, dead-letter message ids, and the final state query.

## 8. Handoff

G04 does not govern this topic. A later aviation workflow may reuse the envelope. It must bring its own fixture. This project does not read the Fraport Bronze store.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
