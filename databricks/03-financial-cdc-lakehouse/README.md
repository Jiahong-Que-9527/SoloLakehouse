# Financial CDC Lakehouse

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D03 · Planned** · [Databricks roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Maintain consistent Delta state from change records that can arrive late or more than once. Exercise historical corrections through financial observations and
withdrawals through synthetic financial transactions.

## Technical scope

Auto Loader, Structured Streaming, checkpoints and Delta MERGE.

## Input and output

- **Input.** Versioned synthetic insert, update and delete events with business keys and a deterministic change order. A financial observation fixture can reuse the [D01](../01-ecb-delta-lakehouse/README.md) key and column conventions.
- **Output.** A current-state Delta table, change and failure evidence, and an expected state for comparison with a full replay.

## Acceptance

1. Apply duplicates and out-of-order revisions. Confirm that a late older event cannot overwrite the latest value or reintroduce a deleted row.
2. Interrupt after a committed micro-batch and restart from the same checkpoint. Verify one effective application for each change.
3. Compare final state with a deterministic full replay. Record what the checkpoint tracks and what the merge logic enforces.

[Databricks Auto Loader](https://docs.databricks.com/gcp/en/ingestion/cloud-object-storage/auto-loader/file-events-explained)

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
