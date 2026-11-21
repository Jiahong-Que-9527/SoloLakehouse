# G04 bootstrap additions

<!-- [Kimi·2026-11-21] G04 reuses G01's bootstrap wholesale (state bucket,
github-deployer SA + grant set, WIF pool/provider, enabled APIs) — see
`gcp/01-european-energy-pipeline/infra/BOOTSTRAP.md`. Only one delta:
the image registry chicken-and-egg. No new API is service-enabled
(bigquery, run, artifactregistry are already enabled by G01). -->

Run everything from WSL with `gcloud` authenticated and the project selected.

## 0. Variables

```bash
export PROJECT_ID=slh-gcp-test
export REGION=europe-west3
export STATE_BUCKET=${PROJECT_ID}-tfstate
```

## 1. Image registry — same chicken-and-egg as G01 §2b / G02 §1 / G03 §1

`build-push` runs before the first apply can ever create the registry, so it
is created by hand and adopted into Terraform state:

```bash
gcloud artifacts repositories create governed-energy-product \
  --repository-format=docker --location=$REGION \
  --project=$PROJECT_ID --description="G04 Governed Energy Data Product images"

cd gcp/04-governed-energy-data-product/infra
terraform init -backend-config="bucket=$STATE_BUCKET"
terraform import \
  -var project_id=$PROJECT_ID -var image=plan-only-placeholder \
  -var input_release_id=plan-only -var candidate_id=plan-only \
  google_artifact_registry_repository.product \
  "projects/$PROJECT_ID/locations/$REGION/repositories/governed-energy-product"
```

## 2. Nothing else

- No deployer grant delta: the apply job already holds `bigquery.admin`,
  `run.admin`, `iam` roles and `resourcemanager.projectIamAdmin` from G01.
- No new project service: G04 uses only already-enabled APIs.
- GitHub variables and the `gcp-test` environment are repo-level and shared.
- The first publication consumes a real G01 `load_release` id; take it from
  `bq query "SELECT release_id, window_start, row_count FROM
  slh-gcp-test.energy.load_release WHERE quality_status='passed' ORDER BY
  published_at DESC LIMIT 1"` and pass it to the publisher job.
