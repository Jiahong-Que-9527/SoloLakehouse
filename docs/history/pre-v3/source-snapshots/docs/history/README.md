# History

This folder tracks how SoloLakehouse evolves across versions and why key architecture choices were made.

Use it as the long-term continuity layer between roadmap intent and implementation details.

## Documents

- [timeline.md](timeline.md): version-by-version evolution path from v1 onward
- [architecture-evolution.md](architecture-evolution.md): major architecture decisions over time and their trade-offs
- [legacy-overview.md](legacy-overview.md): retired runtime paths and archive references
- [planning-template.md](planning-template.md): reusable planning template for v2/v3/v4 milestones
- [v2-planning.md](v2-planning.md): delivered v2 planning and migration notes
- [v2.5-planning.md](v2.5-planning.md): delivered v2.5 planning notes
- The v2.6–v2.9 planning notes are superseded 2026-05-05 snapshots. They are
  kept in maintainer working copies only and are not published; see
  [../roadmap.md](../roadmap.md) for the authoritative scope of each version.
- [v3-planning.md](v3-planning.md): draft plan for production infrastructure and governance
- [ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md): archived 2026-04 lakehouse assessment (SUPERSEDED)
- [project-state-overview-2026-05-05.md](project-state-overview-2026-05-05.md): archived EN state snapshot (SUPERSEDED)
- [v2.6-execution-plan.md](v2.6-execution-plan.md): delivered v2.6 execution order (SUPERSEDED)
- [v2.6-demo-goal.md](v2.6-demo-goal.md): delivered v2.6 demo goal note (SUPERSEDED)

## How to maintain

For each new milestone (for example `v2.0.0`):

1. Add an entry to `timeline.md` with status, outcomes, and next gate.
2. Update `architecture-evolution.md` with what changed and why.
3. Copy `planning-template.md` into a versioned planning note (for example `v2-planning.md`) and fill it before implementation starts.
4. Cross-link release artifacts (tag, PR, release notes, checklist).
