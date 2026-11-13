# Aviation

<!-- [Codex · 2026-11-13] Public project entry point. -->

Aviation is a separately operated project for processing historical OpenSky
observations around Frankfurt into candidate arrival events, taxi-in proxy
labels, features and baseline experiments.

- **Public project sources:** SoloLakehouse maintains this entry point, the
  [Aviation roadmap](roadmap.md), and the
  [public case and evidence summary](../../docs/workloads/aviation.md).
- **Private engineering sources:** The independently maintained Aviation source
  repository owns the implemented acquisition, event logic, contracts, tests,
  workflow and release definitions. Operational records, credentials and
  raw trajectories stay within the private environment.
- **Reproduction:** Use the private project's authorized runbook for the actual
  pipeline. A future public exercise can use synthetic or approved examples
  with explicitly stated output semantics.
- **Environment status:** The existing operated workload is described in the
  dated public case. An isolated Aviation validation target and any cloud
  experiments are design milestones with separate acceptance.

See [project CI/CD](../../docs/design/project-delivery.md) for where a change
triggers validation or release and the [project index](../README.md) for
repository-wide planning.
