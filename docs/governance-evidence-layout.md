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
Dagster, Trino, object-storage, Iceberg, and timestamp fields. Unknown fields,
missing required values, unsafe object paths, and timezone-free timestamps are
rejected.

## Bundle layout

Future writers must place each evidence bundle under the configured audit
bucket using this bucket-relative path:

```text
lineage/<dataset_id>/<UTC-YYYY-MM-DD>/<dagster_run_id>/manifest.json
```

The manifest uses schema version `v1`, contains one `LineageRecord`, and stores
the SHA-256 digest of its canonical JSON. The model rejects a manifest whose
digest does not match its record. This makes the manifest ready for later
signing and immutable archival without claiming those capabilities yet.
