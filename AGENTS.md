# AGENTS.md — rules for every agent working in this repository

<!-- [李淳风·2026-11-20] Mandated by the project owner (节度使大人): a cost
gate for all GCP-related work. Binding for Claude Code, Codex, OpenCode,
Grok, Cursor and any other agent, human-supervised or autonomous. -->

Applies to every project in this repository that touches Google Cloud —
today `gcp/`, later anything G02–G06 creates — and to every agent that
reads this file.

## GCP cost gate (mandatory, non-overridable)

The GCP billing account `01FCE3-C90698-BFE584` is on a **Free Trial**
(€269 credit, expires 2027-02-11). The owner's standing order:

**Before running any operation that may cost money beyond what the trial
credits cover, the agent MUST present the expected cost and get the
owner's explicit approval for that specific action. No approval, no
execution.**

### Always ask before

- Creating or touching resources whose SKUs the credits do not cover
  (check the console link "What your credits cover" for the exclusion
  list)
- Services that provision billable infrastructure even at small scale:
  Cloud NAT, idle external static IPs, load balancers, VPN/Interconnect,
  GPU or TPU attachments, Cloud Composer, Vertex AI billable training or
  online prediction beyond its free tier
- Bulk work that could burn credits quickly: large backfills, repeated
  large BigQuery scans, cross-region or intercontinental data transfer,
  long-running or high-concurrency compute
- Any spend commitment: CUDs (resource- or spend-based), reservations,
  support plans
- Anything that moves the account out of Free Trial: billing upgrades,
  enabling auto-renewal, or raising quotas/limits into paid territory

### No approval needed

Read-only operations (list/describe/get, billing reports, logs) and
day-to-day operations that stay well inside free tier and credits — the
current G01 shape (Cloud Run job runs, batch BigQuery loads, small
registry storage, one scheduled job) is exactly that.

### How to ask

In one message, state: the resource and SKU, the expected cost at list
price (per run and per month), whether credits cover it, and the exact
command you intend to run. Proceed only on an explicit yes from the
owner. If the scope changes, ask again. Sub-agents, background tasks and
auto-approve modes must not bypass this gate; when in doubt, stop and
ask.
