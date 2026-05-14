# Product Entity Contract

This contract defines what makes one SoloLakehouse-derived product entity
complete enough to operate independently.

SoloLakehouse remains the upstream template. `finlakehouse` and
`aviation-lakehouse` are product instances created from that template, each with
its own identity, runtime state, buckets, metadata labels, schedules, evidence,
and upgrade lifecycle.

## Status

- Applies to: v2.5 entity-template preparation.
- Related task: Phase 1, "Define the Entity Contract".
- Related issue: #3.
- Current storage provider: MinIO, treated as the initial S3-compatible object
  store provider rather than as product identity.

## Contract principles

1. A product entity is identified by stable logical fields such as
   `PRODUCT_ID`, domain, dataset namespace, ownership metadata, and upgrade
   strategy.
2. Runtime hosts, bucket names, warehouse URIs, service URLs, bind mounts, and
   backup paths are physical deployment details. They can change during
   side-by-side migration without changing the logical product identity.
3. Logical dataset IDs must survive storage provider changes, bucket renames,
   and v2.6+ governance upgrades.
4. Entity-specific values must come from environment/configuration, not code
   edits to the shared SoloLakehouse template.
5. The first entity split keeps MinIO. Object-store replacement is a later,
   separate migration. See
   [Object Store Abstraction and MinIO Deferral](object-store-abstraction.md)
   for the provider/configuration boundary.

## Required fields

Implementation note: storage fields such as `DATA_BUCKET`, `AUDIT_BUCKET`,
`MLFLOW_ARTIFACT_BUCKET`, and `WAREHOUSE_URI` are entity contract targets. The
current v2.5 runtime still uses `BUCKET_NAME`, `MLFLOW_ARTIFACT_ROOT`, and
existing `sololakehouse` / `mlflow-artifacts` defaults until the relevant
runtime parameterization issues are implemented.

Runtime identity fields such as `PRODUCT_ID`, `PRODUCT_DISPLAY_NAME`,
`PRODUCT_DOMAIN`, `ENVIRONMENT`, `RUNTIME_VERSION`, and `TRINO_USER` are active
for health/verification labels and Trino client defaults. `COMPOSE_PROJECT_NAME`
is documented as the entity-level Compose identity value, but the current
Compose files still keep explicit `slh-*` container names for local compatibility
until runtime state layout work changes that contract.

| Field | Class | Required | FinLakehouse example | Aviation Lakehouse example | Notes |
|---|---|---:|---|---|---|
| `PRODUCT_ID` | Stable logical identity | Yes | `finlakehouse` | `aviation-lakehouse` | Lowercase product instance ID. Prefer DNS-safe names for host paths, compose projects, and service labels. |
| Product display name | Stable logical identity | Yes | `FinLakehouse` | `Aviation Lakehouse` | Human-readable label for portal, docs, dashboards, and runbooks. |
| Domain | Stable logical identity | Yes | `financial_markets` | `aviation_operations` | Defines source/data-product ownership boundary. |
| Dataset namespace | Stable logical identity | Yes | `fin` | `aviation` | Prefix for logical dataset IDs such as `fin.ecb_rates_bronze`. |
| Owner | Stable logical identity | Yes | `Jiahong Que` | `Jiahong Que` | Can later map to governance owners, alert contacts, and access reviews. |
| Runtime version | Release identity | Yes | `slh-v2.5.1` | `slh-v2.5.1` | Record the SoloLakehouse template version or release artifact used by the entity. |
| Environment | Deployment detail | Yes | `prod` or `dev` | `prod` or `dev` | Used for labels, portal context, and future promotion controls. |
| Runtime host | Deployment detail | Yes | Dedicated FinLakehouse VPS | Dedicated Aviation Lakehouse VPS | Each product entity is expected to run on its own host for the first split. |
| Runtime root | Deployment detail | Yes | `/opt/finlakehouse` | `/opt/aviation-lakehouse` | Root containing `app/`, `data/`, `backup/`, `logs/`, and `.env`. |
| `COMPOSE_PROJECT_NAME` | Deployment detail | Yes | `finlakehouse` | `aviation-lakehouse` | Keeps Docker Compose resources entity-scoped. |
| `OBJECT_STORE_PROVIDER` | Storage deployment detail | Yes | `minio` | `minio` | Provider name. Do not encode product identity here. |
| `OBJECT_STORE_ENDPOINT` | Storage deployment detail | Yes | `http://minio:9000` | `http://minio:9000` | Internal service endpoint for stack components. |
| `OBJECT_STORE_EXTERNAL_ENDPOINT` | Storage deployment detail | Yes | `http://localhost:9000` | `http://localhost:9000` | Operator/client endpoint for local access. |
| `DATA_BUCKET` | Storage deployment detail | Yes | `finlakehouse-data` | `aviation-lakehouse-data` | Main Bronze/Silver/Gold data bucket. |
| `AUDIT_BUCKET` | Storage deployment detail | Yes | `finlakehouse-audit` | `aviation-lakehouse-audit` | Reserved for v2.6+ governance evidence and audit artifacts. |
| `MLFLOW_ARTIFACT_BUCKET` | Storage deployment detail | Yes | `finlakehouse-mlflow` | `aviation-lakehouse-mlflow` | Stores MLflow model and run artifacts. |
| `WAREHOUSE_URI` | Storage deployment detail | Yes | `s3a://finlakehouse-data/warehouse/` | `s3a://aviation-lakehouse-data/warehouse/` | Hive/Trino warehouse root for entity-managed tables. |
| `TRINO_USER` | Service identity | Yes | `finlakehouse` | `aviation_lakehouse` | Use an engine-compatible user name; underscores are acceptable when hyphens are not. |
| `TRINO_URL` | Service endpoint | Yes | `http://localhost:8080` | `http://localhost:8080` | Entity-local Trino endpoint. |
| `MLFLOW_TRACKING_URI` | Service endpoint | Yes | `http://localhost:5000` | `http://localhost:5000` | Entity-local MLflow endpoint. |
| `OPENMETADATA_URL` | Service endpoint | Yes | `http://localhost:8585` | `http://localhost:8585` | Entity-local OpenMetadata endpoint. |
| OpenMetadata service name | Metadata identity | Yes | `finlakehouse-trino` | `aviation-lakehouse-trino` | Service name used for technical metadata ingestion. |
| `SUPERSET_URL` | Service endpoint | Yes | `http://localhost:8088` | `http://localhost:8088` | Entity-local Superset endpoint. |
| Superset workspace/database labels | Metadata identity | Yes | `finlakehouse_trino`, `finlakehouse_*` | `aviation_lakehouse_trino`, `aviation_lakehouse_*` | Labels must make dashboards and SQL assets entity-specific. |
| Dagster instance | Runtime state | Yes | Entity-local | Entity-local | Scheduler/run history belongs to one entity and is not shared. |
| Backup root | Runtime state | Yes | `/opt/finlakehouse/backup` | `/opt/aviation-lakehouse/backup` | Staging area for object-store and database backups. |
| Upgrade strategy | Stable logical policy | Yes | `side_by_side` | `side_by_side` | Fresh target runtime, import/rebuild, validate, cut over, retain old runtime for rollback. |

## Logical identity vs physical deployment

Use this separation when adding configuration, documentation, dashboards, or
future governance artifacts.

### Stable logical identity

These values describe what the product entity is. They should remain stable
across host moves, bucket migrations, object-store replacement, and v2.6+
governance upgrades:

- `PRODUCT_ID`
- product display name
- domain
- dataset namespace
- owner
- logical dataset IDs
- OpenMetadata logical service naming convention
- Superset entity labeling convention
- upgrade strategy

Changing one of these fields is a product rename or governance migration, not a
routine deployment change.

### Physical deployment details

These values describe where and how the entity currently runs. They may change
during side-by-side migration while the product identity remains the same:

- runtime host and host paths
- Docker Compose project name
- object-store provider and endpoints
- data, audit, and MLflow artifact bucket names
- warehouse URI
- service URLs
- database connection details
- backup root
- local bind mounts under `docker/data/` or `/opt/<product_id>/data/`

When physical details change, update environment files, runbooks, metadata
ingestion configuration, and restore procedures. Do not rename logical dataset
IDs solely because storage moved.

## Entity configuration examples

### FinLakehouse

```bash
PRODUCT_ID=finlakehouse
PRODUCT_DISPLAY_NAME=FinLakehouse
PRODUCT_DOMAIN=financial_markets
DATASET_NAMESPACE=fin
PRODUCT_OWNER="Jiahong Que"
RUNTIME_VERSION=slh-v2.5.1
ENVIRONMENT=prod
COMPOSE_PROJECT_NAME=finlakehouse

OBJECT_STORE_PROVIDER=minio
OBJECT_STORE_ENDPOINT=http://minio:9000
OBJECT_STORE_EXTERNAL_ENDPOINT=http://localhost:9000

DATA_BUCKET=finlakehouse-data
AUDIT_BUCKET=finlakehouse-audit
MLFLOW_ARTIFACT_BUCKET=finlakehouse-mlflow
WAREHOUSE_URI=s3a://finlakehouse-data/warehouse/

TRINO_USER=finlakehouse
TRINO_URL=http://localhost:8080
MLFLOW_TRACKING_URI=http://localhost:5000
OPENMETADATA_URL=http://localhost:8585
OPENMETADATA_TRINO_SERVICE_NAME=finlakehouse-trino
SUPERSET_URL=http://localhost:8088
SUPERSET_TRINO_DATABASE_LABEL=finlakehouse_trino

UPGRADE_STRATEGY=side_by_side
```

Initial domain scope:

- ECB interest rates
- DAX daily index data
- existing Bronze -> Silver -> Gold flow
- existing MLflow experiment path
- OpenMetadata and Superset integration under FinLakehouse labels

### Aviation Lakehouse

```bash
PRODUCT_ID=aviation-lakehouse
PRODUCT_DISPLAY_NAME="Aviation Lakehouse"
PRODUCT_DOMAIN=aviation_operations
DATASET_NAMESPACE=aviation
PRODUCT_OWNER="Jiahong Que"
RUNTIME_VERSION=slh-v2.5.1
ENVIRONMENT=prod
COMPOSE_PROJECT_NAME=aviation-lakehouse

OBJECT_STORE_PROVIDER=minio
OBJECT_STORE_ENDPOINT=http://minio:9000
OBJECT_STORE_EXTERNAL_ENDPOINT=http://localhost:9000

DATA_BUCKET=aviation-lakehouse-data
AUDIT_BUCKET=aviation-lakehouse-audit
MLFLOW_ARTIFACT_BUCKET=aviation-lakehouse-mlflow
WAREHOUSE_URI=s3a://aviation-lakehouse-data/warehouse/

TRINO_USER=aviation_lakehouse
TRINO_URL=http://localhost:8080
MLFLOW_TRACKING_URI=http://localhost:5000
OPENMETADATA_URL=http://localhost:8585
OPENMETADATA_TRINO_SERVICE_NAME=aviation-lakehouse-trino
SUPERSET_URL=http://localhost:8088
SUPERSET_TRINO_DATABASE_LABEL=aviation_lakehouse_trino

UPGRADE_STRATEGY=side_by_side
```

Initial domain scope must be designed separately from FinLakehouse. Aviation
Lakehouse should not be a financial dataset rename. Before implementation,
define:

- authoritative aviation source systems
- ingestion frequency
- Bronze raw schema
- Silver cleaned schema
- first Gold product
- expected consumers
- freshness and retention expectations
- whether MLflow is required immediately

## Runtime root layout

For continuously operated product entities, prefer a host root owned by the
entity:

```text
/opt/<product_id>/app/       # checked-out code or release artifact
/opt/<product_id>/data/      # runtime bind mounts
/opt/<product_id>/backup/    # local backup staging
/opt/<product_id>/logs/      # optional host-level logs
/opt/<product_id>/.env       # entity-specific configuration
```

The local SoloLakehouse reference may continue to use repository-local
`docker/data/` bind mounts. Product entities should document whether the
repository checkout itself is the runtime root or whether bind mounts live under
`/opt/<product_id>/data/`.

## Dataset identity boundary

Dataset IDs are logical identities and are not storage paths. They should map to
current physical locations through configuration and governance metadata.
See [Dataset ID and Governance Naming Convention](dataset-governance-naming.md)
for naming rules, current FinLakehouse mappings, Aviation Lakehouse
placeholders, and v2.6 lineage evidence fields.

Examples:

```text
fin.ecb_rates_bronze
fin.dax_daily_bronze
fin.ecb_rates_silver
fin.dax_daily_silver
fin.ecb_dax_features_gold
fin.ecb_dax_features_iceberg

aviation.<source>_bronze
aviation.<cleaned_dataset>_silver
aviation.<feature_dataset>_gold
```

When buckets, warehouses, or object-store providers change, preserve these
logical IDs and update their physical mappings.

## Minimum acceptance checklist

A product entity contract is complete when:

- required fields above are present for the entity;
- logical identity fields are separated from physical deployment details;
- data, audit, and MLflow artifact buckets are unique to the entity;
- warehouse URI points at the entity data bucket;
- OpenMetadata and Superset labels are entity-specific;
- Dagster state is entity-local;
- backup root and restore target assumptions are documented;
- upgrade strategy is `side_by_side`;
- MinIO is recorded as the current object-store provider, not the product
  identity.
