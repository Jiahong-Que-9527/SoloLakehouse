# SoloLakehouse

SoloLakehouse is a personal portfolio of independent **Data and AI platform engineering** projects. It covers the full path a data product travels: reliable ingestion from imperfect sources, validated and versioned datasets, delivery on managed cloud services, and the DevOps practice that ships, observes and recovers all of it. Each project owns its inputs, environment and acceptance checks, and records the evidence behind every claim.

![Aviation intelligence airport illustration](docs/images/aviation-intelligence-airport-illustration.png)

## Projects

| Project | Question it answers | What is built | Evidence / status |
|---|---|---|---|
| [**Frankfurt Airport ADS-B Intelligence**](Frankfurt-Airport-adsb-intelligence/README.md) | Can **incomplete aircraft observations** around Frankfurt Airport support **reproducible analysis**? | Local OpenSky collector with **checksummed manifests** and **resumable runs**; **DuckDB** Silver and Gold layers; versioned releases through a **Release Gate** that blocks failing data | **90%** · **53 of 60** OpenSky batches accepted and backed up. Batch b53 is a source-gap month. Batch b54 is next. The original 24 monthly releases reconciled in BigQuery. The offline model and Dagster recovery are verified. Cloud Run awaits measured receipt times. |
| [**Data Engineering**](Data-engineering/README.md) | Can a **hybrid EV-charging and roaming** workload be delivered as a governed warehouse on **dbt, DuckDB, BigQuery and Airflow**? | Resumable raw ingestion, **Kimball** marts, dbt tests and contracts, incremental **SCD Type 2**, Slim CI, BigQuery FinOps, local **Airflow**, dbt artifact **observability** with a reusable **DE template** | **100%** · **E01–E08 delivered — track complete**. Incremental merge, SCD Type 2 and Slim CI are verified under contract **v1.5**. BigQuery FinOps (E06) is live-verified on `slh-gcp-test` (€0, 0 destroys). Airflow orchestration (E07) is accepted locally (4/4 dag runs green, €0); dbt artifact observability + freshness SLO drill + second-workload template (E08) accepted 2026-11-24. |
| [**ML Engineering**](Mlops-engineering/README.md) | Can one ML system be **closed end to end**, from features to **drift-triggered retraining**? | **Point-in-time features**, rolling backtests, **MLflow** lineage, release gate, batch and online serving, drift monitoring, **Dagster** | **100%** · **M01–M09 accepted**. Model rollback and Dagster retraining verified. The template onboarded a second workload. |
| [**DevOps Engineering**](Devops-engineering/README.md) | How does a service travel from a **source change** to a **verified deployment**, and recover from a bad release? | **Seven stages:** reproducible dev, containers, **CI** with supply-chain checks, **digest rollback**, **Kubernetes GitOps** drills, incident recovery, reusable template | **100%** · **D01–D07 accepted**. Delivery and rollback drills passed. The template onboarded a second service. |
| [**Google Cloud**](gcp/README.md) | How are **data products** delivered and governed on managed cloud services? | Scheduled **Cloud Run** batch job to **Cloud Storage and BigQuery**; authenticated **API** over an authorized view; **Pub/Sub** event processing with dedup and replay; governed release with contracts | **100%** · **G01–G06 delivered**. G05 verified batch scoring and rollback in BigQuery. G06 deployed and smoke-tested two isolated stacks, verified cross-stack read denial, and tore down both stacks with zero residual resources. |
| [**Databricks**](databricks/README.md) | How does a **governed lakehouse** product run on Databricks? | **Delta** tables, scheduled jobs, **CDC** with corrections, **Unity Catalog**, MLflow forecasting, workspace provisioning | **100% of Free Edition scope** · **D01–D06 complete in scope**. D06 verified the template, CI, and the reference job with one workspace identity. Multi-principal checks are excluded from this completion figure. |

## Delivery progress

![Delivery progress](docs/images/progress.svg)

Progress estimates combine accepted stages and documented partial work across each project's roadmap.

The earlier self-hosted lakehouse (Compose, Dagster, Iceberg, Trino) is preserved in a [pinned snapshot](https://github.com/Jiahong-Que-9527/SoloLakehouse/tree/741e6da82cdc2cad207aa6ee707b8fb157b0174a); a fixture reproduction is a later milestone.

## Capabilities and target roles

| Project | What it shows | Target roles |
|---|---|---|
| Frankfurt Airport ADS-B Intelligence | **Resumable bulk ingestion**, **manifest commits**, data quality semantics, **DuckDB** Silver and Gold modelling, **data contracts** and **release gates** | **Data Engineer** · **Data Platform Engineer** |
| DevOps Engineering | **Docker**, **GitHub Actions**, image **supply-chain checks**, **digest-based rollback**, **k3d and Helm GitOps**, **observability**, incident drills, service templates | **DevOps Engineer** · **Platform Engineer** · **SRE** |
| Google Cloud | **Cloud Run**, **BigQuery**, **Pub/Sub**, **Terraform**, **Workload Identity Federation**, authorized views, **idempotent event processing**, governed data products | **Cloud Data Engineer** · **Backend Engineer (data)** |
| Data Engineering *(in progress)* | **dbt**, **DuckDB**, **BigQuery**, **Airflow**, data contracts, incremental SCD | **Data Engineer** |
| ML Engineering | **Point-in-time features**, evaluation, **model registry**, **drift monitoring**, orchestration | **MLOps Engineer** · **ML Engineer** |
| Databricks *(Free Edition scope complete)* | **Delta**, **Jobs**, **CDC**, **Unity Catalog**, workspace provisioning | **Lakehouse Engineer** |

A capability counts as demonstrated only where the repository holds code, tests and recorded evidence.

## Run the checks

With Python 3.12+ and [uv](https://docs.astral.sh/uv/). Tests use synthetic data and need no cloud account or live source.

```bash
cd Frankfurt-Airport-adsb-intelligence/01-opensky-acquisition   # or gcp/01-european-energy-pipeline
uv sync --locked && uv run --locked pytest
```

Raw datasets, credentials and runtime state stay outside Git; the repository holds code, contracts, designs and evidence summaries.

[Engineering roadmap](docs/roadmap.md) · [Aviation plan](Frankfurt-Airport-adsb-intelligence/docs/project-plan.md) · [Project template](project-template/README.md)

## License

Code and documentation are licensed under the [Apache License 2.0](LICENSE). Public data slices used as fixtures (Bundesnetzagentur, SMARD, ECB) stay under their providers' terms, and OpenSky-derived summaries remain subject to the OpenSky Network terms; see [NOTICE](NOTICE). SoloLakehouse is an independent project, not affiliated with Frankfurt Airport's operator or DFS.
