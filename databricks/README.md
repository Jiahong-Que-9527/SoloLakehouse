# Databricks project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->

Build one ECB Delta Lakehouse through modeling, automated jobs, incremental
updates and governance. A planned financial ML workload consumes one of its
released snapshots. The aviation flagship provides a second workload for
testing whether the same delivery practices transfer. All milestones below
are planned.

## Projects

- [ECB Delta Lakehouse](ecb-delta-lakehouse/README.md) owns ECB data ingest,
  modeling, incremental updates and governed release. It covers D01 to D04.
- D05 is the planned financial ML workload. It consumes a fixed ECB Gold
  snapshot and produces a versioned evaluation and model artifact.
- The flagship's [Aviation Lakehouse Integration](../Fraport-adsb-intelligence/04-aviation-lakehouse/README.md)
  uses a synthetic or approved aviation Gold release. It is a separate
  workload for testing delivery and governance practices.

## Milestones

1. **D01 · Model one financial series in Delta.** Start with a fixed quarter of
   the ECB daily USD/EUR reference series. Run Bronze, Silver and Gold with a
   small fixture. Verify unique observation keys and expected derived metrics.
2. **D02 · Deploy and operate a job.** Use Lakeflow Jobs and a Declarative
   Automation Bundle. Capture one run with ingest, transform and validation
   tasks. Cause a validation failure, then fix it and verify one release.
3. **D03 · Apply revisions incrementally.** Use fixed input batches to test
   duplicates, new observations and historical corrections. Exercise Auto
   Loader and checkpoint recovery. Compare the output with complete recomputation.
4. **D04 · Govern Gold access.** Test a permitted Gold read and a denied
   unauthorized read, and record the published Delta version. Validate
   lineage in the workspace when available.
5. **D05 · Train from a released snapshot.** Use a time-ordered split and a
   simple baseline. Track evaluation and model artifacts in MLflow. Record the
   release ID, Delta version, feature definition, time cutoffs and commit.
   Report the baseline and model metrics on the same evaluation interval.
6. **D06 · Reuse deployment and governance.** Once the ECB and aviation
   workloads have both been deployed, extract recurring Bundle configuration
   and catalog, schema and permission setup into the
   [project template](../project-template/README.md). Verify that each
   workload deploys independently and that its access tests still pass.

## Project handoffs

An ECB release records its schema version, source window, validation result,
Delta version and code revision. The financial ML workload can validate
against a small fixture and select a specific release for an integration
run. The [local ECB Silver project](../local/ecb-silver-pipeline/README.md)
uses policy rates and provides a reference for fixed windows and quality
checks. The daily exchange-rate series has its own contract.

Record actual workspace permissions and feature availability in the run
evidence. Fixture tests and workspace job, checkpoint or governance tests
are tracked separately.

[ECB daily reference series](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A) ·
[Declarative Automation Bundles](https://docs.databricks.com/gcp/en/dev-tools/bundles) ·
[Unity Catalog](https://docs.databricks.com/gcp/en/data-governance/unity-catalog/)
