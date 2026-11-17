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

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start with the D01 lockfile, service entry point, fixture paths and expected HTTP responses. Use Docker with Compose in WSL.

1. Define the build context at the service directory. Package the locked runtime and entry point, select an unprivileged runtime user and exclude local environments, private inputs and build-only files.
2. Build the image and run one container directly. Mount the passing fixture read-only at the configured path, bind a local port and query all D01 routes. Check the actual user inside the container.
3. Encode the verified invocation under compose/. Add the readiness check and document the startup timeout. Run the same smoke check through the host port and compare the returned report ID.
4. Recreate the container with the failed-quality fixture and then malformed input. Record readiness and response behavior for both. Verify mount permissions and confirm the host fixture checksum after recreation.
5. Give D03 one documented build invocation and one smoke procedure that accepts an image reference. Record the image identity, startup time and fixture checksum.

## Interview evidence

Container and runtime engineering. Demonstrate that the same image can serve different external reports and show how readiness exposes an unusable input.
