# G06 factory bootstrap (as-built, 2026-11-23)

Out-of-Terraform prerequisites, created with `gcloud`/`gsutil` by the
owner before the first apply (playbook §1). Anything created later by
Terraform lives inside the stacks and is destroyed with them.

## Reused (already existed)

| Resource | Id | Notes |
|---|---|---|
| Test project | `slh-gcp-test` | one project, dataset-level isolation (design §6) |
| State bucket | `gs://slh-gcp-test-tfstate` | one prefix per stack: `g06/stacks/<name>` |
| WIF pool + provider | `github-pool` / `github-provider` (global) | OIDC, attribute condition pins it to repo `Jiahong-Que-9527/SoloLakehouse`; no key material anywhere |
| Billing account | `01FCE3-C90698-BFE584` | free trial |

## Created for G06

| Resource | Id | Purpose |
|---|---|---|
| Deploy identity | `g06-deployer@slh-gcp-test.iam.gserviceaccount.com` | distinct from every runtime identity (design §4) |
| Deploy roles | `run.admin`, `storage.admin`, `bigquery.admin`, `artifactregistry.admin`, `iam.serviceAccountAdmin`, `iam.serviceAccountUser`, `resourcemanager.projectIamAdmin`, `logging.configWriter`, `serviceusage.serviceUsageConsumer` | scoped to stack resources; no billing roles |
| WIF binding | `roles/iam.workloadIdentityUser` on `g06-deployer`, member `principalSet://…github-pool/attribute.repository/Jiahong-Que-9527/SoloLakehouse` | only this repository may impersonate the deployer |
| Budget alert | `g06-stack-alpha` (EUR 5, thresholds 50 % / 90 %) | alert only; hard controls are max instances, workload limits and destroy (design §1) |
| Budget alert | `g06-stack-bravo` (EUR 5, thresholds 50 % / 90 %) | idem for stack B |
| Artifact Registry | `g06-factory` (DOCKER, `europe-west3`) | holds the reference workload image, digest-pinned in the stacks |
| Cloud Build fixes | `roles/cloudbuild.builds.builder` on the build SA; `roles/serviceusage.serviceUsageConsumer` on the owner | the build SA could not read its uploaded source — bootstrap gap found and closed |

## Reference workload image

`europe-west3-docker.pkg.dev/slh-gcp-test/g06-factory/reference-batch@sha256:5d25938cfc753d16e9c2751f2df65b389afaa2f8bc341107bea6eee969edb2f3`
built once via Cloud Build from `reference-workload/` (a 40-line job that
reads its stack's fixture object and inserts one smoke row). Stacks pin
the digest; the image is rebuilt only when the reference workload changes.

## Bootstrap record for a new operator

1. Reuse the pool/provider and the state bucket above (no new key material).
2. Create `g06-deployer` with the deploy roles and the WIF binding.
3. Create one named budget per stack at the billing account.
4. Build/push the reference image and pin its digest in both stacks.
