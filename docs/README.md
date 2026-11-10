<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design; no hardware deployment. -->

# Documentation

Start with the [project README](../README.md). Current work is single-repository
v3 design; the planned Mini PCs are not provisioned. Existing reference code,
operated-workload reports and future deployment plans have different evidence.

## Current route

| Question | Source |
|---|---|
| What is in scope? | [Roadmap](roadmap.md) |
| What comes next? | [Active work](../TASKS.md) |
| How will the entire platform be constructed? | [V3 construction plan](design/v3/README.md) |
| How are hosts/resources/network and responsibilities arranged? | [Target architecture](design/v3/architecture.md) |
| Where does state live and how is it recovered? | [Storage and recovery](design/v3/storage-and-recovery.md) |
| How do CI, bootstrap, Flux and environments interact? | [Delivery and environments](design/v3/delivery-and-environments.md) |
| How will migration and acceptance proceed? | [Migration and validation](design/v3/migration-and-validation.md) |
| Which older tasks remain? | [Retained-work ledger](design/v3/retained-work.md) |

## Existing reference and workload evidence

- [Reference/operated architecture](architecture.md), [platform story](platform-overview.md),
  [aviation boundaries](workloads/aviation.md).
- [Compose quick start](quickstart.md), [deployment guide](deployment.md),
  [operator runbook](../RUNBOOK.md), [demo](../DEMO.md).
- [Dagster guide](DAGSTER_GUIDE.md), [detailed demo](DEMO_RUNBOOK_EN.md),
  [user guide](USER_GUIDE_EN.md), [capability inventory](capability-showcase-guide.md).
- [Dataset naming](dataset-governance-naming.md), [evidence layout](governance-evidence-layout.md),
  [catalog boundary](catalog-boundary.md), [operational SLO reference](operational-slo.md).
- [ADR index](decisions/README.md), especially [ADR-024](decisions/ADR-024-v3-gitops-monorepo.md).

These retained documents describe their own reference paths and dates. They
are not proof of a fresh deployment or instructions to run every command now.
Do not execute old reset/cleanup examples; current generic destruction targets
are disabled.

## History and specialized reference

The [pre-v3 archive](history/pre-v3/README.md) preserves original planning and
rewritten entry documents with hashes and commit provenance. The
[history index](history/README.md) retains the timeline and architecture evolution.
[External-validation protocols](external-validation/README.md) remain historical;
external sign-off is not a live blocking requirement.

[Compliance mappings](compliance/README.md), [Polaris evaluation](polaris-evaluation.md)
and entity-template material remain specialized reference, not defaults for
v3 execution or new certification claims. Old ADR numbers and URLs are retained.

Generated compendia, local Chinese notes, release checklists and private runtime
configuration may be intentionally gitignored. Their absence from a public
clone is not a missing deployment feature. Use this bounded route instead of
loading the full archive.
