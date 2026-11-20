# Cloud verification — G02 Energy Analytics API

<!-- [李淳风·2026-11-20] Task 3.4 acceptance evidence (plan:
docs/superpowers/plans/2026-11-20-g02-energy-api.md, Phase 3). Recorded
live against project slh-gcp-test, region europe-west3. -->

## What was proven

The energy observations published by G01 are served over an authenticated
FastAPI service on Cloud Run: denied-by-default access (a dedicated caller
identity invokes; the runtime identity reads an authorized view and nothing
else), hard query guards (31-day span, 15 s statement timeout, 1 GiB byte
cap, fail closed), one release per response, half-open windows, and one
error shape (`code`/`message`/`request_id`) — every step driven by
committed code through the same WIF pipeline and the `gcp-test` gate as G01.

## Delivery trail

| Step | Evidence |
|---|---|
| Plan (approved by owner) | PR #183, merged |
| Phase 0+1 (scaffold, contract, guards, port+fake) + Phase 2 (adapter, IaC, workflow) | PR #183, 11 commits; CI test green, CI plan `Plan: 13 to add, 0 to change, 0 to destroy` |
| First apply — view creation failed | run 44822526115, apply 46s: BigQuery rejected the view — `Invalid project ID` with a leading backtick inside the ID, because the tables API defaults `useLegacySql` to true. PR #189 adds explicit `use_legacy_sql = false` |
| Fix apply — full stack up | run 44823928542, apply green 55s (remaining 5 resources; the other 8 were applied before the failure) |
| App logging fix (revision 2) | PR #192, merged; run 44825357616, apply green 50s |
| Gate approvals | deployments `7953195016`, `7953368674`, `7953541148` (environment `gcp-test`, required reviewer, approved per standing authorization) |

Service URL: `https://energy-api-5hymognmeq-ey.a.run.app`

## Bootstrap record (G02 deltas, one-time, outside Terraform)

`gcp/02-energy-analytics-api/infra/BOOTSTRAP.md`, executed 2026-11-20
**before** the first merge — G01's chicken-and-egg lessons applied
proactively this time:

- Registry `energy-api` created via `gcloud` and `terraform import`ed into
  the G02 state prefix (`gcp/02-energy-analytics-api`) before any CI run —
  the first plan already treated it as managed infrastructure, so the
  post-merge build-push incident from G01 could not repeat.
- Deployer SA granted `roles/monitoring.admin` and `roles/logging
  .configWriter` — G01's grant set predates the observability resources
  and would have 403'd the Task 2.4 apply.
- Acceptance-time only: `roles/iam.serviceAccountTokenCreator` for the
  project owner on `energy-api-caller` and `energy-api-runtime` (token
  minting for the checks below; G01 BOOTSTRAP §5 pattern).

## Identities and denial evidence (review focus #4, #5)

| Check | Identity | Result |
|---|---|---|
| `GET /health` with caller OIDC token (audience = service URL) | `energy-api-caller` (run.invoker on the service only) | **200** `{"status":"ok"}` |
| `GET /v1/summary?metric=actual_load_mwh&area=DE&from=2026-06-08T00:00:00Z&to=2026-06-15T00:00:00Z` | caller | **200** `{"count":664,"min":10552.15,"max":10552.15,"unit":"MWh"}` |
| `GET /v1/metrics` first hour | caller | **200** — RFC 3339 UTC timestamps, `unit:"MWh"`, `release_id` present, rows ordered |
| `GET /health` with a token from an SA **without** invoker | `energy-api-runtime` | **403** — Cloud Run's platform HTML error, not the app's JSON error shape (the platform gate fires before the app) |
| `SELECT COUNT(*) FROM slh-gcp-test.energy.metric_observation` via BigQuery REST | `energy-api-runtime` | **403 Access Denied** — the runtime holds dataViewer on the view only, never on G01's dataset |
| `SELECT COUNT(*), MIN(value), MAX(value) FROM slh-gcp-test.energy_api.metric_observation` | `energy-api-runtime` | **200** — the authorized view is the only sanctioned read surface |

Release resolution reads the **view** (`MAX(ingested_at)` per release),
never the G01 ledger — the adapter docstring and the fake both pin this.

## Half-open window on real data (review focus #1)

The latest G01 release (`0f249cdb…`) carries **672** rows; the API window
`[2026-06-08T00:00Z, 2026-06-15T00:00Z)` returns **664**. The 8-row
difference is real: those rows have `interval_start ≥ 2026-06-15T00:00Z`
and are cut by the `interval_start < @end` predicate — published volume
vs in-window volume, correctly distinguished by the frozen contract.

## Request-id correlation (plan Task 3.1)

Structured app logs appear from revision 2 (revision 1 swallowed
`logger.info` under Python's default WARNING root — fixed in PR #192):

```
INFO:energy_api:route=/v1/summary metric=actual_load_mwh release=0f249cdb2d1c44ab8155fb810b178302 status=200 request_id=0b60c13572b947618fc880f565943671
```

`request_id` is a uuid4 per request, echoed in the `X-Request-Id` response
header and in every error body; caller tokens are never logged.

## Revisions and rollback drill (Task 3.2)

| Revision | Image | Origin |
|---|---|---|
| `energy-api-00001-6g2` | `energy-analytics-api:01cda64a` | PR #189 apply |
| `energy-api-00002-59s` | `energy-analytics-api:4b00f7d4` | PR #192 apply |

- Smoke on revision 2: `/health` 200, `/v1/summary` 200 with values
  identical to revision 1.
- Drill: `gcloud run services update-traffic --to-revisions=energy-api-00001-6g2=100`
  → `status.traffic` shows `100 % → 00001`, request served 200 under the
  pin; restored with `--to-revisions=energy-api-00002-59s=100` → 200
  again. Rollback is a traffic split, not a redeploy.

## Bounded load check (Task 3.3, revision 2)

Warmup 3 requests (all 200). Fixed rate via an asyncio/httpx script,
2 concurrent workers, summary endpoint over the real window.

| Run | Rate | Sent | Completed | Errors | p50 | p95 | max |
|---|---|---|---|---|---|---|---|
| 1 — saturation probe | 10 rps × 60 s | 597 | 114 | **0** (all 200) | 1077 ms | 1225 ms | 1292 ms |
| 2 — steady state | 2 rps × 60 s | 120 | 114 | **0** (all 200) | 1071 ms | 1256 ms | 1331 ms |

Honest reading: at concurrency 2 and ~1.1 s per request (latency is
dominated by BigQuery job polling), the service sustains ≈ 1.9 rps. At
10 rps the client-side queue grows and pending coroutines are cancelled
at drain — the server answers every request it accepts with 200 and never
returns 5xx. Run 2's 6 uncompleted requests are the last in-flight calls
cut by the 3 s drain, not failures. For a sample-scale read API this is
the documented capacity boundary; raising it is a concurrency parameter,
not a redesign.

Bytes billed by the runtime identity's query jobs (30 min window,
682 jobs): **41,943,040 bytes ≈ 40 MiB** — 0.004 % of the monthly free
1 TiB and 0.004 % of the 1 GiB per-job guard. The guard values were
asserted on the job config by unit test and never approached in
production traffic.

## Observability (Task 2.4)

Applied in run 44823928542 (21:44 UTC): log-based metric
`energy_api_errors` (ERROR-severity entries of the service), email
notification channel to the project owner, alert policy `energy-api
error rate` (any error over a 5 min window → email). Free-tier SKUs
throughout.

## Cost

Same cost-gate discipline as G01 ([AGENTS.md](../../AGENTS.md)): the
G02 plan declared expected SKUs only (Cloud Run scale-to-zero, tiny
BigQuery data, registry storage, monitoring free tier); every plan run —
local and CI — confirmed **0 destroys** and no unexpected billable
resource (no NAT, no load balancer, no static IP). Measured usage:
40 MiB billed query bytes, request-based Cloud Run invocations only.
The one-time registry import, the two deployer grants and the two
acceptance TokenCreator bindings cost nothing and are reversible.

## Out of scope (design §2)

Event corrections (G03), release catalog and IAM product model (G04),
training and model serving (G05), the reusable project factory (G06);
public (unauthenticated) invocations are permanently out of scope for
v1 — IAM is the gate by design.
