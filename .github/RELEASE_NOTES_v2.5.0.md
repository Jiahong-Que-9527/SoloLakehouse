## SoloLakehouse v2.5.0 — reference extension

> **Scope note:** This file describes the **v2.5.0 git tag** as published. On current `main`, OpenMetadata and Superset are part of the default `make up` stack, health checks are covered by `make verify`, legacy pipeline Makefile switches are removed, and Compose persistence uses `docker/data/` bind mounts. See the repository root **`CHANGELOG.md`** (Unreleased) for the live contract.

Version **v2.5.0** was a **reference extension** on top of the v2 Dagster-orchestrated platform: it added an open table-format path for the Gold layer and an optional metadata-catalog stack. Current `main` has since promoted the catalog and BI services into the default v2.5 runtime. Scope and versioning are described in the [roadmap](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/roadmap.md).

### Added

- **Apache Iceberg for Gold in Trino** — table `iceberg.gold.ecb_dax_features_iceberg` backed by Hive Metastore as the Iceberg catalog. Rationale and trade-offs: [ADR-013](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/decisions/ADR-013-iceberg-gold-trino.md).
- **Trino Iceberg catalog** — configuration template at [`config/trino/catalog/iceberg.properties`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/config/trino/catalog/iceberg.properties).
- **OpenMetadata** (1.5.x) — optional Docker Compose overlay at the v2.5.0 tag for catalog UI, lineage, and Trino service registration. On current `main`, it is included by default in `make up`. Rationale: [ADR-014](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/decisions/ADR-014-openmetadata-optional-profile.md).
- **Integration test** for Iceberg table creation and query in Trino: [`tests/integration/test_trino_iceberg.py`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/tests/integration/test_trino_iceberg.py).
- **OpenMetadata health verification** — tag-era health check for the optional overlay; on current `main`, use `make verify`.

### Documentation and learning material

- **User guides** — [`docs/USER_GUIDE_EN.md`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/USER_GUIDE_EN.md) (English), [`docs/USER_GUIDE.md`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/USER_GUIDE.md) (中文); central doc map: [`docs/README.md`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/README.md).
- **ADR index** updated for v2.5.

### Quick start after services are up

```bash
make verify
make pipeline
```

**Trino** — verify Hive and Iceberg Gold exposure:

```sql
SELECT * FROM hive.gold.ecb_dax_features LIMIT 5;
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 5;
```

**Current `main` note** — OpenMetadata and Superset start with `make up`, and their health checks are included in:

```bash
make verify
```

### Upgrade notes

- No breaking change to the default `make pipeline` path (Dagster) at the v2.5.0 tag.
- *Post-tag note:* on current `main`, the legacy script entrypoints referenced in earlier drafts have been **removed** as part of v2.5 single-track simplification. Use a pre-removal git tag if you must reproduce the legacy path.
- Pull new images and restart the stack after upgrading; see [deployment.md](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/deployment.md) for ports and troubleshooting.

---

**Full changelog:** [`CHANGELOG.md`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/CHANGELOG.md) (this release: section **v2.5.0**).
