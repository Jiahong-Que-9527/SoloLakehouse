# D01 · Reproducible development

<!-- [房玄龄·2026-11-17] Make the DevOps project self-contained. -->

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the service, fixtures, parser and routes; record local evidence. -->

**Status:** accepted 2026-11-22 · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Owner acceptance, 2026-11-22 (run by the agent on the owner's behalf, WSL
Ubuntu; fresh GitHub clone):

- **Scenario:** fresh-checkout gate (Acceptance 1). **Command:** clone of
  `Jiahong-Que-9527/SoloLakehouse` @ `8bb3484` (== `origin/main` at run
  time), then, in `Devops-engineering/reference-service`: `uv sync
  --locked`, `uv run --locked python -V`, `uv run --locked pytest`,
  `uv run --locked ruff check .`, `uv run --locked ruff format --check .`.
  **Observed:** service tree clean in the clone (0 modified files);
  locked install 0.33 s (25 packages, CPython 3.13.14 selected by uv);
  Python 3.13.14 with uv 0.13.9; pytest 23 passed (0.24 s warm, 1.2 s
  including first collection — v0.2.0 added the metrics tests, up from 21
  at the 2026-11-20 record); ruff check clean and 7 files already
  formatted (0.03 s each). Baseline timing recorded: sync 0.33 s, tests
  0.2–1.2 s, lint under 0.05 s. Note: the clone sits on a different
  filesystem from the uv cache, so the sync paid a full-copy fallback and
  still finished in 0.33 s.
- **Scenario:** fixture behaviors over real HTTP (Acceptance 2). Four
  uvicorn runs on `127.0.0.1:8731`, one per fixture. **Observed:**
  passed → `/live` 200, `/ready` 200, quality 200 with identity
  `eddf-load-20260608-audit-01` (96/96, `coverage_result=passed`);
  failed → quality 200 with 95/96 `coverage_result=failed`; malformed →
  `/live` 200 with `/ready` and quality 503 `report_invalid` naming only
  the missing fields; missing → `/live` 200 with 503 `report_unavailable`.
  No error body contains a filesystem path or report content.
- **Scenario:** fixture identity (Acceptance 3). **Command:**
  `sha256sum fixtures/*.json` in the fresh clone. **Observed:** all three
  checksums identical to the 2026-11-20 record (passed `b728777c…`,
  failed `20fe0352…`, malformed `751fc1b0…`).
- **Run identity:** UTC `2026-11-22T16:07:46Z`, source commit `8bb3484`,
  Python 3.13.14, uv 0.13.9.

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
