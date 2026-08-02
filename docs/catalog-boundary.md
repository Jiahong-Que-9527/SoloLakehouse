# Iceberg Catalog Boundary

SoloLakehouse routes every pyiceberg catalog construction through
`ingestion/catalog_boundary.py`. Pipeline code continues to call
`ingestion.iceberg_io.get_catalog()`, but the backend is now selected explicitly
instead of being hard-coded to Hive Metastore.

## Default path — Hive Metastore (`ICEBERG_CATALOG_BACKEND=hive`)

This is the protected v2.5 runtime path used by `make up`, Dagster, collectors,
transformations, and governance adapters today.

| Setting | Purpose |
|---|---|
| `ICEBERG_CATALOG_BACKEND=hive` | Select the Hive Metastore backend (default) |
| `ICEBERG_CATALOG_NAME` | pyiceberg catalog name (default `hive`) |
| `HIVE_METASTORE_URI` | Thrift URI for Hive Metastore |
| `WAREHOUSE_URI` / `DATA_BUCKET` | Iceberg warehouse location in MinIO |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Object-store credentials |

Behavior is unchanged from v2.5: pyiceberg constructs a `HiveCatalog` backed by
the existing Compose services.

## Planned path — Iceberg REST Catalog (`ICEBERG_CATALOG_BACKEND=rest`)

v2.7 adds an optional REST-catalog seam for openness evidence. It is **not**
enabled in the default Compose stack.

| Setting | Purpose |
|---|---|
| `ICEBERG_CATALOG_BACKEND=rest` | Select the REST backend (planned I3/I4) |
| `ICEBERG_REST_URI` | Base URI for the REST catalog service |
| Shared warehouse + S3 settings | Same object-store layout as the Hive path |

Selecting `rest` constructs a pyiceberg `RestCatalog` through `ingestion/catalog_boundary.py`.
Live namespace listing requires a bootstrapped REST catalog (see
[`docs/polaris-evaluation.md`](polaris-evaluation.md)) and:

```bash
make interoperability-proof LIVE_REST=1
```

## Why this boundary exists

- Keeps catalog choice out of collectors, transforms, and governance modules.
- Makes v2.7 interoperability work a backend swap rather than a pipeline rewrite.
- Preserves the v2.5 acceptance path unchanged when `ICEBERG_CATALOG_BACKEND` is
  unset or set to `hive`.

See also: [ADR-017](decisions/ADR-017-iceberg-rest-catalog-option.md).
