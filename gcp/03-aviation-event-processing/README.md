# Aviation Event Processing

<!-- [房玄龄·2026-11-15] Define the G03 project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G03 · Cloud delivery accepted 2026-11-21** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Cloud verification](docs/cloud-verification.md)

Validate retries, duplicate delivery and late corrections in an event-driven system. Use synthetic energy revisions for comparison with G01 and synthetic
airport operational events to exercise the same delivery behavior.

**Status:** accepted. The seeded airport and energy fixtures reconcile to
their expected final state in BigQuery through the one-script decision
store; duplicate, out-of-order, conflicting and malformed deliveries
behave exactly as the local contract specifies; retry, crash recovery,
dead-letter routing (both direct and via the subscription policy) and
replay are verified against the live resources. 24 events accounted for,
cost €0.00, all free-tier SKUs.

## Technical scope

Pub/Sub, Cloud Run, BigQuery and a Pub/Sub dead-letter topic.

## Input and output

- **Input.** Synthetic event batches with an event ID, entity or observation key, revision, event time, schema version and payload. Energy events reuse the metric schema from [G01](../01-european-energy-pipeline/README.md).
- **Output.** An isolated BigQuery result, processing logs and evidence of a dead-letter recovery. Each fixture has expected final rows.

## Acceptance

1. Send an original event, a correction, a late older revision and a duplicate. Verify that the expected revision is retained once per key.
2. Induce a transient failure and verify recovery through retry. Send a controlled poison message to the dead-letter path.
3. Correct and replay the failed event. Verify that successful events and final rows can be reconciled to the input.

[Pub/Sub message ordering and redelivery](https://docs.cloud.google.com/pubsub/docs/ordering)

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->
