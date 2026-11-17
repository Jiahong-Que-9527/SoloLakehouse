# Design: Cloud Platform Factory

**G06 · Design only.** No application code in this directory yet.

Give a new data project a standard GCP footprint: identity, storage, warehouse, a place to run, logs, and a budget signal, created and destroyed from GitHub. The project proves that a second environment can be made from the same template without copying keys or sharing another project's data.

The project [brief](../README.md) fixes the first proof.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| v1 template | `batch`. It creates a bucket, a BigQuery dataset, a Cloud Run Job, a runtime service account, and a log sink. |
| Specified next | `api` (Cloud Run Service, invoker IAM, logging) and `governed` (dataset, three identities, a release table). They are module boundaries in this design. v1 acceptance does not require them to be applied. |
| Credentials | GitHub Actions obtains a short-lived token through Workload Identity Federation. The repository stores no service-account JSON key. |
| Isolation | Two test stacks from the same template, different state prefixes and different resource names. A runtime identity in stack A cannot read stack B's dataset. |
| Repeat apply | A second `terraform apply` with no input change produces an empty plan. |
| Destroy | One stack is destroyed through the same workflow. The other stays as the isolation check. |
| Cost signal | A budget alert is attached. It does not stop spend. The hard controls are maximum instances, query limits in the workload, and destroy. |
| Evidence | Each apply writes a resource inventory, the git sha, and the smoke-test result. Evidence is a short record, not a log dump. |

## 2. Boundary

In scope: the Terraform modules, the workflow, federation, the two-stack proof, and the destroy proof.

Out of scope: replacing G01's pipeline code, a self-service UI, and production organisation policy. The template deploys a reference workload that writes one fixture row. It does not import the energy pipeline.

G01 and G02 remain the place their own resources are learned. This project copies the resulting shape into modules after those resources exist. Until then, the reference workload is a one-task job that reads a fixture object and inserts one row.

## 3. Architecture

```text
Developer selects template, name, and environment
          |
          v
GitHub Actions
          |
          v
Workload Identity Federation
          |
          v
Terraform
          |
          +--> bucket, dataset, job, service account, logging, budget
          |
          v
Smoke test, then inventory
```

Stack names are `slh-<template>-<env>-<suffix>`. State lives in a dedicated bucket, one prefix per stack. The workflow role can apply and destroy only stacks with that prefix.

## 4. Template contract

Inputs: `template`, `environment` (`dev` or `test`), `name`, `region`, and `owner`. Outputs: resource names, runtime service-account email, and the smoke-test command.

The batch module's runtime account can write its own dataset and its own bucket prefix. It cannot create further IAM bindings. The deploy identity can. Those two accounts are different.

Environments differ by name prefix, budget amount, and whether a scheduler is created. `dev` has no scheduler. `test` may have one, paused by default.

## 5. Behaviour

1. `plan` runs on pull requests. `apply` runs on a manual workflow dispatch for `test`.
2. The smoke test executes the reference job once and checks for one inserted row.
3. A second apply is recorded. The expected plan diff is empty.
4. The isolation check uses stack A's runtime token, or an impersonation of it, to query stack B. The expected result is an access denial.
5. Destroy deletes the selected stack. A follow-up inventory lists any remaining resources. Remaining resources are a failed acceptance, not a note.

Format, validate, and a static security check on the Terraform run in CI before plan.

## 6. Delivery and cost

Both stacks stay in one test project or in two, as the operator's organisation allows. The design prefers one project and strict dataset IAM if creating projects is not available. That choice is recorded in the evidence. Either way, the identities cannot read each other.

Budgets are small and named per stack. Resources are destroyed at the end of the exercise except the stack kept for the isolation record. No template sets a minimum instance above zero.

## 7. Acceptance

1. Create two stacks from `batch`. Show separate datasets, buckets, and service accounts. Show the cross-read denial.
2. Show a GitHub Actions run that applied with federation. The run log contains no long-lived key. Record owner, expected monthly budget, and the alert name.
3. Destroy one stack and list what remains. Keep the second stack only as long as the isolation evidence is needed, then destroy it with the same workflow.

## 8. Handoff

When G02 and G04 are stable, their resource lists become the `api` and `governed` modules. A module is added here only after that project has one successful apply of its own. This factory does not become a hidden dependency of G01.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
