# Aviation Event Processing

<!-- [房玄龄·2026-11-15] Define the G03 project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G03 · Contract phase implemented locally (2026-11-21)** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Validate retries, duplicate delivery and late corrections in an event-driven system. Use synthetic energy revisions for comparison with G01 and synthetic
airport operational events to exercise the same delivery behavior.

**Status:** the local contract phase is done — envelope validation, the pure
revision reducer, a transactional store port, the ack/nack/dead-letter
consumer flow and the seeded airport + energy fixture batches (61 tests).
The [Terraform](infra/) for topics, subscriptions, tables and the consumer
job is written and validated; nothing is provisioned on Google Cloud yet —
deployment follows the [bootstrap sequence](infra/BOOTSTRAP.md) and the
[delivery playbook](../README.md#delivery-playbook-settled-by-g01--g02)
behind the owner's cost-gate approval.

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
