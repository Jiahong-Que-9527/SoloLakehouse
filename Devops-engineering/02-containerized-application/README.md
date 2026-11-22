# D02 · Containerized application

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the image, compose stack and smoke procedure; record local evidence. -->

**Status:** accepted 2026-11-22 · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Implemented and verified locally, 2026-11-20 (agent run in WSL Ubuntu;
working tree uncommitted at record time):

- **Image:** `energy-quality-service:d02`, digest sha256
  `3f54ec192928e30306813b67aff21389ae690adce2d2f5dc1d56e9057ddd57c1`,
  built in 17 s from `python:3.13-slim`, uv `0.13.9`,
  `uv sync --locked --no-dev`, entrypoint uvicorn on `0.0.0.0:8000`.
- **Scenario:** direct container run with read-only input. **Command:**
  `docker run` with `fixtures/` mounted at `/reports:ro`.
  **Observed:** in-container identity `uid=10001(app)` (non-root);
  `/live`, `/ready`, `/v1/quality/latest` all 200 with the passed fixture
  body; `touch /reports/probe.json` fails with `Read-only file system`.
- **Scenario:** missing input. **Command:** container with
  `AUDIT_REPORT_PATH=/reports/absent.json`. **Observed:** `/ready` and the
  quality route 503 `report_unavailable`.
- **Scenario:** image hygiene. **Command:** `docker history`, `ls /app`
  inside the image. **Observed:** no fixtures, tests, credentials or real
  audit artifacts in image contents or layers.
- **Scenario:** compose smoke. **Command:**
  `compose/smoke.sh energy-quality-service:d02 report-passed.json`.
  **Observed:** startup-to-healthy 7 s; three routes 200; identity check
  OK (`eddf-load-20260608-audit-01`); stack torn down afterwards.
- **Scenario:** recreate with the failed fixture. **Observed:** quality
  route 200 with `coverage_result=failed`; container health `healthy` — a
  readable failed audit is data, not an outage.
- **Scenario:** recreate with the malformed fixture. **Observed:** `/ready`
  and quality 503 `report_invalid`; health flips `starting` → `unhealthy`
  at ~70 s, matching the documented startup budget (start_period 5 s plus
  12 retries x 5 s).
- **Fixture integrity:** all three fixture SHA-256 checksums identical
  before and after every recreate cycle.
- **Host daemon note:** this machine's Docker daemon runs on a non-default
  socket; container commands require
  `export DOCKER_HOST=unix:///run/recordchat-docker.sock`.

Owner acceptance, 2026-11-22 (run by the agent on the owner's behalf, WSL
Ubuntu; same fresh GitHub clone as D01 @ `8bb3484`, service tree clean):

- **Scenario:** clean-checkout image build (Acceptance 1). **Command:**
  `docker build -t energy-quality-service:d02 .` in
  `reference-service/` with the pinned client (28.5.2; the system
  `/usr/bin/docker` remains broken per the D07 note). **Observed:** build
  6 s, image id `sha256:98b0b7f29404…`, linux/amd64.
- **Scenario:** compose smoke from the clone (Acceptance 1). **Command:**
  `compose/smoke.sh energy-quality-service:d02` (passed fixture).
  **Observed:** startup-to-healthy 6 s; three routes 200; identity check
  OK (`eddf-load-20260608-audit-01`); stack torn down cleanly.
- **Scenario:** recreate with external input (Acceptance 2). **Command:**
  `compose/smoke.sh … report-failed.json`. **Observed:** healthy, quality
  200 with 95/96 `coverage_result=failed`, identity check OK — a readable
  failed audit is data, not an outage. Container identity is
  `uid=10001(app)`; writing to the report mount fails with
  `Read-only file system` (exit 1).
- **Scenario:** unavailable and invalid input (Acceptance 3). Direct
  `docker run` on ports 8733/8734. **Observed:** missing report → `/live`
  200, `/ready` and quality 503 `report_unavailable`; malformed report →
  503 `report_invalid` naming only the missing fields.
- **Scenario:** image hygiene (Acceptance 3). **Command:** `docker
  history`, `ls /app` inside the image, credential-pattern scan of layer
  instructions. **Observed:** `/app` contains only `.venv`, `pyproject.toml`,
  `src/`, `uv.lock`, `README.md` — no fixtures, tests, credentials or real
  audit artifacts. The only credential-pattern hit is the base image's
  `ENV GPG_KEY=…` (the official python:3.13-slim source-signing public
  key fingerprint), assessed as not a credential.
- **Run identity:** UTC `2026-11-22T16:09:14Z`, source commit `8bb3484`,
  docker client/server 28.5.2, compose v5.7.0.

Handed to D03: build invocation `docker build -t <image-ref> .` from
`reference-service/`, and an image-reference smoke procedure
`compose/smoke.sh <image-ref> [report-file]`.

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
