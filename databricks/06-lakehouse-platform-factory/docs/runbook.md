# D06 validation and operator runbook

## Validate the template

The committed Alpha and Bravo inputs contain fictional identities. From this directory, run the same checks as GitHub Actions.

```bash
PYTHONPATH=notebooks python3 -m unittest discover -s tests -v
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false -input=false -lockfile=readonly
terraform -chdir=terraform validate
terraform -chdir=terraform test -verbose -json > /tmp/d06-tf-test.jsonl
python3 scripts/verify_stack_contract.py /tmp/d06-tf-test.jsonl
```

Terraform reads the real provider schema and uses Terraform's mock provider for the two plans. The verifier feeds their exact output values into Databricks CLI strict Bundle validation against a loopback Workspace stub. It checks schema names, grants, state paths, Bundle roots, task dependencies, service principal IDs and schedule settings. The `d06-stack-contract` CI artifact holds the resolved stack inventory.

## Run the reference job on Free Edition

From a checkout of the code to verify, use an existing CLI profile with Workspace and Jobs access. The smoke runner creates timestamped schemas and workspace notebooks for a single identity, then submits the resolved reference tasks as ad hoc jobs.

```bash
python3 scripts/run_free_edition_smoke.py \
  --profile slh-free --evidence /tmp/d06-reference-smoke.json
```

The runner verifies one published Gold row, repeats the run and checks the same row, then feeds an empty value through Bronze and Silver. It expects the quality task to fail and checks that Gold still contains the original row. The evidence includes run IDs and task outcomes. This exercise uses single-identity Workspace and Jobs access. The Terraform apply, service-principal grant checks and retirement exercise use the multi-principal path below.

## Deploy when a multi-principal workspace is available

Use a workspace operator profile with permission to create schemas, manage schema grants, deploy to its own Workspace folder and assign the runtime service principal to a job. The catalog, account identities and reader groups are operator-managed prerequisites. Give each runtime and Gold reader `USE CATALOG` on the existing catalog. Give the two runtime identities access to the workspace and compute. For SQL acceptance, grant the designated callers `CAN USE` on the chosen warehouse. Review inherited privileges before the isolation exercise.

Terraform owns the three schemas and their schema grants. The Bundle owns the job, tasks, schedule settings and Workspace deployment files. The job owns its three fixture tables. Use the same deployer for a stack's updates. Supply dedicated catalog storage through the existing catalog configuration.

Replace the fictional values in a copy of an example stack file. Use a different application ID and reader group for each team. For the retirement drill, configure Bravo with `environment=dev` and `disposable=true` before its first apply. Use the shown production example for schedule validation.

Run the following from this directory in Bash. Set the variables to the actual stack file, operator profile and a persistent state directory private to this workspace.

```bash
stack_file="$(realpath "$STACK_CONFIG_FILE")"
export DATABRICKS_CONFIG_PROFILE="$FACTORY_OPERATOR_PROFILE"
paths=$(python3 scripts/stack_paths.py "$stack_file" --state-root "$FACTORY_STATE_ROOT")
export TF_DATA_DIR=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data_dir"])' <<< "$paths")
state=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])' <<< "$paths")
mkdir -p -- "$(dirname "$state")"
terraform -chdir=terraform init -input=false -backend-config="path=$state"
terraform -chdir=terraform plan -var-file="$stack_file" -out="$TF_DATA_DIR/apply.tfplan"
terraform -chdir=terraform show "$TF_DATA_DIR/apply.tfplan"
```

Review the six resource addresses, schemas, principals and `force_destroy` setting. Apply the reviewed plan and pass its outputs to the Bundle.

```bash
terraform -chdir=terraform apply "$TF_DATA_DIR/apply.tfplan"
target=$(terraform -chdir=terraform output -raw bundle_target)
bundle_vars=$(terraform -chdir=terraform output -json bundle_vars)
mapfile -t assignments < <(
  python3 -c 'import json,sys; print(*(f"{k}={v}" for k,v in json.load(sys.stdin).items()), sep="\n")' <<< "$bundle_vars"
)
bundle_args=(-p "$DATABRICKS_CONFIG_PROFILE" -t "$target")
for value in "${assignments[@]}"; do bundle_args+=(--var "$value"); done
databricks bundle validate --strict "${bundle_args[@]}"
databricks bundle deploy "${bundle_args[@]}"
databricks bundle summary "${bundle_args[@]}"
databricks bundle run batch_lakehouse "${bundle_args[@]}"
```

Use one working state directory per stack and keep it between reruns. A shared runner will need a persistent, access-controlled backend and a workspace deployment identity before a live deployment workflow is enabled. Current GitHub Actions only validate the template and publish the plan-derived inventory.

## Live isolation and retirement checks

- Capture the Git revision, Terraform stack ID, job ID, run ID and elapsed onboarding time. Verify each job publishes one Gold row with its own stack ID. Use the job output to verify the actual runtime identity.
- Replan and rerun one stack with unchanged inputs. Expect no Terraform changes, the same job ID and one Gold row. Change the job's `fixture_value` parameter in the bundle, redeploy and repeat. If a run fails after deployment, record the stack as deployed and unverified. Resume with the same state and parameters.
- Query the fully qualified Gold table on each team using that team's runtime identity. Then query Bravo's Gold using Alpha's identity through that same warehouse and record the permission denial. Query as Bravo to confirm the table exists and the failure is due to authorization.
- Retire a reviewed disposable dev stack. Record the current job, schemas and tables and save the isolation evidence. With its exact backend and bundle arguments, run `terraform -chdir=terraform plan -destroy -var-file="$stack_file" -out="$TF_DATA_DIR/retire.tfplan"` from the project directory, then review the plan. After approval, destroy the reviewed Bundle first and apply the reviewed Terraform retirement plan. Verify the retired job and schemas are gone and re-query the surviving team's Gold row.
