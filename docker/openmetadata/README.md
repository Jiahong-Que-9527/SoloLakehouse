# OpenMetadata runtime notes

- **Compose file:** `docker/docker-compose.openmetadata.yml` (included by default in `make up`).
- **Start:** `make up` from the repository root.
- **UI:** http://localhost:8585. The Compose ports are bound to `127.0.0.1`;
  use an SSH tunnel when the runtime is on a VPS.
- **Env:** `docker/openmetadata/openmetadata.env` — generated from OpenMetadata 1.5.6 quickstart defaults; hosts patched to `om-mysql` / `om-elasticsearch`.
- **Ingestion runner:** `ingestion` is the bundled OpenMetadata 1.5.6 Airflow runner. It is required for the UI's **Test Connection** and metadata-ingestion workflows, and starts with `make up`.

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

## First administrator and recovery

`om-bootstrap` runs after the vendor migration and before the API server. It
idempotently restores OpenMetadata's required `emailConfiguration` setting,
which prevents an interrupted or migrated first startup from silently skipping
Basic-auth administrator creation. It does not reset metadata, users, or
credentials.

For a new deployment, set `OPENMETADATA_ADMIN_PRINCIPAL` in the local `.env`.
OpenMetadata creates `<principal>@open-metadata.org`; use its documented
initial Basic-auth password only through a local browser or SSH tunnel, then
change that password immediately under **Settings → Members → Admins**. Never
commit a password or an API token. `make verify` reports a failure if the API
is healthy but no configured administrator account exists.

For an existing instance that was affected by the missing-setting state, run
`make up` once. The bootstrap is non-destructive and the server then creates
the configured administrator on its next start.

## Upstream reference

`upstream-docker-compose-1.5.6.yml` is a vendored copy of the upstream quickstart compose used to derive `openmetadata.env`.
