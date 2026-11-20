# G02 bootstrap additions

<!-- [李淳风·2026-11-20] G02 reuses G01's bootstrap wholesale (state bucket,
github-deployer SA + grant set, WIF pool/provider, enabled APIs) — see
`gcp/01-european-energy-pipeline/infra/BOOTSTRAP.md`. Only two deltas, both
run once before the first PR plan / main apply. -->

Run everything from WSL with `gcloud` authenticated and the project selected.

## 0. Variables

```bash
export PROJECT_ID=slh-gcp-test
export REGION=europe-west3
export STATE_BUCKET=${PROJECT_ID}-tfstate
```

## 1. Image registry — same chicken-and-egg as G01 §2b

`build-push` runs before the first apply can ever create the registry, so it
is created by hand and adopted into Terraform state (the registry stays
TF-managed; apply must see it as existing infrastructure):

```bash
gcloud artifacts repositories create energy-api \
  --repository-format=docker --location=$REGION \
  --project=$PROJECT_ID --description="G02 Energy Analytics API images"

cd gcp/02-energy-analytics-api/infra
terraform init -backend-config="bucket=$STATE_BUCKET"
terraform import \
  -var project_id=$PROJECT_ID -var image=plan-only-placeholder \
  google_artifact_registry_repository.energy_api \
  "projects/$PROJECT_ID/locations/$REGION/repositories/energy-api"
```

## 2. Deployer grants for observability (G02 adds monitoring resources)

G01's grant set has no monitoring/logging roles, so the apply job would 403
on the log-based metric, notification channel and alert policy:

```bash
export DEPLOY_SA=github-deployer@${PROJECT_ID}.iam.gserviceaccount.com
for role in roles/monitoring.admin roles/logging.configWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$DEPLOY_SA" --role=$role --quiet
done
```

## 3. Nothing else

GitHub variables (`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
`GCP_STATE_BUCKET`) and the `gcp-test` environment are repo-level and shared
with G01's workflow. No App Engine app change: Cloud Scheduler is G01-only.
