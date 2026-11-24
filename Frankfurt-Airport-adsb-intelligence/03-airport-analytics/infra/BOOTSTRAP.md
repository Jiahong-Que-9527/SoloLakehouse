# BOOTSTRAP — one-time setup outside Terraform

Same model as [G01](../../../gcp/01-european-energy-pipeline/infra/BOOTSTRAP.md):
the resources below pre-date this stack and cannot create themselves.

## Already done (shared with G01/G02/G04)

- **State bucket** `slh-gcp-test-tfstate` — the current configuration uses the prefix
  `frankfurt-airport/03-airport-analytics`.
- **GitHub WIF pool/provider and the `github-deployer` service account** —
  the CI workflow reuses the repo variables `GCP_PROJECT_ID`,
  `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`, `GCP_STATE_BUCKET`.
- **Grant the WIF principal access** — the deploy service account must be
  able to administer this project (same grant pattern as G01).

## Migrating the existing Airport Analytics state

The stack now expects the prefix `frankfurt-airport/03-airport-analytics`.
CI requires an initialized, populated state at that prefix. Before the
first plan or apply, initialize the previous configuration from commit
`7965049b9df21e0c4075d89cbd2d0ea729dc585f` in a separate checkout with the existing state
bucket. Keep its local backend metadata, switch that checkout to the new
configuration and move that metadata into the renamed infrastructure directory
if it did not move with the directory. Run `terraform init -migrate-state`
there with the same bucket and confirm `terraform state list` shows the
existing resources before planning. Review the plan for resource replacements,
including the scheduler display name, before applying.

## One-time grant for the budget resource

`google_billing_budget` needs budget-management rights on the billing
account `01FCE3-C90698-BFE584`. The budget IAM roles are not grantable
directly (there is no `roles/billing.budgetsEditor`); the least-privilege
predefined role is Billing Account Costs Manager. Billing-account IAM
cannot be granted through this project's Terraform, so run once as the
owner (done 2026-11-21):

```bash
gcloud billing accounts add-iam-policy-binding 01FCE3-C90698-BFE584 \
  --member "serviceAccount:github-deployer@slh-gcp-test.iam.gserviceaccount.com" \
  --role roles/billing.costsManager
```
