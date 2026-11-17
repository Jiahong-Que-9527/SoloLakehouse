# Design: Lakehouse Platform Factory

**D06 · Design only.** No application code in this directory yet.

Give another data team a catalog, a schema, a job, and a grant set from a template, and show that the team can run its job without reading the first team's tables. The project proves reuse of the deploy path. It does not prove a platform organisation.

The project [brief](../README.md) fixes the ownership split.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| v1 template | `batch-lakehouse`: schemas for Bronze, Silver, and Gold, one Lakeflow Job, a quality task, and a reader grant on Gold. |
| Specified next | `incremental-lakehouse` (Auto Loader, checkpoint, MERGE) and `ml` (feature task, MLflow experiment, batch score). They are documented shapes. v1 acceptance is the batch template only. |
| Ownership | Terraform, or the workspace provider in use, creates the catalog or schema and the grants. Declarative Automation Bundles create the job, tasks, and pipeline resources. |
| One owner | A resource is named in one tool. The bundle does not also create the schema. Terraform does not also define the job. |
| Targets | `dev` and `prod` differ by schema name and by whether a schedule exists. `dev` has no schedule. |
| Isolation | Two stacks, two schemas, two runtime identities. Identity A runs A's job and is denied `SELECT` on B's Gold. |
| CI | Tests and `bundle validate` on pull requests. Deploy is a manual dispatch. |
| Destroy | A disposable stack can be destroyed. The evidence lists remaining tables and jobs. |
| Guide | The operations section below is the runbook until a separate operator needs one. |

## 2. Boundary

In scope: the template inputs, the ownership split, two-stack isolation, and create, update, destroy.

Out of scope: a self-service portal, copying D01's ECB logic into every new project, and account-level identity provisioning. The reference job writes a fixture row through Bronze, Silver, and Gold. A real team replaces the fixture task with its own code after the template deploys.

## 3. Architecture

```text
New team name and template id
          |
          v
GitHub Actions
          |
          +--> Terraform: catalog or schema, grants, storage prefix
          |
          +--> Bundle: Lakeflow Job, quality task, target schema
          |
          v
Smoke run and a short deployment report
```

Stack id is `slh-<team>-<env>`. Schema names include that id. The report records git sha, schema, job id, smoke run id, and the identity used.

## 4. Template contract

Inputs: `team`, `environment`, `template`, `owner`. Outputs: schema names, job name, runtime identity, and the smoke command.

The batch job has three tasks: land the fixture, merge Silver on a declared key, and publish Gold only if the key is unique. That is the same stop-on-failed-quality rule as D02, reduced to one fixture.

The reader grant is `SELECT` on that team's Gold schema. The team's runtime identity can write its own Bronze, Silver, and Gold. It has no grant on any other team's schema.

`dev` and `prod` bundles are two targets. Prod deploy does not run on a pull request.

## 5. Behaviour

1. Generate or apply the template for team A and team B.
2. Run A's job. Confirm one Gold row in A's schema and no new row in B's schema.
3. Query B's Gold as A's identity. The expected result is a permission error.
4. Change a task parameter, deploy again, and show the job definition matches the bundle. A drift edit in the workspace is not part of the supported path.
5. Destroy B. List jobs and schemas. B's objects are gone. A's smoke row remains.

Terraform state and the bundle target are both keyed by stack id so a second apply of an unchanged stack does not recreate the schema or the job.

## 6. Operations

Create: dispatch the workflow with `team`, `environment`, and `template=batch-lakehouse`.

Verify: read the deployment report and the smoke run id.

Update: change the bundle or the Terraform module, review the plan, dispatch again.

Destroy: dispatch with `action=destroy` for a stack marked disposable. Do not destroy a stack whose report is still the isolation evidence until that evidence is copied into the project record.

Failure: if the bundle deploys and the smoke task fails, the schema remains and the report status is `deployed_unverified`. That is not a successful acceptance.

## 7. Delivery and cost

Both stacks use the smallest warehouse and a handful of fixture rows. No schedule is enabled for the proof. If the workspace cannot create a catalog, both stacks are schemas in the allowed catalog and the evidence says so. Grants still have to isolate them.

## 8. Acceptance

1. Two stacks from the same template, two successful smoke runs, two Gold tables.
2. Team A's identity reads A's Gold and is denied on B's Gold.
3. The report names the tool that owns the schema and the tool that owns the job. CI shows validate and the deploy run.
4. Destroy the disposable stack and record what remains.

## 9. Handoff

G06 is the GCP counterpart and is not a dependency. A team that needs both clouds uses both templates and keeps separate identities. Aviation lakehouse work stays in the Fraport programme. It may copy this bundle layout. It does not deploy through this factory's state.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
