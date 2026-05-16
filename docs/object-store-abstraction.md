# Object Store Abstraction and MinIO Deferral

This document defines the object-store boundary for SoloLakehouse-derived
product entities.

The rule for the first entity split is:

```text
Split entities first, keep MinIO initially, and prepare configuration so the
object store can be replaced later through a separate side-by-side migration.
```

## Status

- Applies to: v2.5 entity-template preparation.
- Related task: Phase 1, "Decide What Not to Change Yet".
- Related issue: #11.
- Related ADR: [ADR-019](decisions/ADR-019-minio-seaweedfs-deferral.md).
- Current provider: MinIO.
- Runtime status: this is a contract document. The current v2.5 runtime now
  supports `DATA_BUCKET` and `WAREHOUSE_URI` for entity data and warehouse
  locations, with `BUCKET_NAME` retained as a compatibility alias. It still
  uses `MLFLOW_ARTIFACT_ROOT`, S3-compatible variables, and the current
  `mlflow-artifacts` default until the MLflow/audit parameterization work is
  implemented.

## Decision

MinIO remains the object-store implementation for the first FinLakehouse and
Aviation Lakehouse split.

Product-level architecture and documentation must still use S3-compatible
object-store concepts so future migrations do not require redesigning product
entities, dataset IDs, or governance evidence.

Do not combine these changes:

1. product entity split,
2. object-store provider replacement,
3. v2.6 governance evidence and audit hardening.

Each is a separate migration surface with its own validation gates.

## Configuration layers

Use explicit current-runtime, future-target, and compatibility/runtime-specific
configuration language.

### Current v2.5 runtime variables

These are the object-store related settings that are actually supported by the
current v2.5 runtime today.

| Current variable or default | Current consumer examples | Current behavior |
|---|---|---|
| `DATA_BUCKET` | Dagster `PipelineConfigResource`, Python pipeline helpers, MinIO init, verification, Trino registration | Entity data bucket for Bronze/Silver/Gold. Defaults to `sololakehouse`. |
| `BUCKET_NAME` | v2.5 compatibility alias for older deployments | Used only when `DATA_BUCKET` is unset. |
| `WAREHOUSE_URI` | Hive Metastore template and Trino Iceberg schema registration | Entity warehouse root. Defaults to `s3a://<DATA_BUCKET>/warehouse/`. |
| `MLFLOW_ARTIFACT_ROOT` | `docker/mlflow/entrypoint.sh` | MLflow default artifact root. Defaults to `s3://mlflow-artifacts/`. |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Trino, Hive Metastore, Dagster, MLflow/AWS SDK clients | S3-compatible credentials for current MinIO-backed clients. |
| `S3_ENDPOINT` | Hive Metastore S3A configuration and generic S3-compatible clients | S3-compatible endpoint, currently `http://minio:9000` in `.env.example`. |
| `MLFLOW_S3_ENDPOINT_URL` | MLflow artifact storage and Dagster runtime | MLflow S3 endpoint, currently `http://minio:9000`. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | boto3 / AWS SDK compatibility | Compatibility aliases for S3 credentials. |
| `MINIO_ENDPOINT` | Dagster Minio client defaults and current compose runtime | Current MinIO endpoint. |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO server bootstrap; fallback defaults for some Python clients | MinIO runtime credentials for local reference use. |
| `sololakehouse` and `mlflow-artifacts` buckets | MinIO init and verification scripts | Current local default buckets created by `scripts/init-minio.sh` and checked by `scripts/verify-setup.py`. |

### Future product-level object-store contract targets

These values describe what a product entity should eventually need from an
object store. New application-level code and docs should prefer these names.
`DATA_BUCKET` and `WAREHOUSE_URI` are active in v2.5; the remaining product-level
storage names become active as their runtime work lands.

| Variable | Purpose | Example |
|---|---|---|
| `OBJECT_STORE_PROVIDER` | Provider name for the current deployment. | `minio` |
| `OBJECT_STORE_ENDPOINT` | Internal endpoint used by stack services. | `http://minio:9000` |
| `OBJECT_STORE_EXTERNAL_ENDPOINT` | Operator/client endpoint outside Docker. | `http://localhost:9000` |
| `OBJECT_STORE_ACCESS_KEY` | Product-level access key, if separated from S3 compatibility vars. | Entity secret |
| `OBJECT_STORE_SECRET_KEY` | Product-level secret key, if separated from S3 compatibility vars. | Entity secret |
| `DATA_BUCKET` | Entity data bucket for Bronze/Silver/Gold and warehouse data. | `finlakehouse-data` |
| `AUDIT_BUCKET` | Entity audit/evidence bucket reserved for v2.6+. | `finlakehouse-audit` |
| `MLFLOW_ARTIFACT_BUCKET` | Entity MLflow artifact bucket. | `finlakehouse-mlflow` |
| `WAREHOUSE_URI` | Hive/Trino warehouse root. | `s3a://finlakehouse-data/warehouse/` |

`OBJECT_STORE_PROVIDER` is a deployment detail. It must not be used as product
identity, dataset namespace, or owner metadata.

The target variables above become active only when the corresponding runtime
components are parameterized. Use `DATA_BUCKET` and `WAREHOUSE_URI` for entity
data and warehouse locations today, while MLflow and audit storage still follow
the compatibility notes below.

### Compatibility mapping from current to future variables

This table defines the intended migration path.

| Current v2.5 setting | Future entity-level target | Migration note |
|---|---|---|
| `BUCKET_NAME=sololakehouse` | `DATA_BUCKET=<product_id>-data` | `DATA_BUCKET` is now preferred. `BUCKET_NAME` remains a compatibility alias when `DATA_BUCKET` is unset. |
| hardcoded/default `sololakehouse` bucket in Python helpers and scripts | `DATA_BUCKET` | Runtime helpers now resolve through `storage_config.get_data_bucket()` while preserving the `sololakehouse` default. |
| `MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts/` | `MLFLOW_ARTIFACT_BUCKET=<product_id>-mlflow` plus an artifact root derived from it | Future #6 work should decide whether the active runtime keeps root URI config or derives it from the bucket variable. |
| `mlflow-artifacts` bucket | `MLFLOW_ARTIFACT_BUCKET` | Future bucket initialization should create the entity MLflow bucket. |
| no active v2.5 audit bucket variable | `AUDIT_BUCKET=<product_id>-audit` | Reserved for v2.6+ governance evidence; documenting it does not enable audit writes in v2.5. |
| `s3a://sololakehouse/warehouse/` in Hive Metastore template | `WAREHOUSE_URI=s3a://<data_bucket>/warehouse/` | `WAREHOUSE_URI` now drives the Hive warehouse template and Trino Iceberg schema location. |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `OBJECT_STORE_ACCESS_KEY` / `OBJECT_STORE_SECRET_KEY`, mapped back to S3 compatibility vars | Current clients still consume S3-compatible names. |
| `S3_ENDPOINT`, `MLFLOW_S3_ENDPOINT_URL`, `MINIO_ENDPOINT` | `OBJECT_STORE_ENDPOINT`, mapped back where clients require legacy names | Endpoint consolidation is future runtime parameterization work. |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO-only runtime settings, not product-level identity | Keep these names for MinIO server bootstrap while MinIO is the provider. |

### S3-compatible client configuration

These values are compatibility variables consumed by current libraries and
services. They may remain while clients still speak S3/S3A.

| Variable | Current consumer examples | Notes |
|---|---|---|
| `S3_ACCESS_KEY` | Trino, Hive Metastore, Dagster, MLflow/AWS SDK clients | Can be populated from `OBJECT_STORE_ACCESS_KEY` later. |
| `S3_SECRET_KEY` | Trino, Hive Metastore, Dagster, MLflow/AWS SDK clients | Can be populated from `OBJECT_STORE_SECRET_KEY` later. |
| `S3_ENDPOINT` | S3-compatible clients that need a generic endpoint | Should align with `OBJECT_STORE_ENDPOINT`. |
| `MLFLOW_S3_ENDPOINT_URL` | MLflow artifact storage | Should align with `OBJECT_STORE_ENDPOINT`. |
| `AWS_ACCESS_KEY_ID` | boto3 / AWS SDK compatibility | Compatibility alias for the active object-store access key. |
| `AWS_SECRET_ACCESS_KEY` | boto3 / AWS SDK compatibility | Compatibility alias for the active object-store secret key. |

These names are not product identity either. They describe a protocol/client
surface.

### MinIO-specific runtime configuration

Use MinIO-specific names only where the runtime is genuinely configuring MinIO
itself.

| Variable | Purpose |
|---|---|
| `MINIO_ROOT_USER` | MinIO server bootstrap/root user. |
| `MINIO_ROOT_PASSWORD` | MinIO server bootstrap/root password. |
| `MINIO_ENDPOINT` | Legacy/local MinIO endpoint used by current Python defaults. |
| `MINIO_API_PORT` | Host port for the MinIO S3 API. |
| `MINIO_CONSOLE_PORT` | Host port for the MinIO console. |

New product-facing code should avoid adding new `MINIO_*` variables unless the
setting cannot apply to another S3-compatible provider.

## Current compatibility example

The v2.5 local reference stack currently uses MinIO and S3-compatible variables
together:

```bash
OBJECT_STORE_PROVIDER=minio
OBJECT_STORE_ENDPOINT=http://minio:9000
OBJECT_STORE_EXTERNAL_ENDPOINT=http://localhost:9000

# Current active client/runtime variables:
BUCKET_NAME=sololakehouse
MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts/
S3_ENDPOINT=http://minio:9000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000

MINIO_ROOT_USER=sololakehouse
MINIO_ROOT_PASSWORD=sololakehouse123
S3_ACCESS_KEY=sololakehouse
S3_SECRET_KEY=sololakehouse123
AWS_ACCESS_KEY_ID=sololakehouse
AWS_SECRET_ACCESS_KEY=sololakehouse123
```

For the initial product entities, the credentials may still be wired through the
existing S3/MinIO variables. The important boundary is naming and ownership:
future entity configuration should introduce product-level object-store values
first, then map them into compatibility variables where the current stack
requires them.

## What changes during the first entity split

For FinLakehouse and Aviation Lakehouse, the target contract changes entity
identity and owned storage names while keeping MinIO as provider.

Target examples for issue #4 and related storage parameterization:

```bash
# FinLakehouse
PRODUCT_ID=finlakehouse
OBJECT_STORE_PROVIDER=minio
DATA_BUCKET=finlakehouse-data
AUDIT_BUCKET=finlakehouse-audit
MLFLOW_ARTIFACT_BUCKET=finlakehouse-mlflow
WAREHOUSE_URI=s3a://finlakehouse-data/warehouse/

# Aviation Lakehouse
PRODUCT_ID=aviation-lakehouse
OBJECT_STORE_PROVIDER=minio
DATA_BUCKET=aviation-lakehouse-data
AUDIT_BUCKET=aviation-lakehouse-audit
MLFLOW_ARTIFACT_BUCKET=aviation-lakehouse-mlflow
WAREHOUSE_URI=s3a://aviation-lakehouse-data/warehouse/
```

`DATA_BUCKET` and `WAREHOUSE_URI` are active for the v2.5 data/warehouse path.
`AUDIT_BUCKET` and `MLFLOW_ARTIFACT_BUCKET` remain contract targets until their
runtime parameterization work lands. Do not replace MinIO in this step.

## What does not change during the first entity split

The initial split should not change:

- object-store provider implementation;
- S3/S3A protocol assumptions;
- current `BUCKET_NAME` / `MLFLOW_ARTIFACT_ROOT` behavior until their
  parameterization issues are implemented;
- Trino/Hive S3 connector behavior;
- MLflow artifact protocol;
- Iceberg table format;
- governance/audit WORM behavior beyond reserving `AUDIT_BUCKET`;
- object-store migration runbooks beyond documenting the future path.

## Future object-store replacement boundary

Object-store replacement is a later side-by-side migration, not a first split
task.

Target flow:

```text
old entity with MinIO
        |
        v
new entity with target S3-compatible object store
        |
        v
mirror object data
        |
        v
recreate or re-register warehouse/catalog/table metadata
        |
        v
run full pipeline and governance evidence validation
        |
        v
cut over
        |
        v
retain old MinIO runtime read-only for rollback
```

Validation gates for the replacement migration:

- target object store supports required S3 operations;
- Trino can read and write through the target endpoint;
- Hive Metastore warehouse paths point to the target warehouse URI;
- Dagster assets can read and write Bronze/Silver/Gold objects;
- MLflow can write and read artifacts;
- OpenMetadata ingests the expected Trino datasets under the entity service
  name;
- Superset can query entity Gold tables through Trino;
- expected object counts and content checks match after mirror;
- Iceberg Gold is rebuilt or re-registered instead of blindly reusing stale
  metadata paths;
- audit bucket immutability expectations are validated if enabled;
- old MinIO is retained read-only until rollback risk is acceptable.

## Impact on dataset and governance identity

Object-store replacement must not rename governed datasets.

Preserve:

- `PRODUCT_ID`
- `DATASET_NAMESPACE`
- logical dataset IDs such as `fin.ecb_dax_features_gold`
- Dagster asset names unless the pipeline semantics change
- OpenMetadata logical service naming convention, even if the service endpoint
  changes

Update:

- `OBJECT_STORE_PROVIDER`
- object-store endpoint values
- bucket names if needed
- `WAREHOUSE_URI`
- Trino catalog/schema/table locations
- OpenMetadata physical table FQNs if service/table names change
- backup and restore runbooks
- lineage evidence physical fields

See [Dataset ID and Governance Naming Convention](dataset-governance-naming.md)
for the stable logical ID rules.

## Acceptance checklist

The object-store boundary is prepared when:

- docs describe MinIO as current provider, not product identity;
- product-level `OBJECT_STORE_*`, `DATA_BUCKET`, `AUDIT_BUCKET`,
  `MLFLOW_ARTIFACT_BUCKET`, and `WAREHOUSE_URI` settings are defined as contract
  targets, with `DATA_BUCKET` and `WAREHOUSE_URI` active in the v2.5 runtime;
- current v2.5 runtime variables (`BUCKET_NAME`, `MLFLOW_ARTIFACT_ROOT`,
  S3-compatible settings, and current default bucket/warehouse mappings) are
  documented separately from future entity-level targets;
- compatibility mapping from current variables to future target variables is
  documented;
- S3-compatible variables are explicitly documented as compatibility variables;
- MinIO-specific variables are limited to MinIO runtime configuration;
- entity split and object-store replacement are documented as separate changes;
- the future replacement path uses side-by-side migration and validation gates;
- dataset IDs and product identity are preserved across provider changes.
