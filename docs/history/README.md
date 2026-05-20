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
- [v2.6-planning.md](v2.6-planning.md): planned governance evidence bedrock (data contracts, lineage evidence pack, WORM audit)
- [v2.7-planning.md](v2.7-planning.md): planned sovereignty and openness evidence (multi-engine Iceberg, exit playbook)
- [v2.8-planning.md](v2.8-planning.md): planned ML compliance bedrock (MLflow ↔ Iceberg snapshot binding, model card)
- [v2.9-planning.md](v2.9-planning.md): planned operational readiness (SLO emit, secrets discipline, promotion/rollback drill)
- [v3-planning.md](v3-planning.md): draft plan for production infrastructure and governance

## How to maintain

For each new milestone (for example `v2.0.0`):

1. Add an entry to `timeline.md` with status, outcomes, and next gate.
2. Update `architecture-evolution.md` with what changed and why.
3. Copy `planning-template.md` into a versioned planning note (for example `v2-planning.md`) and fill it before implementation starts.
4. Cross-link release artifacts (tag, PR, release notes, checklist).
