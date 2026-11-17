# D01 · Reproducible development

<!-- [房玄龄·2026-11-17] Make the DevOps project self-contained. -->

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Start with the [reference service](../reference-service/README.md) and verify that another developer can reproduce its behavior from a fresh checkout.

## Deliverables

- A minimal FastAPI app, a pinned supported Python version and a committed dependency lockfile managed with uv.
- One versioned audit-summary route, an internally defined audit report contract, and synthetic passed and failed fixtures. Document the expected counts, startup and test commands.
- Ruff and pytest configuration. Add an optional convenience wrapper only if the documented uv commands start to repeat.

## Acceptance

1. In a fresh WSL checkout, perform the locked install and record elapsed time and Python version. Run formatting, lint and tests with only this project's files and declared dependencies.
2. Exercise a valid passed audit, a valid failed audit, a missing report and malformed report data. Check response status and ensure error bodies omit filesystem paths.
3. Start the service with the checked-in synthetic report. Verify the HTTP response against the fixture's independently specified coverage counts, audit timestamp and report identity. Save the command and observed result.

D02 consumes the service startup command, runtime configuration and tested contract.

## Evidence

Pending implementation and acceptance runs.
