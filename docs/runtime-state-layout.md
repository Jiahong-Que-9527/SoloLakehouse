# Entity Runtime State Layout

This document defines where runtime state lives for SoloLakehouse-derived
product entities.

It keeps the local v2.5 reference layout intact while documenting the host layout
recommended for continuously operated entities such as FinLakehouse and Aviation
Lakehouse.

## Status

- Applies to: v2.5 entity-template preparation.
- Related issue: #7.
- Related docs:
  - [Product Entity Contract](product-entity-contract.md)
  - [Object Store Abstraction and MinIO Deferral](object-store-abstraction.md)
  - [Entity Backup and Restore Runbook](entity-backup-restore-runbook.md)
  - [Deployment Guide](deployment.md)

## Principles

1. A product entity owns its runtime state. FinLakehouse state must not be mixed
   with Aviation Lakehouse state.
2. Code/release artifacts, runtime data, backups, logs, and secrets/config have
   separate host locations.
3. The local reference runtime may continue to use repository-local
   `docker/data/` bind mounts.
4. Long-running product entities should use an entity-owned root under
   `/opt/<product_id>/`.
5. Side-by-side upgrades create a new runtime root beside the old one. Do not
   mutate the old runtime in place until cutover and rollback decisions are
   complete.

## Current local reference layout

The v2.5 local reference stack stores durable bind-mounted state under the
repository:

```text
<repo>/
  .env
  docker/
    data/
      minio/
      postgres/
      dagster/
      om-mysql/
      om-elasticsearch/
```

This remains the supported local developer/demo layout. It is intentionally
simple: clone the repo, create `.env`, run `make up`, and all local state stays
inside the checkout under `docker/data/`.

Current bind-mount ownership:

| Path | Owner / service | State class | Backup relevance |
|---|---|---|---|
| `docker/data/minio` | MinIO | Object data for data and MLflow buckets | Critical |
| `docker/data/postgres` | PostgreSQL | Hive Metastore, MLflow, Dagster, Superset databases | Critical |
| `docker/data/dagster` | Dagster | Local Dagster instance storage not in PostgreSQL | Useful for diagnostics |
| `docker/data/om-mysql` | OpenMetadata MySQL | OpenMetadata application metadata | Critical if preserving catalog history |
| `docker/data/om-elasticsearch` | OpenMetadata Elasticsearch | Search index | Rebuildable if OpenMetadata can re-index; otherwise backup for faster restore |
| `.env` | Runtime operator | Local secrets/config | Critical; handle as secret material |

`make clean` is destructive for `docker/data/*`. Use it only for local reset,
not for product entity maintenance.

## Product entity host layout

For a continuously operated product entity, use a host root owned by that entity:

```text
/opt/<product_id>/
  app/        # checked-out code or release artifact
  data/       # bind-mounted runtime state
  backup/     # local backup staging and restore-drill inputs
  logs/       # optional host-level logs and command transcripts
  .env        # entity-specific configuration and secrets
  releases/   # optional immutable release snapshots or deployment metadata
```

Examples:

```text
/opt/finlakehouse/
/opt/aviation-lakehouse/
```

Recommended ownership:

| Path | Purpose | Notes |
|---|---|---|
| `/opt/<product_id>/app/` | Active code checkout or unpacked release artifact | Contains Makefile, Docker Compose files, docs, scripts, and application code. |
| `/opt/<product_id>/data/` | Runtime bind mounts | Equivalent to local `docker/data/`, but outside the repo tree for product operation. |
| `/opt/<product_id>/backup/` | Local backup staging | Destination for object-store mirrors, database dumps, metadata exports, and restore drill inputs. |
| `/opt/<product_id>/logs/` | Host-level logs | Optional. Useful for `make up`, backup, restore, migration, and incident command logs. |
| `/opt/<product_id>/.env` | Entity runtime configuration | Secrets/config for one entity only. Do not share across product entities. |
| `/opt/<product_id>/releases/` | Release metadata or immutable snapshots | Optional but useful for side-by-side upgrades and rollback records. |

## Product entity bind-mount layout

When product entities stop using repository-local `docker/data/`, mirror the
current state classes under `/opt/<product_id>/data/`:

```text
/opt/<product_id>/data/
  minio/
  postgres/
  dagster/
  om-mysql/
  om-elasticsearch/
  superset/          # optional if Superset state is split from PostgreSQL later
```

Mapping from current local layout:

| Local reference path | Product entity path | Notes |
|---|---|---|
| `<repo>/docker/data/minio` | `/opt/<product_id>/data/minio` | Object-store state while MinIO remains provider. |
| `<repo>/docker/data/postgres` | `/opt/<product_id>/data/postgres` | PostgreSQL cluster state for Hive Metastore, MLflow, Dagster, Superset. |
| `<repo>/docker/data/dagster` | `/opt/<product_id>/data/dagster` | Dagster local storage and diagnostics. |
| `<repo>/docker/data/om-mysql` | `/opt/<product_id>/data/om-mysql` | OpenMetadata application DB state. |
| `<repo>/docker/data/om-elasticsearch` | `/opt/<product_id>/data/om-elasticsearch` | OpenMetadata search state. |

This document defines the target ownership model. It does not change current
Compose bind mounts yet. If a product deployment moves bind mounts outside the
repository, update Compose paths or deployment wrappers in the same change and
record the new paths in the entity runbook.

## `.env` location and handling

Local reference:

```text
<repo>/.env
```

Product entity:

```text
/opt/<product_id>/.env
```

Rules:

- `.env` belongs to exactly one entity.
- `.env` is secret-bearing configuration and must not be committed.
- Backup `.env` with release metadata, but store it as secret material.
- Keep entity identity values in `.env`: `PRODUCT_ID`, display name, domain,
  environment, runtime version, and service identity values.
- Keep storage/provider values in `.env`: object-store endpoint/credentials,
  bucket names, warehouse URI, and MLflow artifact settings once implemented.
- Do not reuse one entity `.env` for another entity by editing only
  `PRODUCT_ID`; create a new file and review every credential, bucket, service,
  and backup path.

### Loading the product-level `.env` from `app/`

The repository `Makefile` defaults to `ENV_FILE=.env`. If an operator runs
commands from `/opt/<product_id>/app/`, that default points at
`/opt/<product_id>/app/.env`, not the product-level
`/opt/<product_id>/.env`.

Preferred operator command:

```bash
cd /opt/<product_id>/app
ENV_FILE=../.env make up
ENV_FILE=../.env make verify
ENV_FILE=../.env make demo
```

This keeps the secret-bearing runtime configuration outside the active app
checkout while using the existing Makefile contract.

Acceptable alternatives:

1. Create a product-level wrapper script, for example
   `/opt/<product_id>/bin/slh`, that runs `make ENV_FILE=/opt/<product_id>/.env
   ...` from the active app directory.
2. Create a symlink from `/opt/<product_id>/app/.env` to
   `/opt/<product_id>/.env` if the operational model intentionally keeps a
   checkout-local `.env` path.
3. Copy `.env` into the app path only when the copy is intentionally managed as
   secret material and kept in sync with the product-level file.

Without one of these strategies, a product deployment may start with missing
configuration or with stale/default values from the app checkout.

## Side-by-side upgrade layout

Side-by-side upgrades should create a new runtime root rather than mutating the
old root in place.

Preferred host shape:

```text
/opt/finlakehouse/
  current -> /opt/finlakehouse/releases/slh-v2.5.1
  releases/
    slh-v2.5.1/
      app/
      data/
      .env
    slh-v2.6.0-candidate/
      app/
      data/
      .env
  backup/
  logs/
```

Simpler acceptable shape for small deployments:

```text
/opt/finlakehouse-v2.5/
/opt/finlakehouse-v2.6-candidate/
```

Rules:

- Old runtime remains available until validation and cutover decisions are
  recorded.
- New runtime gets its own `app/`, `data/`, and `.env`.
- Copy or rebuild state according to the migration plan; do not share writable
  bind mounts between old and new runtimes.
- Keep old runtime read-only after cutover until rollback risk is acceptable.
- Store migration logs, copy manifests, and validation reports under the
  entity backup/logs area.

## State classification

Use this classification for backup/restore and side-by-side planning. The
operator procedure is in
[Entity Backup and Restore Runbook](entity-backup-restore-runbook.md).

| State | Location | Preferred migration action |
|---|---|---|
| Code/release artifact | `app/` or `releases/<version>/app/` | Deploy fresh from tag/release artifact. |
| Entity config/secrets | `.env` | Copy securely and review all entity-specific values. |
| MinIO object data | `data/minio/` or object-store mirror | Mirror data buckets and artifact buckets; preserve object names. |
| PostgreSQL databases | `data/postgres/` plus logical dumps | Prefer logical dumps for restore drills; avoid blind cluster copy across major versions. |
| Dagster run history | PostgreSQL + `data/dagster/` | Archive/export where needed; do not require old run history inside new scheduler. |
| OpenMetadata MySQL | `data/om-mysql/` or export | Restore or re-ingest depending on migration scope. |
| OpenMetadata Elasticsearch | `data/om-elasticsearch/` | Rebuild if possible; backup if preserving search state matters. |
| Superset metadata | PostgreSQL `superset_metadata` | Export/import dashboards and validate Trino connections after restore. |
| Host logs | `logs/` | Keep with migration/incident evidence. |
| Backup staging | `backup/` | Never mount as a writable service data directory. |

## Acceptance checklist

Runtime state ownership is documented when:

- each product entity has a recommended `/opt/<product_id>/` root;
- code, runtime data, backups, logs, and `.env` have distinct locations;
- current `docker/data/` bind mounts are mapped to entity-owned paths;
- entity `.env` location and secret-handling rules are clear;
- side-by-side upgrade layouts prevent old and new runtimes from sharing
  writable state;
- backup/restore planning can use the state classification above.
