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

Use three layers of configuration language.

### Product-level object-store configuration

These values describe what the product entity needs from an object store. New
application-level code and docs should prefer these names.

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

## Current compatibility mapping

The v2.5 local reference stack currently uses MinIO and S3-compatible variables
together:

```bash
OBJECT_STORE_PROVIDER=minio
OBJECT_STORE_ENDPOINT=http://minio:9000
OBJECT_STORE_EXTERNAL_ENDPOINT=http://localhost:9000

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
entity configuration should introduce product-level object-store values first,
then map them into compatibility variables where the current stack requires
them.

## What changes during the first entity split

For FinLakehouse and Aviation Lakehouse, change entity identity and owned
storage names while keeping MinIO as provider.

Examples:

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

Do not replace MinIO in this step.

## What does not change during the first entity split

The initial split should not change:

- object-store provider implementation;
- S3/S3A protocol assumptions;
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
  `MLFLOW_ARTIFACT_BUCKET`, and `WAREHOUSE_URI` settings are defined;
- S3-compatible variables are explicitly documented as compatibility variables;
- MinIO-specific variables are limited to MinIO runtime configuration;
- entity split and object-store replacement are documented as separate changes;
- the future replacement path uses side-by-side migration and validation gates;
- dataset IDs and product identity are preserved across provider changes.
