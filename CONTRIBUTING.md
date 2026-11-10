# Contributing

Read [AGENTS](AGENTS.md), [roadmap](docs/roadmap.md) and [TASKS](TASKS.md). Use the [construction plan](docs/design/v3/README.md) for design work and [CLAUDE](CLAUDE.md) for retained code patterns.

## Bounded changes

Preserve existing Python/Compose paths and logical dataset identities until an explicit compatibility change. Keep infrastructure, bootstrap, packaging, GitOps and business lifecycle ownership separate inside this repository. Do not import private aviation code or alter operated fin/avi state as part of repository preparation.

For scope/state changes update roadmap and TASKS; maintain timeline, architecture evolution and the current planning cross-link. New public prose is English and signed with author/date. Preserve historical originals and pending work when shortening documents.

## Verification

Use make docs-check and make check-agent-docs for active docs/scaffold. For code/command behavior add the applicable lint, type, contract and unit checks. Actual templates later require their corresponding static validation; hardware, deployment and restore claims require actual runtime evidence. Record unavailable checks rather than treating them as passed.

Do not run clean/reset/purge during verification. Generic destructive targets are disabled; state disposal requires exact scope and approval. Tests of the disabled targets run with no external-command PATH and do not start containers.

## Reviewable delivery

Keep the PR about one coherent output with source/destination boundaries, tests/results and material limits. CI builds/tests; future Flux reconciles reviewed desired deployment state. No direct deployment, public secret, IaC state, private key, actual inventory or unreviewed data deletion belongs in a design PR.
