# Design: Financial CDC Lakehouse

**D03 · Implemented.** Auto Loader, Delta MERGE and restart evidence run as a bundled workspace job.

Turn an append-only stream of synthetic transaction changes into one current row per transaction, including updates and deletes, and recover that state after a checkpoint restart. The project proves incremental state. It does not prove a CDC product inside Auto Loader.

The project [brief](../README.md) adds the observation-key fixture.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Source | A seeded Python generator writes CDC files. The seed is part of the fixture so a replay is deterministic. |
| Ingest | Auto Loader discovers new files and appends them to Bronze. It does not apply updates or deletes. |
| State | A Structured Streaming query reconciles Bronze against a Delta journal in `foreachBatch`. Current state, history and rejects are views over the journal. |
| Apply rule | A change applies only when its `sequence_number` is strictly greater than the sequence stored for that transaction. |
| Delete | A winning `DELETE` removes the current row and writes a tombstone in history. A later higher sequence may insert the transaction again. A lower sequence must not bring it back. |
| Duplicate | The same `(transaction_id, sequence_number)` is a no-op, whether it arrives twice in one file or in two files. |
| Conflict | The same sequence with a different payload is not applied. It is appended to `cdc_reject`. |
| AUTO CDC | Compared in this design and not shipped. v1 has one writer, the MERGE query, so the tests have one definition of "applied". |
| Recovery | Checkpoint and Bronze offsets are the ingest position. The MERGE condition is what prevents a second effect. Both are required. |
| Second fixture | Observation corrections use `(series_key, observation_date)` from D01 as `transaction_id` and the same sequence rule. |

## 2. Boundary

In scope: the generator, file landing, Bronze append, current state, history, checkpoint restart, and a full-replay comparison.

Out of scope: a real core-banking feed, Auto Loader as the state engine, and Unity Catalog roles. The job runs in a schema this project owns.

## 3. Architecture

```text
Seeded generator
       |
       v
CDC files, append-only
       |
       v
Auto Loader -> bronze.cdc_event
       |
       v
Streaming MERGE
       |
       +--> silver.current_transaction
       +--> silver.transaction_history
       +--> silver.cdc_reject
       |
       v
gold.transaction_metrics   counts and amounts from current rows only
```

## 4. Event contract

```json
{
  "transaction_id": "tx-10001",
  "operation": "UPDATE",
  "sequence_number": 3,
  "status": "COMPLETED",
  "amount": "250.00",
  "currency": "EUR",
  "event_time": "2026-11-15T10:30:00Z"
}
```

`operation` is `INSERT`, `UPDATE`, or `DELETE`. `sequence_number` is a positive integer from the source fixture, not from file arrival. `event_time` is stored and is not the ordering key.

`current_transaction` holds the winning payload and `sequence_number`. `transaction_history` holds every applied change and every ignored lower sequence, with `outcome` of `applied` or `ignored`.

## 5. Behaviour

The business key is `(kind, key)`. The journal stores one state row per
business key and one outcome per immutable file name and row ordinal. The
`MERGE` writes both row types in a single Delta transaction, using a separate
row identity for each. The state row retains the highest sequence even after
a delete. The current view excludes tombstones and non-transaction records.
This avoids a partial commit between state, history and rejects.

For each business key:

- No stored state for the key, and the change is not a delete: insert.
- No stored state for the key, and the change is a delete: record the tombstone in history, do not insert a current row.
- Incoming sequence is greater, operation is not delete: update the current row.
- Incoming sequence is greater, operation is delete: delete the current row and record the tombstone.
- Incoming sequence is lower or equal with the same payload: append `ignored` or count it as a duplicate. Do not change current state.
- Incoming sequence is equal and the payload differs: append `cdc_reject`. Do not change current state.

Checkpoint restart: stop the query after a committed micro-batch and start
it again from the same checkpoint. The acceptance also raises an intentional
error immediately after the next Delta MERGE, before the streaming checkpoint
can record the commit. On restart, already recorded deliveries produce no
additional Delta write. Each winning sequence has one applied history record.
Identical business duplicates from a different file have a separate delivery
outcome, while a replay of the same file and ordinal does not add one.

Full replay: run the same files through a batch MERGE with the same rule. Current keys, sequences, and amounts must match the streaming result. Gold metrics are computed only from `primary_current_transaction`, so a deleted transaction drops out of the amount.

## 6. Why Auto Loader is not the CDC engine

Auto Loader records which files have been ingested and appends their rows. It does not know `transaction_id` or `sequence_number`. A file that is ingested twice would duplicate Bronze unless the file commit is idempotent. The business rule still has to live in the MERGE. Shipping a second implementation with `AUTO CDC` would create two definitions of a winning row. The comparison stays in this document: `AUTO CDC` is appropriate later if its sequence column and delete handling are shown to match this MERGE on the same fixture. Until that spike is written up, it is not the path.

## 7. Delivery and cost

The generator writes a few hundred events to a managed Unity Catalog Volume. The reducer collects only this bounded acceptance fixture. The stream runs for the test and is then stopped. The checkpoint path is dedicated to this query. A second query does not share it.

If the workspace cannot run the structured-streaming query, the evidence says so and the batch MERGE plus a simulated restart (apply file 1, checkpoint marker, apply file 2) is the fallback. That fallback is labelled. It is not described as a streaming run.

## 8. Acceptance

| Case | Required result |
|------|-----------------|
| Duplicate event | Current row unchanged, one applied history row for that sequence |
| Older sequence after a newer one | Current row stays on the newer sequence |
| Delete | No current row, tombstone in history, Gold amount excludes it |
| Insert with a higher sequence after delete | Current row exists again |
| Equal sequence, different payload | Current row unchanged, row in `cdc_reject` |
| Stop after a committed batch and restart | Same current state as an uninterrupted run |
| Batch replay of the same files | Same current keys, sequences, and amounts |

Record the checkpoint path, the Bronze version, and the query id.

## 9. Handoff

D04 may grant an analyst read access to the `primary_gold_transaction_metrics` view and deny the `primary_bronze` table. This project does not create those grants.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
