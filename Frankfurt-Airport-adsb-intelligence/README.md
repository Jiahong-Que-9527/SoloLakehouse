# Frankfurt Airport ADS-B Intelligence

<!-- [GLM·2026-11-20] Record the cloud-neutral MLflow substitution for Vertex AI (ADR-005). -->

Build an aviation data foundation for Frankfurt Airport (ICAO `EDDF`) from
OpenSky Network state vectors. The programme starts with a reliable historical
acquisition tool and grows through transformation, a governed data release, a
cloud Gold layer, analytics, a taxi-in time model, serving and orchestration.

Bronze and Silver stay on the local machine. The checked Gold Parquet release
feeds two paths. DuckDB builds point-in-time features locally for Python and
MLflow. Approved Gold releases also go to GCS and BigQuery managed Iceberg
for cloud analytics.

**Status (2026-11-25):** acquisition gate G0 has passed. Batches b01 (2026-10)
through b56 (2022-03) are validated, accepted and backed up to `E:`. b01
through b12 completed the twelve-month cut line. b24 finishes the two-year
window. b25 through b36 finish the first-year cut of the five-year
extension. b37 through b48 finish the second cut (four years on disk).
b49 starts the third cut. The next work is batch b57 (2022-02). Details are
in the
[acquisition status](01-opensky-acquisition/README.md#status-2026-11-25).

**Geometry v2 delivery (2026-11-23):** all 24 monthly packages in the
original two-year window reconciled in BigQuery. M5 is accepted with
433,694 candidates, 400,942 labeled rows and recorded query costs. The
November and December 2024 ingestion replays added zero rows.
See the [local handoff](02-aviation-transformation/README.md#backfill-status-and-handoff)
and the [cloud acceptance record](03-airport-analytics/README.md#geometry-v2-handoff-m5).

**Status (2026-11-20):** the academic research track is now separate from
this repository. Paper-1 experiments, the exploration notebooks and the
consulting notes moved to a local-only workspace outside the repository. That
workspace reads Silver outputs read-only and is not published to GitHub or to
the cloud. Silver, Gold and the cloud track remain engineering scope here.

## Subprojects

| # | Subproject | Runtime | Focus |
|---|------------|---------|-------|
| 01 | [OpenSky Acquisition](01-opensky-acquisition/README.md) | Local | Ingestion, reliability, data manifest |
| 02 | [Aviation Transformation](02-aviation-transformation/README.md) | Local (Python, DuckDB) | Silver, Gold, Release Gate |
| 03 | [Airport Analytics](03-airport-analytics/README.md) | BigQuery + GCS + Iceberg | Cloud Gold, SQL, infrastructure as code |
| 04 | [Point-in-Time Feature Dataset](04-aviation-lakehouse/README.md) | Local DuckDB + Parquet | Feature replay, leakage checks, training manifest |
| 05 | [Taxi-in Prediction](05-taxi-in-prediction/README.md) | Local Python + MLflow | Baseline, training, evaluation, model release |
| 06 | [Model Serving Integration](06-model-serving/README.md) | Cloud Run | API, versioning, monitoring |
| 07 | [Platform Orchestration](07-platform-orchestration/README.md) | Local Dagster | Scheduling, lineage, recovery |

The [04 November 2024 feature replay](04-aviation-lakehouse/README.md#first-delivery)
produced 8,570 predictions and 7,607 usable labels under a documented
availability simulation. Project 05's boosted candidate reduced November
holdout MAE from 140.3 to 129.3 seconds. The frozen model also reduced
[December MAE](05-taxi-in-prediction/README.md#december-2024-independent-evaluation)
from 148.6 to 137.5 seconds on 7,182 usable labels. An offline Docker replay
reproduced the model and both reports byte for byte. The
[local candidate release](05-taxi-in-prediction/README.md#local-candidate-release)
records MLflow version 1 and the checksums. The
[cross-season evaluation](05-taxi-in-prediction/reports/seasonal-evaluation.md)
reduced pooled MAE from 180.2 to 171.3 seconds across 51,319 usable labels in
four held-out months. The report includes results by season, local hour and
traffic level, using the same simulated observation delay.

## Documents

- [Project plan](docs/project-plan.md) covers phases, milestones, dependencies
  and exit criteria.
- [ADR-001](docs/adr/ADR-001-local-execution-for-historical-acquisition.md)
  records why historical acquisition runs locally.
- [ADR-002](docs/adr/ADR-002-regional-dataset-and-monthly-batches.md) records
  the 75 km regional dataset and the monthly batch approach.
- [ADR-003](docs/adr/ADR-003-local-bronze-silver-published-gold.md) records
  why Bronze and Silver stay local and only Gold is published.
- [ADR-004](docs/adr/ADR-004-gold-table-format-and-catalog.md) records the
  Gold table format decision and the check that must pass first.
- [01 design](01-opensky-acquisition/docs/design.md) and
  [batch plan](01-opensky-acquisition/docs/batch-plan.md) describe how the
  first dataset is collected. Original consulting notes and exploration
  notebooks stay local.

## Principles

- **Workload placement.** Run each workload where it is cheapest and simplest
  to operate. Move it only when a real requirement changes.
- **Code, data and backups are separate.** Git holds code, schemas,
  configuration and documentation. Raw data never goes into this repository.
- **Local source of record, published products.** Bronze and Silver stay on
  the local machine. Gold crosses to the cloud only through a Release Gate:
  versioned, checked, with a manifest and a release ID.
- **Idempotent and traceable.** Repeating a run or ingesting a release again
  never duplicates data. Every output traces to a release ID, a data version
  and a commit.
- **Bronze stays raw.** Acquisition keeps source fields, types and units.
  Cleaning, filtering and inference belong to later subprojects.
- **Proxy labels are not ground truth.** Taxi-in values derived from ADS-B
  state vectors are proxies. Claims about airport ground truth need
  independent validation.
- **Public work.** Raw data stays out of Git and public storage. Public work
  uses code, architecture and synthetic data.

## Naming and archived runs

The checked-in reports and evidence display the Frankfurt Airport name.
Original manifest bytes, MLflow registry names, BigQuery job IDs and run
metadata are available at Git commit `7965049b9df21e0c4075d89cbd2d0ea729dc585f`.
Checksums in phase evidence still identify the original run artifacts. The
seasonal evaluation report pins the renamed manifest for archive replay.

For new runs, use the `FRANKFURT_AIRPORT_*` environment and GitHub Actions
variables listed in the phase runbooks. Replay archived artifacts from the
original checkout, or recreate the release bundle and registry entry with
the current code. The [Airport Analytics bootstrap](03-airport-analytics/infra/BOOTSTRAP.md)
covers the Terraform state migration.
