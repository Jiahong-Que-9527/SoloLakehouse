# Financial CDC Lakehouse implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** planned. [Brief](../README.md) · [Design](design.md)

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
