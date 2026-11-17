# D02 · Containerized application

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Package the D01 service and reproduce its behavior in Docker Compose.

## Deliverables

- A service Dockerfile with a locked dependency build and non-root runtime, plus a Compose definition in this phase.
- External runtime configuration, a read-only report mount and a health check. Bind the development service to a local endpoint and document the fixture startup and shutdown commands.
- A smoke check against the running service that confirms both health and the expected audit identity.

## Acceptance

1. Build and start the stack from a clean checkout using the documented Compose command. Verify container health, runtime identity and the audit response.
2. Recreate the service and verify the external audit input yields the same response. Show that the service cannot write to the report mount.
3. Use a missing or invalid report to verify the readiness and API behavior. Check image contents and history for credentials or real audit artifacts.

D03 consumes the Docker build definition and the Compose smoke check.

## Evidence

Pending implementation and acceptance runs.
