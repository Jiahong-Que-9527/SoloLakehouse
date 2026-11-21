# G03 bootstrap additions

<!-- [Kimi·2026-11-21] G03 reuses G01's bootstrap wholesale (state bucket,
github-deployer SA + grant set, WIF pool/provider, enabled APIs) — see
`gcp/01-european-energy-pipeline/infra/BOOTSTRAP.md`. Deltas: the image
registry chicken-and-egg, one deployer role, and the Pub/Sub service agent
warm-up. The resources themselves are free-tier SKUs. -->

Run everything from WSL with `gcloud` authenticated and the project selected.

## As-built record — 2026-11-21 (owner approved, cost gate satisfied)

All steps below were executed on 2026-11-21 before the first PR:

- **§1 registry**: `aviation-events` created and imported into the
  `gcp/03-aviation-event-processing` state prefix.
- **§2 deployer grant**: `roles/pubsub.admin` added to `github-deployer`.
- **§3 service**: `pubsub.googleapis.com` was **already enabled** in the
  project, so it was imported instead of created — the correct import ID
  is `{project}/{service}` (`slh-gcp-test/pubsub.googleapis.com`; the bare
  service name fails with an ID-format error). The Pub/Sub service agent
  (`service-236720670014@gcp-sa-pubsub...`) already existed, so no
  `services identity create` warm-up was needed.
- **Plan check**: `terraform plan` against the real state shows
  **22 to add, 0 to change, 0 to destroy** — free-tier SKUs only.

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

## 3. Service and service agent

`pubsub.googleapis.com` may already be enabled (it was on 2026-11-21). Check
first; if enabled, import it with the `{project}/{service}` ID instead of
letting apply create it:

```bash
gcloud services list --enabled --format='value(config.name)' | grep pubsub
terraform import \
  -var project_id=$PROJECT_ID -var image=plan-only-placeholder \
  google_project_service.pubsub "$PROJECT_ID/pubsub.googleapis.com"
```

The dead-letter policy needs the Pub/Sub service agent
(`service-<project-number>@gcp-sa-pubsub.iam.gserviceaccount.com`). It
already existed here; if a fresh project lacks it:

```bash
gcloud beta services identity create --service=pubsub.googleapis.com
```

## 4. Nothing else

- GitHub variables (`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
  `GCP_STATE_BUCKET`) and the `gcp-test` environment are repo-level and
  shared with G01/G02.
- `monitoring.googleapis.com` is already enabled by G02; G03's alert and
  log metric rely on it without re-declaring the service resource.
- The fixture generator publishes from WSL with the owner's own credentials
  (project-level roles already cover `pubsub.publisher` on the topic).
