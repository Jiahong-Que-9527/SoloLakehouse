# Layer 1 Source Selection Criteria

## Status

- **Block:** `L` — Layer 1 sources: research and remediate (`TASKS.md`)
- **Task:** `L1` — source-selection criteria for long-term operation
- **Date:** 2026-09-03
- **`L3` / D4:** decided 2026-09-03 — see `docs/roadmap.md` D4 and `TASKS.md` `L4`
- **Next step:** `L4` — implement the decision (EWG migration, optional crypto, hardening)

This document is the **evaluation rubric** for Block `L`. `L2` applied it to
candidates; **`L3` decided** remediation and replacement; `L4` implements.

**Authority chain:** `docs/roadmap.md` and `TASKS.md` win over this file.

**Agent rule (D4):** `data/sample/dax_daily_sample.csv` and any in-repo static
DAX/market CSV are **retired**. They are not a valid demo fallback, production
path, or planning option. Policy **P0** (demo frozen on sample DAX) and
outcome **D** (split demo vs operation with sample DAX) are **revoked** by the
Owner Decision.

---

## Purpose

SoloLakehouse has a complete v2.5 runtime and a v2.6–v2.9 evidence plane. Its
**input edge** is being remediated under Block `L` / D4:

- **ECB** — live SDW REST API (MRO today; DFR/MLF planned in `L4`)
- **Market leg** — **`L3` retired the DAX sample CSV**; target is live **EWG**
  via Alpha Vantage (CI fixture only — not the CSV)

Until `L4` lands, `DAXCollector` may still read `data/sample/dax_daily_sample.csv`
on `main`. That is **implementation lag**, not an approved option. Agents must not
treat the CSV as current policy or propose keeping it.

---

## Scope

### In scope

- Criteria for selecting or retaining finance-domain Layer 1 sources for the
  **shared upstream reference pipeline** (ECB + German-equity-proxy event-study
  path; legacy documentation may still say ECB + DAX until `L4` lands).
- Batch refresh models compatible with the existing Dagster schedule/sensor
  pattern (`daily_pipeline_schedule`, `ecb_data_freshness_sensor`).
- License, identity, and governance-contract requirements for Bronze ingestion.
- Policy options for whether `make demo` must keep working on the current path.

### Out of scope (until `L3` decides otherwise)

- New domains (for example aviation / ADS-B) — entity-clone work per
  [product-entity-contract.md](product-entity-contract.md).
- Streaming ingestion (Kafka, Flink, and similar) — contradicts the v2.5
  batch runtime and Block `L` explicit non-goals.
- New Compose services, catalog engines, or v3.0 runtime migration.
- Entity split (`task.md`, roadmap D2) — deferred indefinitely.

---

## Strategic constraints

These are fixed inputs; they are not re-litigated in `L2`.

| Constraint | Implication for Layer 1 |
|---|---|
| v2.5 runtime frozen until v3.0 | Sources must work through existing collectors + BronzeWriter + Iceberg path — no new platform services. |
| Batch orchestration only | Scheduled API pull or file ingest; no streaming prerequisite. |
| Five governed datasets | Any source change must map to existing or explicitly renamed `fin.*` contracts — see [dataset-governance-naming.md](dataset-governance-naming.md). |
| ADR-004 in force | ECB + German-equity-proxy event-study path; ADR-004 amended by D4 (`L4l`) |
| Primary audience (roadmap) | EU/DACH regulated-data decision-makers — sources should support credible finance/regulatory narrative, not generic tutorial data. |
| Entity template model | Upstream keeps a reproducible finance reference; production-grade feeds may live in entity clones, but criteria still apply when upstream sources are remediated. |

---

## Decision outcomes (`L3`)

**Decided 2026-09-03 (D4):** remediate ECB in place; **retire DAX sample CSV
entirely**; replace market leg with live EWG (Alpha Vantage); add optional
isolated crypto streaming leg. Full implementation: `TASKS.md` `L4`.

The table below records the **pre-decision** options evaluated in `L1`/`L2`.
**Outcomes that kept the sample CSV are revoked** and must not appear in new
plans or agent proposals.

| Outcome | Meaning | Status after D4 |
|---|---|---|
| **A — Remediate in place** | Keep ECB + market event-study; fix gaps with live feeds and licensing metadata. | **Partial** — ECB yes; market leg becomes EWG, not DAX CSV |
| **B — Replace one leg** | Keep event-study story but swap ECB or market for a better batch source. | **Superseded** by D4's explicit EWG choice |
| **C — Replace Layer 1** | New finance source pair; Gold and contracts may change. | Not chosen |
| **D — Split demo vs operation** | `make demo` stays on sample DAX; operation uses different sources. | **Revoked** — no static file on any path |

---

## Mandatory gates (pass / fail)

A candidate source (or a remediated current source) **must pass every gate** to
advance from `L2` to `L3` shortlist. Failure on any gate disqualifies unless
`L3` documents a conscious exception with compensating controls.

### G1 — Durable source identity

The source must have a **stable, externally recognizable identity** that
survives in governance metadata and audit evidence for years.

| Pass | Fail |
|---|---|
| Official provider name, dataset code, or series ID documented | “CSV from a forum post” with no canonical ID |
| `source_of_truth` in dataset contract can name a real authority | Vague text like “market-data source configured by the collector” |
| Version or publication date of the feed is traceable | Anonymous scraper with no stable endpoint contract |

**Current baseline**

- ECB: **pass** — ECB Statistical Data Warehouse, documented REST series key.
- DAX: **fail** — sample file in-repo; no authoritative live identity.

### G2 — License and redistribution clarity

Operators must be able to state **what they may ingest, store, retain, and
redistribute** in a private Compose deployment.

| Pass | Fail |
|---|---|
| License or terms of use are published and linkable | Ambiguous “public data” with no terms |
| Repo redistribution requirements are understood (bundled CSV vs API-only) | Prohibits storage or requires undisclosed commercial license |
| Demo / internal_analytics use fits stated terms | Terms require registration secrets that cannot be documented in `.env.example` |

Preference order: **open government / central-bank statistics** > **free API with
clear terms** > **licensed vendor with documented entitlement**. Undocumented
scraping is always fail.

**Current baseline**

- ECB: **pass** — public SDW API, no key required.
- DAX: **pass for demo** (synthetic sample, no third-party redistribution) —
  **fail for long-term operation** (not a licensed or authoritative market feed).

### G3 — Batch-compatible refresh

The source must support **scheduled batch ingestion** aligned with Dagster
without new infrastructure.

| Pass | Fail |
|---|---|
| REST/JSON or CSV/Parquet file pull on a schedule | Requires continuous stream consumer |
| Backfill over a date range is possible or unnecessary | Only “latest tick” websocket |
| Reasonable rate limits for daily or weekday schedule | Aggressive throttling that breaks `daily_pipeline_schedule` |
| Idempotency strategy can be defined (date partition, content hash, or upsert key) | Full re-download with no dedupe story |

Allowed patterns: **scheduled API**, **periodic file drop**, **versioned bulk
download**. Not allowed in Block `L`: **Kafka / Pulsar / Flink** as a
prerequisite.

**Current baseline**

- ECB: **pass** — REST with `startPeriod`; daily sensor already exists.
- DAX: **pass mechanically** (file read) — **fail operationally** (static file,
  no refresh).

### G4 — Operational value

The source must justify **long-term operation** of the Compose stack — not just
CI green once.

| Pass | Fail |
|---|---|
| Data still updates or remains meaningfully current on a business-day horizon | Frozen end date years in the past with no refresh path |
| Supports the existing or planned Gold use case (ECB–equity event study or documented replacement) | Orphan Bronze with no Silver/Gold consumer |
| Failure modes are observable (HTTP errors, empty file, schema drift) | Silent stale data with no freshness check |

**Current baseline**

- ECB: **partial pass** — live but sparse; MRO-only limits analytic depth.
- DAX: **fail** — static through 2024-12-31.

### G5 — Governance contract compatibility

Each Bronze table needs a **machine-validated** `governance/datasets/fin.*_bronze.yaml`
contract. Sources must be describable with the existing contract fields.

Required contract fields that Layer 1 must inform:

- `source_of_truth`
- `refresh_sla` (`business_day` or stricter)
- `quality_rules` (`date_column`, `max_gap_days`, `forbid_future_dates`, etc.)
- `dagster_asset_key` mapping

| Pass | Fail |
|---|---|
| Schema stable enough for Pydantic models and quality rules | Highly volatile wide tables with no stable core columns |
| Refresh SLA can be stated honestly | SLA would require streaming to meet |

---

## Scored criteria (`L2` ranking)

After mandatory gates, rank survivors using a **0–3** score per criterion.
**3 = strong fit**, **2 = acceptable**, **1 = weak**, **0 = unacceptable**.

| ID | Criterion | 3 (strong) | 0 (unacceptable) |
|---|---|---|---|
| S1 | **Incremental refresh** | Date- or version-based incremental fetch; content-hash dedupe possible | Full snapshot only, multi-GB daily |
| S2 | **Freshness fit** | Matches `business_day` SLA with sensor or schedule | Unknown lag or manual-only refresh |
| S3 | **Engineering realism** | Exercises real-world concerns (calendars, sparse events, gaps) | Trivially clean synthetic data |
| S4 | **EU/DACH domain fit** | Credible for Frankfurt / ECB / regulated-finance audience | Generic global tutorial dataset |
| S5 | **API / access reliability** | No key, stable endpoint, documented limits | Fragile scraper or opaque auth |
| S6 | **Schema stability** | Rare breaking changes; documented fields | Frequent unannounced schema breaks |
| S7 | **Volume fit** | Laptop / single-node Compose friendly | Needs cluster scale for Bronze alone |
| S8 | **Layer 2 change surface** | Drop-in for existing collector + schema | Requires new medallion tables and Gold rewrite |
| S9 | **Event-study continuity** | Preserves ECB–market joint Gold story | Forces unrelated Gold domain |

**Shortlist rule for `L2`:** candidates that fail any mandatory gate are
**out**. Among gate passers, advance sources with **average score ≥ 2.0** and no
**0** on S8 unless `L3` outcome C is already preferred.

---

## `make demo` continuity policy

**Decided policy: P1** — demo follows the same Layer 1 as long-term operation.
The sample CSV is **not** retained for demo, CI design, or as a labeled
fallback. CI uses a committed Alpha Vantage JSON fixture (`L4-dax-f`), not
`data/sample/dax_daily_sample.csv`.

Historical policies (for `L2` context only — **do not apply after D4**):

| Policy | When to use | Status after D4 |
|---|---|---|
| **P0 — Demo frozen on current path** | Was: `make demo` keeps ECB + sample DAX | **Revoked** — sample DAX forbidden on any path |
| **P1 — Demo follows production sources** | Single honest path; sample retired | **Active** — EWG live (fixture in CI) |
| **P2 — Demo deprecated** | Major domain change | Not chosen |

**Current state:** **P1** by Owner Decision D4. **Implementation:** Phase 1
(batch ECB + EWG full pipeline) is active; Phase 2 (streaming crypto) is
deferred until Phase 1 lands (`TASKS.md` "L4 execution phases").

---

## Baseline scorecard — current Layer 1 (for `L2` comparison)

Scores use the rubric above. Mandatory gates: **P** = pass, **F** = fail,
**~** = partial.

| Source | G1 | G2 | G3 | G4 | G5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ECB SDW (MRO) | P | P | P | ~ | P | 2 | 2 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | Sparse; single series |
| DAX sample CSV | F | ~ | ~ | F | P | 0 | 0 | 2 | 3 | 3 | 3 | 3 | 3 | 3 | **Retired by D4** — historical baseline only |
| **Pair (today)** | — | — | — | **F** | — | — | — | — | — | — | — | — | — | Blocked for long-term ops |

**Known gaps to address in `L2` / `L3` (from
[ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md)):**

- DAX is static and diverges from real index levels.
- ECB is MRO-only.
- Idempotency is date-based, not content-fingerprinted.
- Rejected Bronze records have no governance loop.

---

## `L2` survey deliverable template

For each candidate source, create a row in a survey table (markdown in
`docs/layer1-source-survey.md` — created in `L2`, not `L1`):

```markdown
### <provider> — <dataset name>

- **URL / access:** …
- **License / terms:** …
- **Refresh model:** API | file drop | bulk download
- **Mandatory gates:** G1–G5 (pass/fail + one-line evidence)
- **Scores:** S1–S9 (0–3)
- **Layer 2 impact:** collector / schema / contract changes
- **Gold impact:** none | feature tweak | replacement
- **Demo policy fit:** P0 | P1 | P2
- **Risks:** …
```

Candidate categories to survey in `L2` (non-exhaustive):

1. **Remediated ECB** — additional SDW series (deposit facility, refi rate, etc.)
2. **Remediated DAX** — licensed or open index history via file/API (Stooq,
   Deutsche Börse public stats, ECB SDW equity if applicable — verify license)
3. **Replacement macro leg** — still EU/sovereign rates if ECB kept
4. **Replacement market leg** — liquid EU equity index with batch history

Do not implement collectors in `L2`.

---

## Relationship to other documents

| Document | Relationship |
|---|---|
| [ADR-004](decisions/ADR-004-financial-dataset.md) | Original domain decision; amended by D4 (`L4l`) — DAX sample CSV retired |
| [architecture.md](architecture.md) | Layer 1–2 boundary and Dagster asset graph |
| [medallion-model.md](medallion-model.md) | Bronze/Silver/Gold expectations for any new source |
| [product-entity-contract.md](product-entity-contract.md) | Entity clones may use different sources; upstream criteria still apply to shared reference |
| [dataset-governance-naming.md](dataset-governance-naming.md) | Stable `fin.*` IDs when renaming physical tables |
| [TASKS.md](../TASKS.md) | Block `L` task list and sequencing |

---

## Acceptance — `L1` complete when

- [x] Mandatory gates G1–G5 are defined with pass/fail examples.
- [x] Scored criteria S1–S9 and shortlist rule are defined.
- [x] `make demo` continuity policies P0–P2 are defined for `L3`.
- [x] Baseline ECB/DAX scorecard is recorded for `L2` comparison.
- [x] `L2` survey template and candidate categories are listed.

**Next:** `L2` — research-only survey using this rubric; output in
[`layer1-source-survey.md`](layer1-source-survey.md) (**done 2026-09-03**).
