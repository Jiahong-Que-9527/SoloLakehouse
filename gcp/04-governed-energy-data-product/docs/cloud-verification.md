# Cloud verification — G04 first governed release

<!-- [Claude · 2026-11-21] Recorded from the live delivery and drill runs. -->

## What was proven

One governed release is live end to end in `slh-gcp-test`: the publisher
consumed the pinned G01 input release `0f249cdb2d1c44ab8155fb810b178302`
(the Berlin-local week 2026-06-08..2026-06-15, 672 quarter-hour
intervals), the contract gate passed all five checks, and the authorised
view `energy_product.energy_load_current` serves the immutable version
table under release id `cand-2026-11-21-fourth` — 672 rows, first
interval 2026-06-07 22:00 UTC, last interval end 2026-06-14 22:00 UTC.

The acceptance behaviours were exercised live, not only in tests:

- **Blocked publication keeps the preceding release queryable.** Three
  candidates were blocked by the gate (`first`, `second` with window
  defects; `invalid` with an injected null measure); the view kept
  serving the passed release throughout.
- **Reader/auditor role boundary.** The matrix below was executed with
  impersonated identities.
- **Reversible publishing.** `third` was withdrawn; with no previous
  passed release the view fell back to the zero-row authorised
  placeholder; the corrected data was republished under the fresh id
  `fourth` and the view serves it again.
- **Audit trail.** The append-only ledger holds every attempt with its
  gate manifest: `blocked → blocked → passed+withdrawn → blocked →
  passed` for `first`, `second`, `third`, `invalid`, `fourth`.

## Delivery trail

Infrastructure applied by the project workflow (test → build-push →
apply, the apply gated on the `gcp-test` environment with the owner as
required reviewer; seven owner approvals recorded on 2026-11-21). The
first publications surfaced five defects, each fixed by a reviewed PR:

| # | Symptom (job execution) | Root cause | Fix |
|---|---|---|---|
| 1–3 | ImportError / AttributeError crashes (16:12, 16:26, 16:44) | publish-job imports, adapter port, a merge dropped the import fix | PRs #214, #215, #216 |
| 4 | Gate blocked healthy data: "672/7 expected keys" (17:09) | DATE-typed window + date arithmetic collapsed 672 quarter-hour keys onto 7 day keys | PR #220 |
| 5 | Still blocked: "missing 8, unexpected 8" (17:26) | G01 window DATEs are Europe/Berlin local midnights, not UTC | PR #223 |
| 6 | Gate passed; crash at the view switch (18:07) | `google.cloud.bigquery.NotFound` does not exist; the exception lives in `google.api_core.exceptions` | PR #229 |
| 7 | 403 `bigquery.datasets.update` at the switch (19:58, 20:34) | the current view sits in the dataset access entries, so rewriting its definition (DDL or tables API) demands dataset-level permission; the producer held only dataEditor | PR #231 (tables API) + PR #233 (dataOwner on the product dataset only) |
| 8 | Withdrawal failed: 400 streaming buffer (drill) | DML cannot touch streaming-buffered rows; the ledger is now append-only with superseding rows read latest-wins | PR #235 |

The version tables are content-addressed by the rows checksum in their
description: `third`'s table (`f2013386…`) survived two failed
publications and was adopted idempotently on retry; the withdrawal drill
reused that mechanism.

## Identities and denial evidence

Grants are exactly the Terraform mapping: producer = dataViewer on
G01's `energy` + dataOwner on `energy_product` + jobUser; analyst =
dataViewer on the view only + jobUser; auditor = dataViewer on the
`release` table only + jobUser. Acceptance-time only: the project owner
holds `roles/iam.serviceAccountTokenCreator` on the three drill SAs
(G01 BOOTSTRAP §5 pattern) for token minting.

| Check | Identity | Result |
|---|---|---|
| `SELECT COUNT(*) FROM energy_product.energy_load_current` | `energy-product-analyst` | **672 rows** — the only sanctioned read surface |
| `SELECT COUNT(*) FROM energy_product.energy_load_v<release>` | analyst | **403 Access Denied** — version tables are not reader-visible |
| `SELECT COUNT(*) FROM energy_product.quarantine` | analyst | **403 Access Denied** |
| `SELECT COUNT(*) FROM energy.metric_observation` | analyst | **403 Access Denied** — the G01 source is closed to readers |
| `SELECT release_id, status FROM energy_product.release` | `energy-product-auditor` | **5 release ids, 6 rows** (third appears twice: passed, then withdrawn) — the auditor sees the whole attempt history |
| `SELECT COUNT(*) FROM energy_product.quarantine` | auditor | **403 Access Denied** |
| `SELECT COUNT(*) FROM energy_product.energy_load_current` | auditor | **403 Access Denied** |
| publisher job reads G01 input + writes the product dataset | `energy-product-producer` | execution `dth84` completed end to end — the job itself is the producer's allow proof |

## Release/withdrawal drill (run as the producer identity)

| Step | Action | Observed |
|---|---|---|
| A | publish a candidate with one null measure (`cand-2026-11-21-invalid`) | gate **blocked** it; `value_range` quarantined; the view still served `third` at 672 rows; a checksum-identical retry is refused with `PublishConflict` (fresh ID demanded) |
| B | withdraw the current release (`third`) | ledger **appended** a `withdrawn` row at 20:57:05 UTC; no previous passed release existed, so the view fell back to the zero-row authorised placeholder (0 rows, schema preserved) |
| C | republish the corrected data under a fresh id (`fourth`) | gate passed; view switched; 672 rows live again |

Final ledger (append-only, latest row per id wins):

| release_id | status | published_at (UTC) |
|---|---|---|
| `cand-2026-11-21-first` | blocked | 17:09:37 |
| `cand-2026-11-21-second` | blocked | 17:26:01 |
| `cand-2026-11-21-third` | passed → withdrawn | 20:39:59 / 20:57:05 |
| `cand-2026-11-21-invalid` | blocked | 20:45:18 |
| `cand-2026-11-21-fourth` | **passed (current)** | 20:57:08 |

## Traceability

A published row traces through: the view definition (the release id) →
the ledger row's manifest (`input_release_id`, `checksum`,
`contract_version`, per-check gate results, `published_at`) → the G01
input release `0f249cdb2d1c44ab8155fb810b178302` (its own G01 ledger
row and rows carry `ingested_at` and source attribution). The code
revision of the running publisher is the image tag applied by the
workflow run (`:61ecd5d`, run 44948522915); `git_sha` in the manifest
is null because the job environment does not set `GIT_SHA` — recorded
as a known gap below.

## Cost

All spend remained inside the Free Trial shape: one on-demand Cloud Run
job (1 vCPU / 512 MiB, seconds per run, eight executions total), batch
BigQuery queries and loads on 672-row data, ~50 MB Artifact Registry
storage, no new APIs, no networking primitives. No SKU outside the
trial credits was touched; every apply was owner-approved.

## Out of scope / known gaps

- **Catalog and lineage evidence**: the test project has no Data Catalog
  entry or native lineage graph wired for `energy_product`; manifest
  lineage (release → input release → checksum → code revision) is the
  recorded substitute, per the design's "identify any unavailable cloud
  evidence".
- `git_sha` is not recorded in manifests yet (the workflow does not set
  `GIT_SHA`); the applied image tag is the de-facto revision pointer.
- The version tables and IAM live in the single-purpose test project;
  deletion protection is the 0-destroys plan rule, not the flag.
