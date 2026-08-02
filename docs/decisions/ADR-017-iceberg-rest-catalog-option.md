# ADR-017: Iceberg REST Catalog Option

**Status:** Accepted (catalog boundary — I1/I2); REST implementation deferred to I3/I4  
**Date:** 2026-08-02  
**Version:** v2.7

## Context

SoloLakehouse uses Hive Metastore as the default Iceberg catalog backend. v2.7
must demonstrate catalog portability without replacing the protected v2.5
Compose stack. Before comparing REST Catalog or managed alternatives, the
codebase needs an explicit backend-selection seam rather than a hard-coded
`HiveCatalog` constructor in `ingestion/iceberg_io.py`.

## Decision

1. Introduce `ingestion/catalog_boundary.py` as the **only** place that chooses
   and constructs a pyiceberg catalog backend.
2. Keep `ingestion.iceberg_io.get_catalog()` as the public pipeline entry point,
   delegating to the boundary with optional overrides for tests and Dagster
   resources.
3. Default backend remains **`hive`** via `ICEBERG_CATALOG_BACKEND=hive`
   (unchanged v2.5 behavior).
4. Add **`rest`** as a selectable backend that **fails loudly** until v2.7 tasks
   `I3`/`I4` wire a reference REST implementation and interoperability proof.
5. Document the Hive vs REST paths in [`docs/catalog-boundary.md`](../catalog-boundary.md).

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `ICEBERG_CATALOG_BACKEND` | `hive` | Backend selector (`hive` or `rest`) |
| `ICEBERG_CATALOG_NAME` | `hive` | pyiceberg catalog name |
| `ICEBERG_REST_URI` | unset | Required when backend is `rest` |
| Existing Hive/S3 settings | unchanged | Warehouse + credentials |

## Consequences

- v2.7 interoperability work can swap backends without touching collectors,
  transforms, or governance modules.
- The default `make up` / `make demo` path is unchanged.
- REST Catalog does **not** enter `docker-compose.yml` until I3/I4 explicitly add
  an optional profile or reference path.

## Alternatives Considered

- **Document-only portability claim** — rejected; roadmap requires a code seam.
- **Immediate REST Catalog in default Compose** — rejected; violates v2.5 runtime
  freeze and ADR scope reduction.
- **Glue as default local backend** — rejected; managed catalog is a deployment
  choice, not the reference stack.

## Related

- [`docs/catalog-boundary.md`](../catalog-boundary.md)
- v2.7 tasks `I3` (Polaris evaluation) and `I4` (minimal interoperability proof)
