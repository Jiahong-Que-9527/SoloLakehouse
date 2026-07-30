---
name: slh-context-router
description: "Route SoloLakehouse work through Graphify to the smallest authoritative context, appropriate tools or agents, and focused validation plan. Use for backlog questions, code changes, architecture analysis, operations, documentation, GitHub work, or multi-agent delegation—especially after an Owner Decision or whenever broad repository loading would be wasteful."
---

# SoloLakehouse Context Router

Select only the context needed to answer or execute the request. For unapproved significant work, ask for or create an Owner Decision through `$slh-platform-owner` before routing implementation.

## Route the request

1. Classify it using `references/routing-map.md`.
2. Use `$graphify` as the discovery layer for every question about this project when `graphify-out/graph.json` exists. Query the task in natural language before opening repository files. Use `graphify path` for a relationship or dependency trace, and `graphify explain` for an unfamiliar concept.
3. Turn the graph result into a minimal source list. Open only the returned canonical documents, target modules, and matching tests; verify claims against those sources because graph edges are navigational evidence, not authority.
4. State the baseline constraints and exclusions before editing.
5. Select the narrowest tool/agent and validation command that can prove the requested outcome. After modifying repository content, run `graphify update .` so the discovery layer remains current.

## Graphify protocol

Run one of these before broad repository browsing:

```bash
graphify query "<task or question>"
graphify path "<source concept>" "<target concept>"
graphify explain "<unfamiliar concept>"
```

Use `query` by default. Use `path` only when the task depends on an exact relationship, such as caller-to-service, dataset-to-consumer, or document-to-decision. Use `explain` to orient on a node before reading its source.

If `graphify-out/graph.json` is absent, use the routing map's canonical entrypoints, then restore Graphify discovery when the graph becomes available. Do not rebuild a healthy graph merely to answer a question.

## Return a routing brief

```markdown
## Context Route
- Task class: <class>
- Decision input: <Owner Decision, or why a one-sentence owner impact is enough>
- Canonical context: <ordered, minimal file list>
- Exclude: <nearby but non-authoritative or out-of-scope material>
- Baseline constraints: <must-preserve behavior and version boundaries>
- Graphify trace: <query/path/explain and the source nodes retained>
- Route: <Graphify / code / docs / ops / review / delegated roles>
- Validation: <focused commands and observable expected results>
```

For an answer-only request, stop after the brief and answer from the selected sources. For an implementation request, use the brief as the working contract.

## Multi-agent routing

Give every delegated agent:

- the Owner Decision or owner-impact sentence;
- exact canonical files and explicit exclusions;
- baseline constraints;
- one bounded output and validation expectation.

Do not delegate overlapping ownership. Use independent agents only for separable review, research, or validation work; integrate their findings against the canonical sources.

## Boundaries

- Do not redefine priority or approve scope; return to `$slh-platform-owner` when that decision is missing or materially changes.
- Do not load all documentation by default; use Graphify to discover candidates, then prefer `docs/README.md` for navigation and canonical documents for claims.
- Do not treat historical planning, generated documentation, or a graph result as authoritative over the current roadmap, code, tests, or runbooks.
