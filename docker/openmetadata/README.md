# OpenMetadata runtime notes

- **Compose file:** `docker/docker-compose.openmetadata.yml` (included by default in `make up`).
- **Start:** `make up` from the repository root.
- **UI:** http://localhost:8585 (default basic auth per OpenMetadata docs).
- **Env:** `docker/openmetadata/openmetadata.env` — generated from OpenMetadata 1.5.6 quickstart defaults; hosts patched to `om-mysql` / `om-elasticsearch`; `PIPELINE_SERVICE_CLIENT_ENABLED=false`.

## Trino connection in OpenMetadata

Add a Trino service with host `trino`, port `8080`, user `sololakehouse` (or your `TRINO_USER`), and catalogs `hive` and `iceberg`. Run metadata ingestion from the UI.

## Verify

```bash
make verify
```

## Upstream reference

`upstream-docker-compose-1.5.6.yml` is a vendored copy of the upstream quickstart compose used to derive `openmetadata.env`.
