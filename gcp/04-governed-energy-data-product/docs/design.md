# Design: Governed Energy Data Product

**G04 · Design only.** No application code in this directory yet.

Publish an energy table only after its contract and quality gate pass, and make that publication traceable to a source release, a commit, and an allowed reader. The project proves a release boundary. It does not prove a company-wide catalog.

The source for this scope is the G04 section of the [subproject design note](../../../chatgpt-consulting-subprojects-design.md). The project [brief](../README.md) fixes the first release.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| First product | `energy-load`, the German actual-load metric from G01 or from a fixture with that schema. |
| Specified, not required for v1 | `energy-prices` and `renewable-generation`. Their contracts are written. Their publish runs against fixtures. They are not blocked on a live ENTSO-E feed. |
| Source of record | A release manifest in the repository's evidence and a BigQuery row in `energy_product.release`. A catalog entry mirrors that row when the API is available. |
| Catalog | Dataplex Universal Catalog, now exposed as Knowledge Catalog, is the place lineage is shown. If the test project cannot call it, the manifest still records producer, input release, output table, and commit. The design does not treat a missing catalog call as a passed lineage check. |
| Failure | A failed gate writes a quarantine report and does not replace the published view. The previous release stays queryable. |
| Access | Three identities: producer, analyst, auditor. The analyst can query the published view and cannot query the source table or the quarantine table. |
| Withdraw | A withdraw removes the current view's grant target and marks the release `withdrawn`. Republish creates a new release id. It does not edit the old manifest. |

## 2. Boundary

In scope: the contract, the gate, publish and withdraw, IAM for the three identities, and the lineage record from input release to published view.

Out of scope: building the source pipeline, an external data mesh, and column-level policies beyond the view. G06 may later template this flow. This project implements it once.

## 3. Architecture

```text
Input release or fixture
          |
          v
Contract check
          |
          v
Quality gate
          |
          +-- fail --> quarantine table + report, published view unchanged
          |
          v
energy_product.<product>_v<release>
          |
          v
authorised view energy_product.<product>_current
          |
          +--> analyst grant
          +--> release row and manifest
          +--> catalog link when the API accepts it
```

## 4. Contract

Each product has one YAML contract. v1 values for `energy-load`:

```yaml
data_product: energy-load
version: 1.0.0
contract:
  schema_version: 1
  grain: [area, metric, interval_start]
  required_columns: [interval_start, interval_end, area, metric, value, unit, release_id]
quality_gates:
  completeness_min: 1.0
  duplicate_business_keys_max: 0
  value_min: 0
  freshness_hours_max: 48
release:
  approval_required: true
  record_manifest: true
```

`completeness_min: 1.0` matches a fixed historical week, where every interval is known. A live feed may lower `freshness_hours_max` only by changing the contract version. Thresholds are not hidden in code.

`energy-prices` uses `metric=day_ahead_price_eur_mwh` and an hourly grain. `renewable-generation` uses `metric=renewable_generation_mw`. Both keep the same required columns so a consumer can read them through the same view shape.

## 5. Behaviour

1. The producer submits an input `release_id` and a contract version. A human or a protected CI job sets `approved=true`. An unapproved input cannot publish.
2. The gate checks schema, grain uniqueness, completeness against the expected interval count, the value range, and freshness against `ingested_at`.
3. Failure writes the offending keys to `energy_product.quarantine` and a report. `energy-load_current` still points at the previous passed release.
4. Success copies the window into a release table named with the new release id, points `_current` at it, and writes the manifest: contract version, input release id, output table, git sha, gate results, approver.
5. Withdraw flips the release status and replaces `_current` with the previous passed release, or with an empty authorised view if none remains.
6. The analyst identity is tested by querying `_current` and by a denied query on the source table. The auditor can read `release` and the manifest and cannot edit observations.

## 6. Delivery and cost

The dataset is the small G01 week or a smaller fixture. Grants are Terraform resources. The gate is a Python command run from CI against the fixture, and from Cloud Run Job against a cloud input. Catalog registration is a separate step that records its own success or a named gap.

## 7. Acceptance

1. An input with a duplicate key or a null measure does not change `_current`. The failed gate result and the previous release id are both queryable.
2. The analyst identity reads `_current` and is denied on the source table. Record the identities and the two responses.
3. A published row traces to the manifest, the input release, and the git sha. Record the catalog lineage link or the explicit gap.
4. Withdraw, then republish. The new release id differs, and the withdrawn id remains in `release`.

## 8. Handoff

G05 trains only on a release id whose status is `passed`. G02 may point its view at `_current`. Neither inherits this project's producer identity.
