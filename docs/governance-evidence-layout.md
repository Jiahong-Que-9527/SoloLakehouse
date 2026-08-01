# Governance Evidence Layout

## Scope

This document defines the v2.6 stable evidence type and object layout. It does
not yet collect source data or write audit objects; those behaviors belong to
the Block H adapters and evidence CLI.

## Stable identity

`dataset_id` is the logical join key. Physical deployment values such as the
Trino table, object-store bucket, object path, and Iceberg snapshot are carried
as evidence and may change during a storage migration.

Each `LineageRecord` requires the v2.6 evidence tuple from
[`dataset-governance-naming.md`](dataset-governance-naming.md): runtime,
Dagster, OpenMetadata table FQN, Trino, object-storage, Iceberg, and timestamp
fields. Unknown fields, missing required values, unsafe object paths, and
timezone-free timestamps are rejected.

## Bundle layout

Future writers must place each evidence bundle under the configured audit
bucket using this bucket-relative path:

```text
lineage/<dataset_id>/<UTC-YYYY-MM-DD>/<dagster_run_id>/manifest.json
```

The manifest uses schema version `v1`, contains one `LineageRecord`, and stores
the SHA-256 digest of its canonical JSON. The model rejects a manifest whose
digest does not match its record.

## Audit-bucket Object Lock

The audit bucket is created with MinIO Object Lock enabled by
`scripts/init-minio.sh`:

| Setting | Default | Meaning |
|---|---|---|
| `AUDIT_OBJECT_LOCK_MODE` | `GOVERNANCE` | Default retention mode for new evidence objects |
| `AUDIT_OBJECT_LOCK_RETENTION` | `2555d` | Default retention period (~7 years) |

Object Lock must be enabled when the bucket is first created. If an older audit
bucket exists without Object Lock, `minio-init` fails loudly and instructs you to
run `make clean` before recreating the stack. `make verify` reads the bucket's
Object Lock configuration through the MinIO API.

This is a **local reference implementation** of write-once audit storage. It is
not a regulatory-compliance or enterprise WORM certification claim.

Use `make lineage-evidence DATASET_ID=<dataset_id> DAGSTER_RUN_ID=<run_id>` to
collect all three sources and write the manifest. The command emits no object
when OpenMetadata, Iceberg, Dagster, or the final audit write is incomplete.
