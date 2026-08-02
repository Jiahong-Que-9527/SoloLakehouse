# Apache Polaris Evaluation (v2.7 I3)

SoloLakehouse evaluates **Apache Polaris** as the first reference implementation
for the Iceberg REST Catalog path introduced in I1/I2. Polaris is **not** part of
the protected v2.5 default stack.

## Why Polaris

| Criterion | Assessment |
|---|---|
| **Open source** | Apache Software Foundation project (Apache-2.0) |
| **Protocol fit** | Implements the Iceberg REST Catalog OpenAPI |
| **pyiceberg support** | `pyiceberg.catalog.rest.RestCatalog` is already a project dependency |
| **Reference material** | Upstream ships Trino/Spark docker-compose guides |
| **Scope fit** | Catalog portability evidence without adding compute engines |

Alternatives considered for the reference path:

| Option | Why not first |
|---|---|
| **Nessie** | Strong Git-like branching; heavier operational model for a minimal REST proof |
| **Glue / Unity REST** | Managed cloud catalogs; contradicts on-prem reference stack goals |
| **Hive Metastore only** | Current v2.5 default; no REST interoperability evidence |

## Default stack vs optional Polaris profile

| Path | Compose | Catalog backend | When to use |
|---|---|---|---|
| **v2.5 protected baseline** | `make up` | `ICEBERG_CATALOG_BACKEND=hive` | Demo, pipeline, CI |
| **Optional REST reference** | `make polaris-up` | `ICEBERG_CATALOG_BACKEND=rest` | I4 interoperability drill only |

The optional profile lives in `docker/docker-compose.polaris.yml` with Compose profile
`polaris`. It does **not** modify `docker/docker-compose.yml` or the default
`COMPOSE_STACK` in the Makefile.

## Polaris REST endpoint shape

Polaris exposes the Iceberg REST API (typical local layout):

| Setting | Example |
|---|---|
| `ICEBERG_REST_URI` | `http://localhost:8181/api/catalog` |
| `ICEBERG_CATALOG_NAME` | Polaris catalog name after bootstrap (e.g. `quickstart_catalog`) |
| `ICEBERG_REST_CREDENTIAL` | OAuth client credentials as `client_id:client_secret` |
| `ICEBERG_REST_OAUTH2_URI` | Optional explicit token endpoint override |

pyiceberg constructs a `RestCatalog` through `ingestion/catalog_boundary.py`. S3/MinIO
settings (`MINIO_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `WAREHOUSE_URI`) remain
shared with the Hive path so both backends can target the same object-store layout.

## Bootstrap workflow (manual reference)

Polaris requires catalog/role bootstrap before pyiceberg can list namespaces. The
upstream project documents this through its getting-started guides:

- [Apache Polaris guides](https://polaris.apache.org/guides/)
- [Polaris + Trino quickstart](https://polaris.apache.org/guides/trino/)

Recommended SoloLakehouse drill:

1. `make up` — start the protected baseline (MinIO, Hive, Trino, Dagster, …).
2. `make polaris-up` — start Polaris on port `8181` only.
3. Bootstrap a Polaris catalog/namespace using upstream instructions (realm
   `POLARIS`, default dev credentials documented by Polaris).
4. Point env at REST:
   ```bash
   export ICEBERG_CATALOG_BACKEND=rest
   export ICEBERG_REST_URI=http://localhost:8181/api/catalog
   export ICEBERG_CATALOG_NAME=<polaris-catalog-name>
   export ICEBERG_REST_CREDENTIAL=root:secret
   ```
5. Run `make interoperability-proof LIVE_REST=1`.

## Limitations (explicit)

- Polaris is a **reference path**, not a production recommendation in this repo.
- OAuth/bootstrap steps are **not** automated in the default Makefile targets.
- Trino in the v2.5 stack still uses the Hive Iceberg catalog; switching Trino to
  REST is out of scope for I3/I4 and belongs to operational rollout planning.
- This evaluation does **not** claim regulatory certification or data-residency
  compliance — see `make sovereignty-report` for component-origin evidence only.

## Related

- [`docs/catalog-boundary.md`](catalog-boundary.md)
- [`docs/exit-playbook.md`](exit-playbook.md)
- [ADR-017](decisions/ADR-017-iceberg-rest-catalog-option.md)
