# 02 · Aviation Transformation

**Runtime:** Google Cloud. Cloud Run Jobs first, Dataproc Serverless if
single-job compute is not enough.

Read Bronze state vectors from Cloud Storage and write a cleaned Silver layer:
validated observations, reconstructed trajectories and arrival events. This
is the main GCP CI/CD project in the programme.

## Why GCP

The raw data already sits in GCS, so compute runs next to it. Transformation
logic changes often, so a build and release pipeline pays off. The job no
longer depends on OpenSky authentication.

## Scope

- Clean and type Bronze observations. Record every rule that removes or
  repairs a row.
- Reconstruct per-aircraft trajectories with documented gap handling.
- Identify arrival candidates and surface-movement events with documented
  thresholds.
- Run data-quality checks and write a quality report for each run.
- Compare processing options on the same input: single-node Polars, Spark and
  BigQuery SQL. Record runtime, cost and complexity.
- Release through GitHub Actions to Artifact Registry and Cloud Run Jobs.

## Layers

```text
GCS Bronze    raw OpenSky state vectors (from project 01)
GCS Silver    clean observations, trajectories, arrival events
```

## Milestones

- **M1.** Transform one day of Bronze into Silver locally with tests.
- **M2.** Package as a container and run it as a Cloud Run Job on one day.
- **M3.** CI/CD from GitHub to Artifact Registry to Cloud Run.
- **M4.** Process the full year. Record run ID, source window, quality
  results and the outcome of a repeat run.
- **M5.** Engine comparison report.

## Acceptance

- A repeat run on the same input and code revision gives the same output.
- Quality checks fail the run visibly, and the failure has a documented
  rerun procedure.
- Deployment and runtime identities are separate and documented.

## Depends on

Project 01 Bronze dataset in GCS.

## Outputs

Silver tables, a quality report and a run record, used by projects 03 to 05.
