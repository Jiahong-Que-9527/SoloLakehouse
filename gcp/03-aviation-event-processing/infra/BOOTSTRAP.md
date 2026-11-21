# G03 bootstrap additions

<!-- [Kimi·2026-11-21] G03 reuses G01's bootstrap wholesale (state bucket,
github-deployer SA + grant set, WIF pool/provider, enabled APIs) — see
`gcp/01-european-energy-pipeline/infra/BOOTSTRAP.md`. Deltas: the image
registry chicken-and-egg, one deployer role, and the Pub/Sub service agent
warm-up. Nothing here runs until the owner approves the deployment
(cost gate in `AGENTS.md`); the resources themselves are free-tier SKUs. -->

Run everything from WSL with `gcloud` authenticated and the project selected.

## 0. Variables

```bash
export PROJECT_ID=slh-gcp-test
export REGION=europe-west3
export STATE_BUCKET=${PROJECT_ID}-tfstate
```

## 1. Image registry — same chicken-and-egg as G01 §2b / G02 §1

`build-push` runs before the first apply can ever create the registry, so it
is created by hand and adopted into Terraform state:

```bash
gcloud artifacts repositories create aviation-events \
  --repository-format=docker --location=$REGION \
  --project=$PROJECT_ID --description="G03 Aviation Event Processing images"

cd gcp/03-aviation-event-processing/infra
terraform init -backend-config="bucket=$STATE_BUCKET"
terraform import \
  -var project_id=$PROJECT_ID -var image=plan-only-placeholder \
  google_artifact_registry_repository.consumer \
  "projects/$PROJECT_ID/locations/$REGION/repositories/aviation-events"
```

## 2. Deployer grant for Pub/Sub (G03 adds a new API)

G01's grant set has no Pub/Sub roles, so the apply job would 403 on topics,
subscriptions, dead-letter policy and their IAM bindings:

```bash
export DEPLOY_SA=github-deployer@${PROJECT_ID}.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOY_SA" --role=roles/pubsub.admin --quiet
```

## 3. Pub/Sub service agent warm-up

The dead-letter policy needs the Pub/Sub service agent
(`service-<project-number>@gcp-sa-pubsub.iam.gserviceaccount.com`). It is
created on first use of the API; if the first apply fails with a
"service agent does not exist" error, materialize it and re-apply:

```bash
gcloud beta services identity create --service=pubsub.googleapis.com
terraform plan -var project_id=$PROJECT_ID -var image=plan-only-placeholder
# expected: adds only, 0 destroys — then apply through the gcp-test gate
```

## 4. Nothing else

- GitHub variables (`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
  `GCP_STATE_BUCKET`) and the `gcp-test` environment are repo-level and
  shared with G01/G02.
- `monitoring.googleapis.com` is already enabled by G02; G03's alert and
  log metric rely on it without re-declaring the service resource.
- The fixture generator publishes from WSL with the owner's own credentials
  (project-level roles already cover `pubsub.publisher` on the topic).
