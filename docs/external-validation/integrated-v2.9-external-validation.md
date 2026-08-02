# Integrated v2.6.1–v2.9 External Validation Protocol

Gate owner: release readiness (`docs/v2.6-release-readiness.md`)

Version under test: **integrated post-v2.9 candidate** on `main` (v2.6.1 Block `J`
through v2.9 Blocks `B`/`C`/`D`/`F`, plus v2.7 Block `I` and v2.8 Block `E`)

Record status: **active — v2.9 delivered; external sign-off pending**

Minimum baseline: commit [`e534c73`](https://github.com/Jiahong-Que-9527/SoloLakehouse/commit/e534c73)
(Block `J`) through the signed integrated candidate. Do **not** test tag `v2.6.1`
alone — that tag predates Block `J`.

Block `J` detail and historical friction: [`v2.6.1-external-validation.md`](v2.6.1-external-validation.md)

---

## Scope

This record is the **primary** external-validation protocol. A passing integrated
sign-off requires all sections below, not Block `J` alone.

| Section | Version / block | What it proves |
|---|---|---|
| Bootstrap | — | Cold clone, v2.9 env split, stack health |
| Runtime baseline | v2.5 | `make verify`, `make demo` |
| Block `J` | v2.6.1 | Automatic five-dataset lineage evidence + Object Lock |
| Block `E` | v2.8 | Agent-ready policy hook catalog |
| Block `I` | v2.7 | Catalog interoperability proof + sovereignty report |
| Blocks `B`/`C` | v2.9 | Promotion, rollback drill, operational SLO evidence |
| Blocks `D`/`F` | v2.9 | Secrets discipline, rotation drill record, K8s readiness gate |

Optional (not required for default-stack sign-off):

- `make interoperability-proof LIVE_REST=1` — only when a REST catalog (for
  example optional Polaris) is running; see `docs/polaris-evaluation.md`.

---

## Validator protocol

Run on a machine with Docker, Git, Python 3.13+, and **no prior SoloLakehouse
development checkout**.

### 1. Bootstrap

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
git checkout <signed-post-v2.9-candidate>   # e.g. main @ 0d4ea57 or later signed tag

make init-env
# Creates .env.shared, .env.secrets, and merged .env from the v2.9 split templates.

make setup
make verify
```

Do **not** use `cp .env.example .env` — that bypasses the v2.9 secrets split and
skips `make init-env`.

### 2. OpenMetadata token (required before demo / Block `J`)

After the stack is healthy:

1. Sign in to OpenMetadata at `http://localhost:8585` as
   `<OPENMETADATA_ADMIN_PRINCIPAL>@open-metadata.org` (default principal in
   `.env.shared.example`).
2. Create a Bot or Personal Access Token with table read access.
3. Paste the token into **`.env.secrets`** only:

   ```bash
   # edit .env.secrets — set OPENMETADATA_AUTH_TOKEN=...
   make init-env    # re-merge into .env for Compose and scripts
   ```

4. Confirm `OPENMETADATA_TRINO_SERVICE_NAME` in `.env.shared` (default
   `sololakehouse-trino`) matches the Trino service in OpenMetadata after first
   boot.

Never commit tokens or paste them into this record.

### 3. Runtime baseline (v2.5)

```bash
make demo
```

`make demo` runs `make verify` then the Dagster demo job. Record pass/fail and
any friction.

### 4. Block `J` — lineage evidence (v2.6.1)

Follow [Block `J` verification](v2.6.1-external-validation.md#block-j-verification)
in the appendix record. Confirm:

- automatic emission for all five governed datasets (no manual
  `make lineage-evidence` on the happy path)
- `make verify` reports Object Lock on `AUDIT_BUCKET`

### 5. Block `E` — AI/ML governance (v2.8)

With the stack still up (or after re-running `make verify` if you restarted):

```bash
make validate-contracts
make export-policy-hooks
```

Save the JSON locally for your sign-off packet. Exit code `0` and non-empty
canonical JSON are required.

### 6. Block `I` — catalog openness (v2.7)

Default-stack proof (no Polaris required):

```bash
make interoperability-proof
make sovereignty-report
make sovereignty-report FORMAT=json
```

Save markdown and JSON locally. Exit code `0` for each command.

### 7. Blocks `B`/`C` — promotion and operations (v2.9)

Requires a healthy runtime (`make verify` PASS):

```bash
make promotion-evidence
make rollback-drill
make operational-evidence
```

Each command must exit `0` and emit a SHA-256-bound JSON manifest on stdout.
If a gate fails, record the failing gate id — do not set `ALLOW_SLO_FAILURE=1`
(for `make operational-evidence`) or `ALLOW_UNHEALTHY=1` (for
`make rollback-drill`) unless you are documenting a known limitation. Note the
variable is `ALLOW_UNHEALTHY`, not `ALLOW_UNHEALTHY_RUNTIME`; `make` silently
ignores unknown variables, so a typo looks like a genuine failure.

### 8. Blocks `D`/`F` — secrets and K8s readiness (v2.9)

Repository checks (stack may be up or down):

```bash
make secrets-discipline
make secrets-rotation-drill ROTATED_KEYS=POSTGRES_PASSWORD,S3_SECRET_KEY ROTATION_NOTES="external validation drill"
make k8s-readiness
```

`make secrets-discipline` must exit `0` without `--allow-warn`.

---

## Integrated external validator sign-off

| Field | Value |
|---|---|
| Validator name | _pending_ |
| Affiliation (outside SoloLakehouse maintainers) | _pending_ |
| Date (UTC) | _pending_ |
| Host OS / Docker version | _pending_ |
| Git commit or tag tested | _pending_ |
| `make init-env` + `make setup` | _pending_ |
| `make verify` (incl. Object Lock) | _pending_ |
| `make demo` | _pending_ |
| Block `J` — five governed audit manifests | _pending_ |
| Block `E` — `make export-policy-hooks` | _pending_ |
| Block `I` — interoperability + sovereignty | _pending_ |
| Block `B`/`C` — promotion / rollback / operational | _pending_ |
| Block `D`/`F` — secrets / rotation drill / K8s readiness | _pending_ |

**Overall integrated gate:** _pending_

Link the completed record from [`docs/v2.6-release-readiness.md`](../v2.6-release-readiness.md).

---

## Friction log

| ID | Step | Severity | What happened | Workaround / fix | Resolved in repo? |
|---|---|---|---|---|---|
| E1 | `.env.secrets` | info | `OPENMETADATA_AUTH_TOKEN` is empty in templates by design; Block `J` emission fails until a local token is set | Create OM token after first boot; paste into `.env.secrets`; run `make init-env` | documented in this record |
| E2 | `make setup` / upgrade | high | Audit bucket created before v2.6.1 Block `J2` lacks Object Lock; `minio-init` fails on upgrade | `make clean && make up` recreates bind-mounted state | documented in `docs/governance-evidence-layout.md` |
| E3 | OpenMetadata | medium | First-time Trino table ingestion into OpenMetadata is an operator prerequisite for evidence adapters | Run bundled OM ingestion or register tables manually before `make demo` | documented in `docs/v2.6-release-readiness.md` |
| E4 | `make setup` | medium | Cold clone takes several minutes; `make wait` timeout is 5 minutes which can be tight on slow hosts | Retry `make verify`; increase wait locally if needed | _open — monitor external runs_ |
| E5 | Evidence | info | Automatic emission requires `dagster-daemon` healthy and OM token present; sensor tick may lag ~30s after run success | Wait for daemon log `lineage_evidence_emitted` | fixed: sensor defaults RUNNING |
| E6 | Bootstrap | high | Prior protocol used `cp .env.example .env`, which skipped the v2.9 split and contradicted Block `D` | Use `make init-env` instead | fixed in this record (2026-08-02) |

Add rows during your run. Do not delete maintainer-identified rows — append new
IDs or mark validator-specific follow-ups.

---

## Maintainer integrated rehearsal (template)

Maintainer rehearsals help fix docs before outreach. They **do not** satisfy the
external-validation gate.

| Field | Value |
|---|---|
| Environment | maintainer rehearsal (not external) |
| Git commit tested | _pending_ (target: signed post-v2.9 candidate on `main`) |
| Bootstrap | _pending_ (`make init-env`, not `cp .env.example .env`) |
| `make verify` | _pending_ |
| `make demo` | _pending_ |
| Block `J` five datasets | _pending_ |
| Block `E` / `I` / `B`/`C`/`D`/`F` commands | _pending_ |
| Friction found | _pending_ |

Historical Block `J`-only rehearsal (2026-08-01): see
[`v2.6.1-external-validation.md`](v2.6.1-external-validation.md#maintainer-block-j-rehearsal-2026-08-01).
