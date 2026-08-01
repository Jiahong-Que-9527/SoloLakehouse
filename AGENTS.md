# Agent Guide — SoloLakehouse

Entry point for any AI coding agent (Codex, Cursor, Copilot, Claude, …).
Read this before doing anything. Claude Code users should also read `CLAUDE.md`
for the code-level patterns; this file is the shared, tool-neutral contract.

---

## 1. Where authority lives

Exactly two documents decide what gets built:

| Document | Answers |
|---|---|
| **`docs/roadmap.md`** | What each version does, current status, open decisions |
| **`TASKS.md`** | What the next PR does |

**When any other file disagrees with those two, those two win.** This includes
historical planning notes, dated snapshots, generated documentation, ADRs
describing proposals, and anything under `docs/history/`.

Never treat a roadmap *target* as a delivered *capability*.

---

## 2. Current state (verify against `docs/roadmap.md` before relying on this)

- **Runtime baseline: v2.5.** Docker Compose + Dagster + all-layer Iceberg +
  Trino + MLflow + OpenMetadata + Superset. **This runtime does not change
  before v3.0.** Do not add platform services.
- **Released tag: `v2.6.1`** (2026-07-31, commit `6bd138a`) — corrects the
  version stamp and ships the v2.6 governance/evidence plane (contracts,
  three-source lineage join, manual `make lineage-evidence`). It does **not**
  include Block `J`.
  - `v2.6.0` is superseded: it stamped `slh-v2.5.1` into every evidence
    manifest. Anyone on that tag should upgrade and regenerate.
- **Block `J` on `main`** (2026-08-01, commit `e534c73`, PR #49) — automatic
  emission, Object Lock, five-dataset coverage, causal snapshot↔run binding,
  and CI coverage for `governance/` + `dagster/`. **Implementation complete;
  external validation pending.**
- **Active acceptance gate:** independent external sign-off in
  `docs/external-validation/v2.6.1-external-validation.md` against acceptance
  baseline `e534c73` (or later `main`). See `TASKS.md`.

Each v2.x version adds **one category of evidence** without changing the runtime:

```text
v2.5  the platform runs
  -> v2.6   the platform produces evidence
     -> v2.6.1  that evidence is operational, not just demonstrable
        -> v2.8 / v2.7  auditable-AI evidence  OR  openness evidence
           -> v2.9  operational and promotion evidence
              -> v3.0  the runtime migrates to Kubernetes
```

---

## 3. Decision gates — do not cross these without an explicit decision

Recorded in `docs/roadmap.md` under "Open Decisions". An agent that starts work
behind one of these gates is doing work that may be thrown away.

| Gate | Rule |
|---|---|
| **D1** | v2.7 (`I1`–`I5`) and v2.8 (`E1`–`E4`) are **blocked**. G4 recorded 2026-08-01: provisional **v2.8 first** retained (no external signal to overturn). Implementation still requires external confirmation in `docs/external-validation/v2.6.1-external-validation.md` or an explicit Owner Decision. Do not start either version until then. |
| **D2** | The entity split described in `task.md` is **deferred indefinitely**. It is a design reference, not a backlog. Do not reopen it as a work track. |
| **D3** | The portal / Keycloak exploration is **sandbox only**. It must not enter `docker/docker-compose.yml`, `.env.example`, or any version scope. |

If a task appears to require crossing a gate, stop and surface the conflict
rather than proceeding.

---

## 4. Hard rules

1. **Do not regress the v2.5 baseline.** `make demo` and `make pipeline` must
   keep working. CI gates this with a full Compose run.
2. **Fail loudly, never partially.** Quality checks and evidence adapters raise
   rather than degrade. Never emit an evidence artifact that looks complete but
   is not — a partial bundle is worse than none.
3. **Do not overstate.** No compliance certification, WORM/immutability, or
   regulatory-readiness claim without an implementation and a verification
   record. Limitations belong in `CHANGELOG.md` and the release-readiness doc.
4. **English only.** The published repository contains English documentation
   only. Chinese working documents live in `docs/local-cn/` and are gitignored.
   Do not add non-English files to the repository.
5. **Do not add engines or services** to chase maturity. Engine count is not a
   success metric — see the roadmap's alignment rules.
6. **Estimate with the measured rate.** v2.6 was planned at 4 weeks and took
   11.7 (≈2.9×). Publish version *order*, not dates.

---

## 5. Validation — run these before claiming done

```bash
make test               # unit tests, no Docker required
make lint               # ruff
make typecheck          # mypy over ingestion/ transformations/ ml/ scripts/ dagster/ governance/
make validate-contracts # every governance/datasets/*.yaml against the contract schema

# Requires the stack to be up (make setup / make up):
make verify             # service health checks
make demo               # acceptance data flow; asserts Gold is queryable via Trino
```

Evidence proportional to the claim:

- runtime behaviour → a reproducible command, its output, and a test
- governance → a machine-readable artifact plus its validation result and limits
- architecture → an ADR, or an explicit reason none is needed
- release → the readiness checks in `docs/v2.6-release-readiness.md`

"Code merged", "document written", or "service running" is **not** evidence.

---

## 6. Repository map (short form)

| Path | Contents |
|---|---|
| `ingestion/` | Collectors, Pydantic schemas, Bronze quality checks, `iceberg_io.py` |
| `transformations/` | Bronze→Silver→Gold; each file has a pure transform plus a `run()` |
| `governance/` | v2.6 contracts, quality gates, lineage adapters, evidence, audit writer |
| `ml/` | XGBoost/LightGBM with `TimeSeriesSplit`; MLflow tracking |
| `dagster/` | Assets, resources, jobs, schedule, sensor, asset checks |
| `scripts/` | Health checks, bootstrap, contract validation, evidence CLI |
| `docs/` | See `docs/README.md`; `docs/local-cn/` is local-only |
| `tests/` | Unit tests mock Iceberg I/O — no Docker needed |

`CLAUDE.md` carries the code-level patterns (collector, schema, transformation,
Iceberg I/O, governance/evidence, logging, testing). Follow them when adding code.

---

## 7. Multi-agent conventions

- **Do not delegate overlapping ownership.** One agent owns one bounded change.
- **Hand off the constraints, not just the task**: decision-gate status, the
  exact canonical files, explicit exclusions, and the validation command.
- **Update state when you change it.** If your change alters version status,
  scope, or a decision gate, update `docs/roadmap.md` and `TASKS.md` in the same
  PR. Stale planning state is the failure mode this guide exists to prevent.
- **Per-version history maintenance is required** — see the "History
  maintenance" section of `CLAUDE.md`.

### Entry points — all three resolve here

| Tool | Reads first | Role |
|---|---|---|
| **Codex** (and any agent following the `AGENTS.md` convention) | `AGENTS.md` | This file — the shared contract |
| **Claude Code** | `CLAUDE.md` | Points here for state; adds code-level patterns |
| **Cursor** | `.cursor/rules/sololakehouse.mdc` | Points here; `alwaysApply: true` |

**Version state, decision gates, and hard rules live in this file only.** The
other two are pointers by design — duplicating state into them is how the three
tools drift apart and start working from different targets.

`make check-agent-docs` enforces this mechanically: it fails when an entry point
is missing or unpublished, stops pointing here, or starts duplicating the
version table. It runs in CI.

Two project skills are available under `.agents/skills/`:

- `$slh-platform-owner` — produce an Owner Decision before implementing
  unapproved scope
- `$slh-context-router` — select the minimum authoritative context for a task

---

## 8. Graphify

This project has a knowledge graph at `graphify-out/` with god nodes, community
structure, and cross-file relationships.

When the user types `$graphify`, use the installed graphify skill or
instructions before doing anything else.

Rules:

- For codebase questions, first run `graphify query "<question>"` when
  `graphify-out/graph.json` exists. Use `graphify path "<A>" "<B>"` for
  relationships and `graphify explain "<concept>"` for focused concepts. These
  return a scoped subgraph, usually much smaller than `GRAPH_REPORT.md` or raw
  grep output.
- Dirty `graphify-out/` files are expected after hooks or incremental updates;
  dirty graph files are not a reason to skip graphify. Only skip graphify if the
  task is about stale or incorrect graph output, or the user explicitly says not
  to use it.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of
  raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when
  query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current
  (AST-only, no API cost).

Graphify finds context. **Canonical source files establish facts.** A graph edge
is navigational evidence, not authority.
