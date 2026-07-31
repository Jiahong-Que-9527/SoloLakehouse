## SoloLakehouse v2.6.0 — computational governance and evidence

Version **v2.6.0** adds a governance-evidence plane to the protected v2.5
Compose runtime. It makes one governed Gold dataset demonstrably traceable
through repository-native commands without expanding the production runtime
surface.

### Added

- Machine-validated dataset contracts and governed quality checks.
- A typed lineage record that joins OpenMetadata metadata, Iceberg snapshot
  metadata, and a successful Dagster materialization by stable dataset ID.
- `make lineage-evidence`, which writes a canonical SHA-256-bound manifest to
  the configured audit bucket.
- Release-readiness guidance and a recorded real-environment evidence drill for
  `fin.ecb_dax_features_gold`.
- OpenMetadata bootstrap and verification hardening needed for the local
  evidence workflow.

### Validation

- Contract validation, unit and integration checks, the protected v2.5 demo
  flow, and the v2.6 evidence drill completed before this release.
- The drill verified an OpenMetadata-owned Trino Gold table, an Iceberg
  snapshot, a successful Dagster run, and the resulting audit manifest.

### Known limitations

- This release does **not** enforce Object Lock/WORM retention; the audit path
  and manifest layout are stable, but retention enforcement is future work.
- OpenMetadata ingestion remains an operator prerequisite. The read token is
  local-only and must never be committed.
- Production RBAC, token lifecycle management, automated ingestion, and a
  regulatory-compliance certification are out of scope.

**Full changelog:** [`CHANGELOG.md`](../CHANGELOG.md), section `v2.6.0`.
