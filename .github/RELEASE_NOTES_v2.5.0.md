## SoloLakehouse v2.5.0 — reference extension

> **Scope note:** This file describes the **v2.5.0 git tag** as published. On current `main`, OpenMetadata and Superset are part of the default `make up` stack, legacy pipeline Makefile switches are removed, and Compose persistence uses `docker/data/` bind mounts. See the repository root **`CHANGELOG.md`** (Unreleased) for the live contract.

Version **v2.5** is a **reference extension** on top of the v2 Dagster-orchestrated platform: it adds an open table-format path for the Gold layer and an optional metadata-catalog stack. The default product narrative remains the v2 five-layer lakehouse core; scope and versioning are described in the [roadmap](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/roadmap.md).

### Added

- **Apache Iceberg for Gold in Trino** — table `iceberg.gold.ecb_dax_features_iceberg` backed by Hive Metastore as the Iceberg catalog. Rationale and trade-offs: [ADR-013](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/decisions/ADR-013-iceberg-gold-trino.md).
- **Trino Iceberg catalog** — configuration template at [`config/trino/catalog/iceberg.properties`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/config/trino/catalog/iceberg.properties).
- **Optional OpenMetadata** (1.5.x) — Docker Compose profile via `make up-openmetadata` for catalog UI, lineage, and Trino service registration. Rationale: [ADR-014](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/decisions/ADR-014-openmetadata-optional-profile.md).
- **Integration test** for Iceberg table creation and query in Trino: [`tests/integration/test_trino_iceberg.py`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/tests/integration/test_trino_iceberg.py).
- **`make verify-openmetadata`** — health check when the optional OpenMetadata profile is running.

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

**OpenMetadata (optional)** — start the profile, open the UI at http://localhost:8585 , then run:

```bash
make verify-openmetadata
```

### Upgrade notes

- No breaking change to the default `make pipeline` path (Dagster v2). Legacy script execution remains available via `make pipeline-v1`, `make pipeline-legacy`, or `PIPELINE_MODE=v1`.
- Pull new images and restart the stack after upgrading; see [deployment.md](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/docs/deployment.md) for ports and troubleshooting.

---

**Full changelog:** [`CHANGELOG.md`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/v2.5.0/CHANGELOG.md) (this release: section **v2.5.0**).
