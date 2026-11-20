# D01 · Reproducible development

<!-- [房玄龄·2026-11-17] Make the DevOps project self-contained. -->

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the service, fixtures, parser and routes; record local evidence. -->

**Status:** implemented locally; owner acceptance pending · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Implemented and verified locally, 2026-11-20 (agent run in WSL Ubuntu;
working tree uncommitted at record time):

- **Scenario:** strict v1 contract parsing. **Command:** `uv run --locked pytest`.
  **Observed:** 21 passed — fixture oracle equality, unsupported schema
  version, invalid counts, inconsistent coverage, malformed JSON, and
  error bodies free of filesystem details.
- **Scenario:** three routes over real HTTP. **Command:** uvicorn on
  `127.0.0.1:8731` with each fixture as `AUDIT_REPORT_PATH`, probed with
  curl. **Observed:** `/live` 200; `/ready` 200; quality route 200 with the
  passed fixture body; failed fixture 200 with `coverage_result=failed`;
  missing report 503 `report_unavailable`; malformed fixture 503
  `report_invalid` naming the missing fields, with no filesystem paths.
- **Runtime versions:** Python 3.13.14, uv 0.13.9.
- **Fixture identity (SHA-256):** passed
  `b728777c2a8b7b7a1878986cee5bfe431fd66e45c02ecbea756270a99dbff6d0`,
  failed
  `20fe035236c2ad58fc4e0aba14f946c8fce960dc47b4f4768296d17dbbba8aa7`,
  malformed
  `751fc1b0f01f2c3f32aa440f7587b0f6bdd90beeb94c0cc5901e0f0557e8185e`.
- **Checks:** `uv run --locked ruff check .` and
  `uv run --locked ruff format --check .` clean.

Pending owner acceptance (fresh-checkout gate, Acceptance 1):

1. Fresh clone, then `cd Devops-engineering/reference-service`.
2. `time uv sync --locked`; record elapsed time and `uv run python -V`.
3. `uv run --locked pytest`, `uv run --locked ruff check .`,
   `uv run --locked ruff format --check .`.
4. Serve with the checked-in fixture and record the three route responses
   and the fixture checksum (commands in the reference service README).

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start in reference-service/ with Python and uv available in WSL. Use the fixture specification in the reference service README as the test oracle.

1. Write down the v1 input fields, their types and constraints, then prepare the two synthetic audit reports. Record the expected response for each before building the reader.
2. Pin the Python minor version and dependencies. Define a locked installation, a Ruff check and a pytest invocation from the service directory. Document the working directory for each.
3. Build the parser first. Cover missing fields, invalid counts, unsupported schema versions and unreadable inputs. Select the report through AUDIT_REPORT_PATH so the same application can run in each environment.
4. Expose the configured audit at GET /v1/quality/latest. Implement /live and /ready separately. A valid failed audit returns HTTP 200 with its failed result. Missing or invalid input returns 503 for readiness and the quality route while liveness stays 200.
5. Run unit tests, then start the service in a fresh checkout and exercise all three routes over HTTP. Record exact commands, fixture identity, setup time and observed responses. Give D02 the startup command and expected smoke responses.

## Interview evidence

Data contracts and test design. Show one failed audit and one unreadable report side by side. Explain what action a downstream data consumer takes for each.
