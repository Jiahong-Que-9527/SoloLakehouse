# OpenMetadata runtime notes

- **Compose file:** `docker/docker-compose.openmetadata.yml` (included by default in `make up`).
- **Start:** `make up` from the repository root.
- **UI:** http://localhost:8585 (default basic auth per OpenMetadata docs).
- **Env:** `docker/openmetadata/openmetadata.env` — generated from OpenMetadata 1.5.6 quickstart defaults; hosts patched to `om-mysql` / `om-elasticsearch`; `PIPELINE_SERVICE_CLIENT_ENABLED=false`.

## Trino connection in OpenMetadata

Add a Trino service with host `trino`, port `8080`, the effective `TRINO_USER`
from `.env` (default `sololakehouse`; otherwise derived from `PRODUCT_ID` unless
explicitly set), and catalogs `hive` and `iceberg`. Run metadata ingestion from
the UI.

For v2.6 lineage evidence, set `OPENMETADATA_TRINO_SERVICE_NAME` to that
service's name and set a local-only `OPENMETADATA_AUTH_TOKEN` with read access
to the ingested table. The `make lineage-evidence` command deliberately fails
without both values or without the cataloged table and owner.

## Verify

```bash
make verify
```

## Upstream reference

`upstream-docker-compose-1.5.6.yml` is a vendored copy of the upstream quickstart compose used to derive `openmetadata.env`.
