# Financial CDC Lakehouse

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D03 · Accepted on Databricks Free Edition (2026-11-24)** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

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

## Free Edition execution scope

- The seeded job writes immutable synthetic CDC files to a managed Unity Catalog Volume (`/Volumes/workspace/<schema>/cdc_events`) rather than an external cloud bucket.
- Driven via **Databricks CLI** (`databricks bundle` + Serverless job) using `availableNow=True` Structured Streaming `MERGE`, or the explicitly labeled batch-MERGE checkpoint fallback defined in [design.md](docs/design.md) if Free Edition restricts streaming features. See [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md).

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

[Live verification and run links](docs/implementation.md#free-edition-verification) · [Structured evidence](evidence/free-edition-acceptance.json)

## Run acceptance

From this directory in a clean Git checkout, use a fresh, dedicated schema
and an authenticated Free Edition profile.

```bash
schema="ecb_d03_$(date -u +%Y%m%d_%H%M%S)"
args=(-t dev -p slh-free --var "schema=$schema" --var "git_sha=$(git rev-parse HEAD)")
databricks bundle validate --strict "${args[@]}"
databricks bundle deploy "${args[@]}"
databricks bundle run "${args[@]}" -o json d03_financial_cdc
```

The first job intentionally fails with
`D03_INJECTED_AFTER_DELTA_COMMIT_BEFORE_CHECKPOINT`. It writes
`fault_receipt.json` in the primary checkpoint directory first. Once that
marker and the failed run are present, resume in a new job run with the same
bundle variables and schema.

```bash
databricks bundle run "${args[@]}" -o json d03_financial_cdc -- --phase resume_verify
```

The resumed job compares its result with an independent uninterrupted stream
and full batch replay. Both use separate tables and checkpoints. Runs leave
their Delta tables and checkpoints available for inspection. If the platform
rejects streaming, repeat both phases on a fresh schema, passing
`--mode batch` after the `--` separator each time. The evidence labels the
mode of every run.
