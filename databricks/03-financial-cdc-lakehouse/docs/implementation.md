# Financial CDC Lakehouse implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** accepted on Databricks Free Edition on 2026-11-24. [Brief](../README.md) · [Design](design.md)

## First delivery

Maintain a current-state Delta table from deterministic synthetic corrections and withdrawals. Start with isolated input, output and checkpoint locations, one writer and an independently calculated final state.

## Implementation sequence

1. For one transaction prepare insert sequence 1, update 2, duplicate 2, delete 4 and delayed update 3. Expect absence after the delete and delayed update. Then add insert 5 and expect one active row. Add an equal-sequence conflicting payload with an explicit reject expectation.

2. Keep the source files immutable and track ingestion offsets. Land events in Bronze and reduce each key by sequence before MERGE. Retain the highest applied sequence and tombstone across micro-batches so an absent current row cannot admit an older update.

3. Exercise identical duplicates, conflicting payloads and withdrawals across separate files and micro-batches. Verify current amount, history, rejects and the highest sequence for each key. Record how partial writes to state and history are detected and repaired on retry.

4. Stop after a committed batch, restart with the same checkpoint and compare with uninterrupted processing. Also interrupt after state mutation before the batch is acknowledged; verify history and reject records remain idempotent on retry.

5. Replay identical immutable files to a separate target and checkpoint. Compare normalized rows, sequences and totals by key, including deleted keys. Repeat with a synthetic observation correction using the D01 business key.

## Portfolio evidence

Evidence: one transaction timeline with offsets, sequence numbers and table versions. Document separately how file discovery advances and how business state survives redelivery. Link measured results from the brief after execution.

## Free Edition verification

Job `369469967455087` ran commit
`9cae23a53b1156005e91edc89549a8a562ff81cb` in
`workspace.ecb_d03_20261124_211650` on Serverless. Auto Loader read four immutable
JSONL files from the managed Unity Catalog Volume. A second
`availableNow` query applied Bronze deliveries through Delta MERGE.

| Case | Observed result |
|---|---|
| Commit then fail before checkpoint confirmation | The first job stopped after the next journal MERGE. Offset 1 existed, but only batch 0 was committed. Bronze and journal were both at version 2. |
| Restart in a different job run | The new job reopened the same checkpoint with the same query ID and a different run ID. Batch 1 was confirmed. State, history, rejects and Delta versions did not change during that replay. |
| Duplicate, out-of-order change and delete | Exactly two duplicate deliveries and two stale events were identified. After deleting `tx-focus` at sequence 4, the late update at sequence 3 did not restore it. Gold excluded both withdrawn transactions at that stage. |
| Higher-sequence insert and conflicting data | Sequence 5 restored `tx-focus` with EUR 17.00. The conflicting payload at sequence 5 was rejected, as was a different payload at sequence 2. `tx-withdrawn` retained its sequence-3 tombstone. |
| D01 business key | The observation `EXR.D.USD.EUR.SP00.A/2025-02-05` reached sequence 2 and USD 1.042500 per EUR. A redelivered sequence 1 did not undo it. |
| Independent comparison | The recovered stream, uninterrupted stream and full batch replay matched on every state key, sequence, tombstone and amount. Final Gold contained 145 active EUR transactions totaling EUR 36,071.90. Bronze held 190 deliveries, with 188 history records and two rejects. |

The source checkpoint records discovered files. The apply checkpoint
records delivered Bronze offsets. Delta's journal and MERGE preserve
business state and rejected deliveries when Spark redelivers an
unacknowledged batch.

[Expected failed run](https://dbc-7395c3c6-fdc9.cloud.databricks.com/?o=7474653372862099#job/369469967455087/run/1062713573466551) · [Successful recovery run](https://dbc-7395c3c6-fdc9.cloud.databricks.com/?o=7474653372862099#job/369469967455087/run/531861986471703) · [Structured acceptance evidence](../evidence/free-edition-acceptance.json)
