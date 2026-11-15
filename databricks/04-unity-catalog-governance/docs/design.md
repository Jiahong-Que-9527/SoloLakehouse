# Design: Unity Catalog Governance

**D04 · Design only.** No application code in this directory yet.

Put the financial tables in Unity Catalog and show that an analyst, a risk reader, and a producer do not have the same access. The project proves grants, a controlled view, and a lineage record that matches a release. It does not claim account-level audit features the workspace does not offer.

The source for this scope is the D04 section of the [subproject design note](../../../chatgpt-consulting-subprojects-design.md). The project [brief](../README.md) fixes the roles under test.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Catalog | `finance` when the workspace allows a new catalog. Otherwise a dedicated schema pair inside the allowed catalog, recorded as a constraint. |
| Schemas | `bronze`, `silver`, `gold`, and `consumer`. |
| Environments | `dev` and `prod` are separate schemas or catalogs. A dev writer cannot write prod. |
| Producer | Creates and writes tables in the assigned schemas. |
| Analyst | `SELECT` on `consumer` views over Gold. No `SELECT` on `bronze` or `silver`. |
| Risk analyst | `SELECT` on a controlled view that exposes the synthetic sensitive columns this role is allowed to see. |
| ML engineer | `SELECT` on a feature view that lists approved columns and a pinned `release_id`. |
| Auditor | `SELECT` on the release and grant-evidence tables. No write on observations. |
| Sensitive columns | v1 uses a controlled view that omits or hashes synthetic account-like fields. Column masking is used only when the workspace supports it, and the evidence says which one ran. |
| Quality | A failed uniqueness or null check does not update the consumer view's release pointer. |
| Free Edition | Checks the workspace cannot run stay open. They are listed in the evidence as `not_available`. They are not marked passed. |

## 2. Boundary

In scope: names, grants, the views, the release pointer, lineage from Bronze to Gold for the D01-shaped fixture, and one recorded permission change.

Out of scope: building the ECB pipeline, account SCIM integration, and a full audit-log product. D02 may be the writer. This project can seed the tables itself so the grants are testable without D02 deployed.

## 3. Architecture

```text
Unity Catalog
  finance
    bronze / silver / gold     producer write
    consumer                   analyst, risk, and ML read
          |
          +--> fx_indicator_current          analyst
          +--> transaction_risk_detail       risk analyst
          +--> forecast_feature              ML engineer
          |
          +--> release and grant evidence    auditor
```

Lineage is read from Unity Catalog for the Gold table back to the Silver and Bronze tables produced by the fixture job. If lineage is not available in the edition, the release row still stores input table version, output table version, and job id, and the lineage check is `not_available`.

## 4. Grant matrix

| Role | bronze | silver | gold tables | consumer views | release table |
|------|--------|--------|-------------|----------------|---------------|
| Data engineer | write | write | write | write | write |
| Data analyst | none | none | none | read indicators | none |
| Risk analyst | none | none | none | read risk view | none |
| ML engineer | none | none | none | read feature view | none |
| Auditor | none | none | none | none | read |

Grants are `GRANT` and `REVOKE` statements kept in the bundle or Terraform, not clicks. A permission test uses a token or an executed-as identity for that role.

The risk view's underlying fixture may contain `account_token` and `counterparty`. The analyst view does not select those columns. The risk view selects them. A revoked grant is tested by running the same query again and recording the denial.

## 5. Behaviour

1. The producer publishes by writing Gold and then moving `consumer.current_release` to that `release_id`. Readers use views filtered to the current release.
2. The quality task runs before that pointer moves. A duplicate `(series_key, observation_date)` leaves the pointer on the previous release.
3. The auditor reads a `grant_change` row written by the deploy: who, role, object, action, git sha, time. v1 records changes made by this project's deploy, not every workspace audit event.
4. Dev and prod objects are named so a test cannot point the prod consumer view at a dev table.

## 6. Delivery and cost

Use the D01 sample or a smaller copy. Identity tests are a few queries, then the warehouse stops. No all-purpose cluster is required for the grant checks if the SQL warehouse can run them.

Enterprise-only items, checked explicitly and left open when absent:

- account-level audit log delivery
- column masking policies
- system tables for lineage beyond what the workspace shows

## 7. Acceptance

1. Producer publishes. Analyst reads the indicator view and is denied on Bronze. Risk reads the risk view. After `REVOKE`, the analyst query fails. Record each identity and response.
2. An invalid fixture fails the quality check. The consumer view still returns the previous release id.
3. Show lineage from the Gold table to its inputs, or record `not_available` with the workspace edition. Show one `grant_change` row for a revoke.

## 8. Handoff

D05's feature read is the `forecast_feature` view, pinned to a release id. D06 may turn this grant set into a template. The template must not grant `USE CATALOG` broadly to consumer roles.
