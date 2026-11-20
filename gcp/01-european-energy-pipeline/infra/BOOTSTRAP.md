# One-time cloud bootstrap

<!-- [李淳风·2026-11-20] Written for Task 2.1 (plan: docs/implementation.md). These
commands are deliberately OUTSIDE `main.tf`: the Terraform state bucket and the
GitHub deploy identity cannot create themselves (chicken-and-egg). Run them once
with the project owner's `gcloud` identity, then never again. -->

Run everything from WSL with `gcloud` authenticated (`gcloud auth login` done)
and the project selected (`gcloud config set project …`).

## 0. Variables

```bash
export PROJECT_ID=slh-gcp-test
export REGION=europe-west3
export STATE_BUCKET=${PROJECT_ID}-tfstate
export DEPLOY_SA=github-deployer@${PROJECT_ID}.iam.gserviceaccount.com
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
export REPO=Jiahong-Que-9527/SoloLakehouse
```

## 1. Terraform state bucket

```bash
gcloud storage buckets create gs://$STATE_BUCKET \
  --location=$REGION \
  --uniform-bucket-level-access \
  --public-access-prevention
```

## 2. Prerequisites Terraform cannot create for itself

Three things must exist BEFORE the first `terraform plan`/`apply` and before
the first `build-push`. Each was hit live on 2026-11-20:

```bash
# a) Every service main.tf manages, PLUS cloudresourcemanager: without CRM,
#    terraform's google_project_service resources all fail with 403.
gcloud services enable \
  run.googleapis.com storage.googleapis.com bigquery.googleapis.com \
  artifactregistry.googleapis.com cloudscheduler.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com iam.googleapis.com \
  serviceusage.googleapis.com cloudresourcemanager.googleapis.com \
  --project=$PROJECT_ID

# b) The image registry: build-push runs before the first apply can ever
#    create it (apply needs the image build-push publishes).
gcloud artifacts repositories create energy \
  --repository-format=docker --location=$REGION \
  --project=$PROJECT_ID --description="G01 energy pipeline images"

# c) An App Engine app: Cloud Scheduler refuses to create jobs without one.
#    Empty shell, no code, no cost; the region choice is irreversible.
gcloud app create --region=$REGION --project=$PROJECT_ID
```

Adopt the registry into Terraform state (the plan keeps it TF-managed), so
`apply` sees it as existing infrastructure instead of failing on create:

```bash
cd gcp/01-european-energy-pipeline/infra
terraform init -backend-config="bucket=$STATE_BUCKET"
terraform import \
  -var project_id=$PROJECT_ID -var image=plan-only-placeholder \
  google_artifact_registry_repository.energy \
  "projects/$PROJECT_ID/locations/$REGION/repositories/energy"
```

## 3. Deployer service account and grant set

The deployer manages everything `main.tf` declares (services, storage, BigQuery,
registry, scheduler, the `energy-job` identity and its project bindings), so it
needs one admin role per resource family plus `actAs` for the job's service
account and project-IAM rights for the two project-level bindings. This is a
single-purpose test project; revisit when G06 builds the project factory.

```bash
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions deployer (SoloLakehouse)"

for role in \
  roles/run.admin \
  roles/storage.admin \
  roles/bigquery.admin \
  roles/artifactregistry.admin \
  roles/cloudscheduler.admin \
  roles/serviceusage.serviceUsageAdmin \
  roles/iam.serviceAccountAdmin \
  roles/iam.serviceAccountUser \
  roles/resourcemanager.projectIamAdmin
do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$DEPLOY_SA" \
    --role=$role \
    --quiet
done
```

`roles/iam.serviceAccountUser` at project level also lets the scheduler's OIDC
config and the Cloud Run job reference `energy-job`, which Terraform itself
creates on first apply.

## 4. Workload Identity Federation (GitHub Actions → deployer)

```bash
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition='assertion.repository=="'"$REPO"'"'

gcloud iam service-accounts add-iam-policy-binding $DEPLOY_SA \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO"
```

## 5. Verify (Task 2.1 acceptance)

The impersonation check below needs the calling account to hold
`roles/iam.serviceAccountTokenCreator` on the deployer SA (the primitive Owner
role does not include it):

```bash
gcloud iam service-accounts add-iam-policy-binding $DEPLOY_SA \
  --member=user:$(gcloud config get-value account) \
  --role=roles/iam.serviceAccountTokenCreator
```

```bash
gcloud iam workload-identity-pools describe github-pool --location=global

# A listing as the deployer must succeed without any key material:
gcloud storage ls --impersonate-service-account=$DEPLOY_SA
```

## 6. Terraform init (once per checkout)

```bash
cd gcp/01-european-energy-pipeline/infra
terraform init -backend-config="bucket=$STATE_BUCKET"
```

## 7. Values for the GitHub variables (Task 2.2)

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | `$PROJECT_ID` |
| `GCP_WIF_PROVIDER` | `projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_DEPLOY_SA` | `$DEPLOY_SA` |
| `GCP_STATE_BUCKET` | `$STATE_BUCKET` |
