<!-- [房玄龄·2026-11-10] Owner-approved single-repository v3 design; no hardware deployment. -->

# Agent guide — SoloLakehouse

Read this before changing the repository. Honor the owner's current task and
invoking workspace instructions, including exact-target file/data approval.

## 1. Authority and reading route

- [docs/roadmap.md](docs/roadmap.md): scope, current position and decisions.
- [TASKS.md](TASKS.md): active order and next verifiable output.
- [docs/design/v3/README.md](docs/design/v3/README.md): detailed v3 construction design.
- [CLAUDE.md](CLAUDE.md): code-level patterns; pointer tools defer here for state.
- [docs/README.md](docs/README.md): bounded reference navigation.

<!-- [房玄龄·2026-11-10] Shared next-session and completion protocol for coding agents. -->

### Starting and handing off work

1. Read roadmap scope and TASKS current stage/next-session output before edits.
   TASKS is the only active TODO, including dependencies and acceptance; do not
   choose a task from a dated prompt, archive, generated graph or tool-local list.
2. Follow the owner's requested scope. Otherwise use the first pending task
   whose required inputs are available. A task being listed is not deployment
   authorization. If an input is missing, record the gap and only advance
   independent authorized work; never invent addresses, versions or credentials.
3. State the task ID, concrete output and verification for the bounded change.
4. In the same PR, update TASKS with actual evidence (commit/PR, command/result,
   remaining gaps and next ID). Check off only proven outputs. Update roadmap
   and detailed design when scope/state/decisions change; do not copy the queue
   into tool-specific entrypoints, skill notes or a second TODO file.

Codex uses this file; Claude Code, Cursor, Gemini and GitHub Copilot have thin
entrypoints pointing here and to roadmap/TASKS. Other agents must use this shared
route. `make check-agent-docs` checks those published pointers; it cannot prove
that every agent product automatically loads or obeys them.

History, old specs, ADR proposals and generated graphs are context, not a
competing backlog. Never treat a target as delivered capability. Use the
smallest relevant source set; do not load the entire history/compendium.

## 2. Current state

- **Runtime baseline: v2.5 reference semantics.** Existing Compose + Dagster +
  all-layer Iceberg + Trino + MLflow + OpenMetadata/Superset paths remain.
- **Released tag:** v2.6.1 predates Block J; evidence work through v2.9 and
  finance L4 phase 1/L5-L7 are on main. This is not current runtime proof.
- **Current work:** D7 framework merged; D1 construction-input decisions are next (see TASKS).
  Three planned 32GB/1TB Mini PCs are not provisioned. New infra/bootstrap/
  deploy/gitops areas are responsibility documents, not implemented deployment.
- The reference cold-clone/image-supply gap remains open; no new Compose or
  hardware result is implied by documentation checks.
- Aviation is the primary separately maintained operated domain; finance is
  this public code reference. Historical/proxy labels are not airport truth,
  and no live air-cargo closed loop is established.
- Training/evaluation/tracking/evidence remain the ML boundary. Serving,
  a portal and an operations agent are later candidates.

## 3. Decisions and exclusions

Read current wording in the roadmap before implementation.

- **D1:** v2 evidence order is historical/delivered; independent external
  sign-off was cancelled as a blocking gate. Internal verification remains.
- **D2:** entity/product split stays deferred indefinitely. A monorepo
  directory layout does not reopen it.
- **D3:** portal/Keycloak remains sandbox-only; no reference stack/env addition.
- **D4/D5:** no retired DAX sample CSV. Live EWG via Alpha Vantage is the
  approved market leg; committed JSON fixtures support controlled tests.
  Preserve calendars, FX, freshness and source limits. Crypto/new domains stay deferred.
- **D6:** private aviation implementation and existing operated fin/avi state
  remain separate. Preserve unfinished evidence/reliability work.
- **D7:** the owner approved the monorepo construction plan, scaffold,
  entry-document rewrite, byte-preserved archive and safe command changes.
  This does not authorize deployment, host installation or data migration.

If a task requires changing these boundaries, surface the concrete conflict.
Do not invent a new approval requirement for already authorized reversible work.

## 4. Hard rules

1. Preserve reference demo/pipeline semantics. Use the manual Compose Demo
   workflow for affected runtime acceptance; do not claim it ran when it did not.
2. Quality/evidence adapters fail loudly; no partial bundle presented as complete.
3. No compliance certification, WORM/immutability, regulatory-readiness, SLA,
   HA or production claim without scoped implementation and verification.
4. **English-only** public documentation; local Chinese working notes remain
   gitignored. Preserve signed historical text; new edits carry an author/date.
5. Do not add engines/services, new domains or extra repositories as a side effect.
6. Publish ordering and actual results, not unsupported delivery dates.
7. Never restore retired DAX CSV paths; legacy schemas/contracts with active
   references require deliberate compatibility work.
8. Preserve original data and backups. No file/volume/database/bucket deletion,
   destructive reset or broad cleanup without exact scope and owner approval.
   No bypass flags or autonomous background disposal.
9. Do not use or restore Hallmark, flywheel-gate, personal-company-strategy,
   or associated mandatory attribution/testing workflows.

## 5. Verification

```bash
make docs-check          # active links, archive hashes and retained-task coverage
make check-agent-docs    # shared entry points and authority
make lint
make typecheck
make validate-contracts
make test
```

Run checks appropriate to the change. Design-only changes do not justify
automatic container startup or a destructive command. Disabled legacy Make
targets must remain non-destructive. Actual IaC/chart definitions later need
their applicable static checks; hardware and data restore need actual runtime
evidence. A skipped check is not a pass.

If state/scope changes, update roadmap and TASKS in the same PR. Maintain
timeline, architecture evolution and the v3 planning cross-link; do not rewrite
historical originals. Keep the archived-task ledger exhaustive.

## 6. Code and tool routing

Keep existing ingestion/transformations/governance/ml/dagster paths for now.
CLAUDE.md describes their patterns; old names are not proof of dead code.
The project skills slh-platform-owner and slh-context-router route bounded work;
current owner authorization takes precedence over historical defaults.

If graphify-out/graph.json exists, query Graphify before broad code navigation;
use query/path/explain, then verify against canonical sources. Dirty graph files
are not a reason to skip it. If absent, use the bounded document route without
installing/rebuilding a graph just for orientation. After code changes update
an available graph; report unavailable tooling rather than fabricating a result.
