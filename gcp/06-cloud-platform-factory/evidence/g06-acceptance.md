# G06 · Acceptance evidence

WSL2 + GitHub Actions, 2026-11-23. Project `slh-gcp-test`, region
`europe-west3`. Every apply and destroy ran through the
`G06 cloud platform factory` workflow with Workload Identity Federation
as `g06-deployer@slh-gcp-test.iam.gserviceaccount.com` — no service-account
key exists anywhere in the repository (design §1).

## Acceptance 1 · Two isolated stacks from one template

- Stack **alpha** applied in run `45262108548` (after the label fix): 9
  resources added on top of the partial first apply; stack **bravo**
  applied in run `45266049800`: **11 added, 0 changed, 0 destroyed**.
- Separate resources, all name-prefixed:
  `slh-batch-dev-alpha` / `slh-batch-dev-bravo` buckets,
  `slh_batch_dev_alpha` / `slh_batch_dev_bravo` datasets,
  `slh-batch-dev-alpha-runtime@…` / `slh-batch-dev-bravo-runtime@…`
  runtime identities, one Cloud Run Job each.
- Each stack's smoke job wrote its row with its **own** runtime
  principal: `alpha,slh-batch-dev-alpha-runtime@…` and
  `bravo,slh-batch-dev-bravo-runtime@…` (visible in the run logs and
  queried back from BigQuery).

## Acceptance 2 · Deployed from GitHub Actions with short-lived credentials

- Every dispatch run authenticated via WIF (job log shows
  `google-github-actions/auth@…` against the `github-pool` provider;
  the provider's attribute condition pins it to this repository).
- Budget alerts `g06-stack-alpha` / `g06-stack-bravo` (EUR 5 each,
  thresholds 50 % / 90 %) exist at the billing account; recorded in
  [BOOTSTRAP](../infra/BOOTSTRAP.md). Costs observed: KB-scale storage,
  a handful of KB-scale queries — inside the free tier, no credits spent.

## Acceptance 1b · Isolation (the cross-read denial)

- Alpha's runtime identity, impersonated for the check, queried bravo's
  `smoke_results` table → **403 PERMISSION_DENIED**
  (`bigquery.tables.getData denied on table slh-gcp-test:slh_batch_dev_bravo.smoke_results`).
- Positive control: the same identity reading its own table → **200**
  with rows.

## Acceptance 1c · Repeat apply is a no-op

- Second apply of alpha (run `45265387169`): **"No changes. Your
  infrastructure matches the configuration."** — 0 added, 0 changed,
  0 destroyed.

## Acceptance 3 · Teardown and residual inventory

- Stack **bravo destroyed** in run `45269001470`; the workflow's residual
  inventory and an independent check (gsutil/bq/gcloud/run-jobs, all
  filtered on `bravo`) found **zero** remaining resources.
- Stack **alpha destroyed** in run `45270733200` after the isolation
  evidence was recorded; independent check: **0** buckets, datasets and
  jobs matching `slh-batch` remain. The shared bootstrap resources
  (state bucket, WIF pool, budgets, Artifact Registry) remain by design
  and are listed in BOOTSTRAP.md.

## Developer-experience measure and friction list

- Time from image build to first verified smoke row: **≈52 min**
  (20:05 → 20:57), dominated by two real defects found and fixed on the
  way, plus CI-merge latency on a busy repository.
- Defects found by the drills and fixed the same day:
  1. GCP label values reject `@`/`.` — the owner label is now sanitised
     (the full address stays in BOOTSTRAP.md and tfvars).
  2. `google.auth` on Cloud Run reports `default` — the reference
     workload reads the real principal from the metadata server (image
     v2; stacks re-pinned).
  3. Cloud Run Jobs default to `deletion_protection=true` — disabled in
     the module; a destroy before an apply-with-the-flag is refused by
     design and re-converges via apply → destroy.
  4. Bootstrap gaps: the Cloud Build SA lacked `cloudbuild.builds.builder`
     and the owner lacked `serviceusage.serviceUsageConsumer`.
- One recorded lesson in `scoring`-adjacent code and BOOTSTRAP: `bq mk`
  parses `name:TYPE` schema pairs.

## Remaining after the exercise

- The `api` and `governed` templates stay module boundaries (design §1);
  they are added only after G02/G04 each have a successful apply of
  their own.
- Stack state prefixes `g06/stacks/{alpha,bravo}` remain in the state
  bucket (empty after destroy); bootstrap resources remain per the
  table above.
