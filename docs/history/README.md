# History

This folder tracks how SoloLakehouse evolves across versions and why key architecture choices were made.

Use it as the long-term continuity layer between roadmap intent and implementation details.

## Documents

- [timeline.md](timeline.md): version-by-version evolution path from v1 onward
- [architecture-evolution.md](architecture-evolution.md): major architecture decisions over time and their trade-offs
- [planning-template.md](planning-template.md): reusable planning template for v2/v3/v4 milestones

## How to maintain

For each new milestone (for example `v2.0.0`):

1. Add an entry to `timeline.md` with status, outcomes, and next gate.
2. Update `architecture-evolution.md` with what changed and why.
3. Copy `planning-template.md` into a versioned planning note (for example `v2-planning.md`) and fill it before implementation starts.
4. Cross-link release artifacts (tag, PR, release notes, checklist).
