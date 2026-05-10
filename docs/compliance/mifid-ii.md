# MiFID II / MiFIR Mapping

Primary source for the data-record evidence angle: Regulation (EU) No 600/2014 (MiFIR), especially Article 25 record keeping and Article 26 transaction reporting.

SoloLakehouse does not implement a MiFID transaction reporting system. This mapping explains how the v2.5 lakehouse architecture demonstrates the kind of traceable, queryable data foundation that regulated reporting systems require.

| MiFID II / MiFIR area | Regulatory intent | SoloLakehouse v2.5 evidence | Related ADR / doc | Gap before production |
|---|---|---|---|---|
| Article 25 style record retention | Relevant order and transaction records must remain available to competent authorities. | Bronze is immutable by convention; raw source records are retained in object storage before transformation. | `docs/medallion-model.md`, ADR-003 | No regulatory retention policy, WORM storage, or legal hold workflow. |
| Article 26 transaction reporting accuracy | Reports should contain complete, accurate, timely transaction details. | Pydantic schemas validate inbound records; quality checks fail fast rather than silently degrading. | `ingestion/schema/`, `ingestion/quality/`, tests | No MiFID transaction report schema or ARM connectivity. |
| Timely queryability | Supervisory evidence must be retrievable. | Trino queries both Hive and Iceberg Gold tables; `make demo` checks positive Gold row counts. | `scripts/verify-demo.py`, ADR-013 | No reporting SLA or regulator-facing export package. |
| Data lineage | Records should be traceable from source to reportable output. | Dagster asset graph and medallion paths show source-to-Gold transformation flow. | `dagster/assets.py`, `docs/architecture.md` | Full OpenMetadata + Iceberg + Dagster lineage join is planned for v2.6. |
| Audit repeatability | Evidence should be reproducible. | Cold-clone demo, health dashboard, fixed demo script, and CI checks make the baseline repeatable. | README, `DEMO.md`, Makefile | External cold-start test still required before freeze. |

## v2.5 Boundary

The v2.5 baseline is a technical foundation for auditable financial-market data processing. It intentionally does not claim MiFID II/MiFIR regulatory reporting completeness.
