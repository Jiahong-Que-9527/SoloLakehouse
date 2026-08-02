# Exit Playbook — Catalog and Platform Portability (v2.7 I5)

This playbook describes how to **leave** the SoloLakehouse reference stack without
vendor-specific lock-in claims. It complements the machine-readable output of
`make sovereignty-report` and the catalog seam documented in
[`docs/catalog-boundary.md`](catalog-boundary.md).

**This is operational guidance, not a compliance certification.**

## 1. Inventory before exit

1. Run `make sovereignty-report > sovereignty-report.md` and archive the JSON
   variant with `make sovereignty-report FORMAT=json`.
2. Export governed dataset contracts from `governance/datasets/*.yaml`.
3. Record current Iceberg table locations from Trino:
   ```sql
   SELECT table_schema, table_name, metadata_location
   FROM iceberg.information_schema.tables;
   ```
4. Capture OpenMetadata export (UI or API) for business metadata and lineage edges.
5. List audit-bucket manifests under the configured `AUDIT_BUCKET` prefix.

## 2. Object storage — data always leaves via S3 API

All Iceberg data and audit artifacts live in S3-compatible buckets (default: MinIO).

| Asset | Default location | Exit action |
|---|---|---|
| Iceberg warehouse | `s3://<DATA_BUCKET>/warehouse/` | `mc mirror` / `aws s3 sync` to target bucket |
| MLflow artifacts | `s3://<MLFLOW_ARTIFACT_BUCKET>/` | Same S3 sync |
| Audit evidence | `s3://<AUDIT_BUCKET>/lineage/...` | Copy with Object Lock metadata preserved |

No proprietary API is required to read Parquet data files once metadata files are
copied alongside them.

## 3. Catalog migration — Hive Metastore to REST

The v2.7 catalog boundary allows backend selection without rewriting collectors or
transformations:

| Step | Hive path (default) | REST path (reference) |
|---|---|---|
| Select backend | `ICEBERG_CATALOG_BACKEND=hive` | `ICEBERG_CATALOG_BACKEND=rest` |
| Connection | `HIVE_METASTORE_URI` | `ICEBERG_REST_URI` (+ OAuth credential) |
| Warehouse | `WAREHOUSE_URI` | Same `WAREHOUSE_URI` / bucket layout |

Recommended migration sequence:

1. **Freeze writes** on the source environment (stop Dagster schedule/sensor).
2. **Register tables** in the target REST catalog (Polaris or another Iceberg REST
   implementation) pointing at existing metadata locations in object storage.
3. **Repoint readers** (Trino catalog properties, pyiceberg env) to REST.
4. **Validate** with `make interoperability-proof LIVE_REST=1` and Trino smoke
   queries on governed gold tables.
5. **Decommission Hive Metastore** only after REST readers pass acceptance checks.

See [`docs/polaris-evaluation.md`](polaris-evaluation.md) for the optional Polaris
reference profile.

## 4. Query and orchestration

| Component | Portability notes |
|---|---|
| **Trino** | Catalog definitions live in `config/trino/catalog/` templates; swap Iceberg connector catalog type (`hive_metastore` → `rest`) |
| **Dagster** | Asset code uses `get_catalog()`; backend swap is env-driven |
| **Superset** | Database connections are exportable JSON; update Trino URI/catalog |
| **MLflow** | Point tracking URI and artifact root to the new host/bucket |

## 5. Governance and evidence

| Artifact | Location | Exit action |
|---|---|---|
| Dataset contracts | `governance/datasets/` | Git-tracked; ship with the entity repo |
| Lineage manifests | Audit bucket | S3 copy; verify SHA-256 digests offline |
| Policy hooks | `make export-policy-hooks` | Archive canonical JSON |
| Model evidence | Audit bucket `.../model-evidence/` | S3 copy with MLflow run cross-reference |

Evidence records remain verifiable offline because digests are SHA-256 bound in the
manifest schema (`governance/evidence.py`, `governance/model_evidence.py`).

## 6. Metadata (OpenMetadata)

OpenMetadata stores descriptive metadata separately from Iceberg physical tables.

1. Export entity JSON / lineage graph from OpenMetadata.
2. Stand up OpenMetadata (or another catalog) in the target environment.
3. Re-ingest Trino/Iceberg connectors against the new REST or Hive catalog endpoint.
4. Re-link governed `dataset_id` values to the new OpenMetadata FQNs before resuming
   automatic lineage emission.

## 7. Rollback

If REST migration fails:

1. Set `ICEBERG_CATALOG_BACKEND=hive`.
2. Restore `HIVE_METASTORE_URI` and Trino hive/iceberg catalog templates.
3. Restart Trino and Dagster; rerun `make demo`.

Hive Metastore and the warehouse bucket are not destroyed by attempting REST
registration, so rollback remains object-store + config reversal.

## Related

- [`docs/catalog-boundary.md`](catalog-boundary.md)
- [`docs/polaris-evaluation.md`](polaris-evaluation.md)
- [ADR-017](decisions/ADR-017-iceberg-rest-catalog-option.md)
- `make sovereignty-report`
- `make interoperability-proof`
