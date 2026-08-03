# External Validator Outreach (Block G)

This note is for maintainers preparing the integrated post-v2.9 external gate.
It is **not** a substitute for the validator protocol.

**Protocol:** [`integrated-v2.9-external-validation.md`](integrated-v2.9-external-validation.md)

---

## Who to ask

Target **one person outside the SoloLakehouse maintainer team** who:

- has Docker, Git, and Python 3.13+ on a machine **not used for SoloLakehouse development**
- can spend **2–4 hours** on a cold clone (first run is often slower than CI)
- is comfortable recording friction honestly, including steps that eventually worked
- ideally works in **EU/DACH regulated data / platform engineering** (the project's primary audience)

Good profiles: data platform engineer, lakehouse architect, MLOps engineer with
governance interest, or an auditor-adjacent technologist who runs stacks rather
than reading slides.

## What to send

1. Link to the repository and the **exact git ref** to test — currently `main @ 0339672` or later. Send the SHA, not a branch name.
2. Link to the integrated protocol above — **not** the Block `J` appendix alone.
3. Explicit scope statement: this is the **v2.6.1–v2.9 integrated candidate**, not tag `v2.6.1` alone.
4. Reminder: **do not commit** `OPENMETADATA_AUTH_TOKEN` or other secrets; paste into `.env.secrets` only.
5. Heads-up that evidence manifests will read `runtime_version=slh-v2.6.1` by design — see the protocol's *Declared runtime version stamp* section — so they do not spend time on it as a suspected defect.
6. Ask them to fill the **Integrated external validator sign-off** table and friction log in the protocol file, then return it (issue, email, or shared doc — maintainer merges a redacted copy into the repo).

## Onboarding checklist (validator)

Send this list verbatim:

- [ ] Clone repo; checkout the signed ref maintainer provided
- [ ] Run `make init-env` (do **not** use `cp .env.example .env`)
- [ ] Run `make setup` then `make verify`
- [ ] Create OpenMetadata token; paste into `.env.secrets`; run `make init-env` again
- [ ] Run `make demo`
- [ ] Confirm five governed audit manifests + Object Lock (Block `J` section)
- [ ] Run Block `E` / `I` / `B`/`C`/`D`/`F` commands from the integrated protocol
- [ ] Record every friction point in the protocol friction log (even if resolved)
- [ ] Sign the integrated sign-off table with name, affiliation, date (UTC), OS/Docker versions

## Specific question to ask

After they complete the run, ask **one concrete question** (pick one per outreach round):

> "Which step would have blocked you from trusting this as an audit evidence plane
> for a regulated dataset — automatic lineage emission, promotion evidence,
> secrets discipline, or something else entirely?"

Alternatives if the validator is more infrastructure-focused:

> "Did `make init-env` + `make setup` on a cold clone fail in a way the README
> does not mention, and where would you expect that prerequisite to be documented?"

## What maintainers do with the response

1. Merge friction fixes into docs/scripts before the next outreach round if needed.
2. Link the signed integrated record from [`docs/v2.6-release-readiness.md`](../v2.6-release-readiness.md).
3. Only after external sign-off: operational rollout, post-v2.9 tag, and v3.0 planning.

## What this outreach is not

- Not a marketing launch or star-count campaign
- Not satisfied by maintainer rehearsal (see integrated record § Maintainer integrated rehearsal)
- Not a request to implement v3.0, entity split (D2), or portal/Keycloak (D3)
