# Energy Event Pipeline

<!-- [房玄龄·2026-11-15] Define the G03 project brief. -->

**Milestone:** G03 in the [Google Cloud roadmap](../README.md). Planned.

Test how a GCP pipeline handles corrections to the load observations defined
by the [European Energy Pipeline](../european-energy-pipeline/README.md).
Publish synthetic events to Pub/Sub, process them with Cloud Run and verify
the resulting state in an isolated BigQuery table.

## Event and output

Each test event carries an event ID, an observation key, a revision, a
schema version and a value. The observation key identifies a metric,
market area and interval. A higher revision replaces a lower revision
for that observation. Duplicate delivery has the same final effect as a
single delivery.

## First delivery

1. Publish an original observation, a newer correction, a late older
   revision and a replay of the correction. Verify that the target holds
   one row for the observation with the newer value.
2. Introduce one transient processing failure and verify that a retry
   reaches the expected state.
3. Send a controlled failing event to the dead-letter path. Record the
   reason, fix the input and replay it. Verify that successful events
   and prior results can still be accounted for.
4. Save the input fixture, expected final rows and runtime evidence so a
   new test environment can replay the same cases.

[Pub/Sub message ordering and redelivery](https://docs.cloud.google.com/pubsub/docs/ordering)
