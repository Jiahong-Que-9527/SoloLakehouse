# Layer 1 Source Survey (Block `L` / `L2`)

> **Superseded recommendations (D4, 2026-09-03):** This survey predates the
> Owner Decision. Any option that **keeps**, **retains**, or **falls back to**
> `data/sample/dax_daily_sample.csv` or policy **P0** is **revoked** — not an
> option for agents, demo, production, or CI design. Authoritative policy:
> `docs/roadmap.md` D4, `TASKS.md` `L4`, `AGENTS.md` hard rule §4.7.

## Status

- **Block:** `L` — Layer 1 sources: research and remediate
- **Task:** `L2` — research-only survey against
  [layer1-source-selection-criteria.md](layer1-source-selection-criteria.md)
- **Date:** 2026-09-03
- **Next step:** `L4` — implement D4 (`TASKS.md`); do not re-open sample CSV options

**Research only.** No collector implementation, no Compose service changes, no ADR
updates in this task.

---

## Executive summary

| Leg | Current state | Survey conclusion |
|---|---|---|
| **Macro / policy (ECB)** | Live MRO only | **Strong remediate-in-place candidate.** ECB SDW already passes all gates; extend to DFR (+ optional MLF/MRO bundle) on the same API pattern. |
| **Market / equity (DAX)** | Static sample CSV | **Superseded by D4** — sample CSV retired; target is live EWG (Alpha Vantage) |

**Preliminary options for `L3` (historical — D4 supersedes):**

| Option | Macro leg | Market leg | Demo policy | Layer 2 / Gold impact | D4 status |
|---|---|---|---|---|---|
| **1 — Minimal remediate** | ECB MRO + DFR + MLF | Keep sample CSV | P0 | Low | **Rejected** — CSV forbidden |
| **2 — Honest single path** | ECB multi-rate | Licensed STOXX/DAX via entity `.env` secret | P1 | Medium | Partial — entity path only |
| **3 — Open-data pivot** | ECB multi-rate | ECB FM benchmark instead of DAX OHLCV | P1 or P2 | High | Not chosen |
| **4 — Status quo** | ECB MRO only | Sample CSV | P0 (implicit) | None | **Rejected** |
| **D4 (decided)** | ECB + DFR/MLF | **Live EWG (Alpha Vantage)** | **P1** | Medium | **Active plan** — `L4` |

**D4 decision (2026-09-03):** adopt ECB remediation + **live EWG**; **delete the
sample CSV from every path**; optional crypto streaming leg. Do not cite Option 1,
Option 4, or P0 as valid alternatives.

---

## Survey method

1. Applied mandatory gates **G1–G5** and scores **S1–S9** from the L1 rubric.
2. Restricted to **batch** access (REST CSV/JSON or file download).
3. Prioritized **EU/DACH finance** domain fit per ADR-004 and roadmap audience.
4. Did not evaluate streaming, ADS-B, or non-finance domains (Block `L` non-goals).

---

## Macro leg candidates (ECB SDW)

### ECB SDW — Main Refinancing Operations rate (current)

- **URL / access:** `https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.MRR_RT.LEV` (same pattern as `ECBCollector.ENDPOINT`)
- **License / terms:** ECB Statistical Data Warehouse — public, no API key; [ECB Data Portal terms](https://data.ecb.europa.eu/help/api/data)
- **Refresh model:** REST / JSON (`format=jsondata`); sparse change events; daily business-day series
- **Mandatory gates:** G1 P · G2 P · G3 P · G4 ~ · G5 P
- **Scores:** S1=2 S2=2 S3=3 S4=3 S5=3 S6=3 S7=3 S8=3 S9=3 · **avg 2.9**
- **Layer 2 impact:** None (implemented)
- **Gold impact:** None — but sparse post-2022; not the primary policy signal today
- **Demo policy fit:** P1
- **Risks:** MRO alone under-represents post-2022 policy regime ([ASSESSMENT](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) P7)

### ECB SDW — Deposit Facility Rate (DFR)

- **URL / access:** `https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV` (series `FM.D.U2.EUR.4F.KR.DFR.LEV`)
- **License / terms:** Same as ECB SDW public API
- **Refresh model:** REST / JSON; change-on-decision + daily level series; same collector pattern as MRO
- **Mandatory gates:** G1 P · G2 P · G3 P · G4 P · G5 P
- **Scores:** S1=2 S2=2 S3=3 S4=3 S5=3 S6=3 S7=3 S8=3 S9=3 · **avg 2.9**
- **Layer 2 impact:** Low — add series parameter or second Bronze table; extend Pydantic/contract
- **Gold impact:** Low — use DFR as primary event anchor (recommended in assessment P7)
- **Demo policy fit:** P1
- **Risks:** Still sparse events; need multi-series strategy for richer Gold

### ECB SDW — Multi-rate bundle (MRO + DFR + MLF)

- **URL / access:** MRO `…MRR_RT.LEV` or `…MRR_FR.LEV`; DFR `…DFR.LEV`; MLF `…MLFR.LEV` (ECB FM dataset)
- **License / terms:** ECB SDW public API
- **Refresh model:** Three parallel REST pulls or one parameterized collector
- **Mandatory gates:** G1 P · G2 P · G3 P · G4 P · G5 P
- **Scores:** S1=2 S2=2 S3=3 S4=3 S5=3 S6=3 S7=2 S8=3 S9=3 · **avg 2.8**
- **Layer 2 impact:** Medium — schema/contract may add `rate_type` dimension or separate Bronze tables
- **Gold impact:** Medium — parameterize event source; more post-2022 events
- **Demo policy fit:** P1
- **Risks:** Slightly wider Layer 2 surface; still macro-only

**Macro shortlist:** **DFR** or **multi-rate bundle** — both advance to `L3`.
Retaining MRO-only is a regression for long-term operation.

---

## Market leg candidates (DAX / equity index)

### DAX — bundled sample CSV (retired — historical record only)

- **Status:** **Retired by D4 (2026-09-03).** Not an option for demo, production,
  CI design, or agent proposals. Remove from the production path in `L4-dax-g`.
- **URL / access:** `data/sample/dax_daily_sample.csv` (in-repo) — **do not revive**
- **License / terms:** Synthetic/sample — no third-party redistribution; demo-safe
- **Refresh model:** Static file read; no external refresh
- **Mandatory gates:** G1 **F** · G2 ~ · G3 ~ · G4 **F** · G5 P
- **Scores:** S1=0 S2=0 S3=2 S4=3 S5=3 S6=3 S7=3 S8=3 S9=3 · **disqualified**
- **Layer 2 impact:** None
- **Gold impact:** None
- **Demo policy fit:** ~~P0 only~~ **Revoked**
- **Risks:** Frozen at 2024-12-31; not authoritative; fails long-term operation bar

### STOXX / DAX — licensed index data (official)

- **URL / access:** [STOXX Index Data Distribution](https://stoxx.com/); registration + license via `customersupport@stoxx.com`
- **License / terms:** [DAX Conditions of Use](https://stoxx.com/legal/dax-conditions-of-use/) — view-only without license; **no download/redistribution** without License Agreement; commercial use restricted
- **Refresh model:** Licensed SFTP/portal file drops (batch)
- **Mandatory gates:** G1 P · G2 P (with entity license) · G3 P · G4 P · G5 P
- **Scores:** S1=3 S2=3 S3=3 S4=3 S5=2 S6=3 S7=2 S8=3 S9=3 · **avg 2.9** (when licensed)
- **Layer 2 impact:** Medium — file-drop or API collector; secrets in entity `.env`
- **Gold impact:** Low — preserves DAX OHLCV event-study path
- **Demo policy fit:** P1 for licensed entity; **not suitable as upstream open-repo default**
- **Risks:** Cost, entitlement process, secrets discipline; cannot ship data in git

### Stooq — DAX / `^dax` historical CSV API

- **URL / access:** `https://stooq.com/q/d/l/` (API key required since ~2026); bulk `https://stooq.com/db/h/`
- **License / terms:** Personal/free tier; redistribution and commercial use **not clearly granted**; daily quota limits
- **Refresh model:** REST CSV by date range (batch)
- **Mandatory gates:** G1 ~ · G2 **F** (upstream repo) · G3 P · G4 P · G5 P
- **Scores:** S1=3 S2=2 S3=2 S4=2 S5=1 S6=3 S7=2 S8=3 S9=3 · **disqualified for upstream**
- **Layer 2 impact:** Low–medium — similar to ECB REST pull
- **Gold impact:** Low
- **Demo policy fit:** P0/P1 in private entity clone only
- **Risks:** ToS/redistribution; API key + quota; not an auditable `source_of_truth`

### Yahoo Finance / yfinance — `^GDAXI`

- **URL / access:** Unofficial Yahoo endpoints via `yfinance` library
- **License / terms:** Yahoo ToS — **personal use**; prohibits commercial use and unauthorized automated collection
- **Refresh model:** Batch pull via unofficial API
- **Mandatory gates:** G1 ~ · G2 **F** · G3 P · G4 ~ · G5 P
- **Scores:** **disqualified**
- **Layer 2 impact:** Low
- **Gold impact:** Low
- **Demo policy fit:** None for governed long-term operation
- **Risks:** Legal/ToS; endpoint breakage; fails G2 for reference platform

### Deutsche Bundesbank — SDMX time series

- **URL / access:** `https://www.bundesbank.de/statistic-rmi/StatisticDownload` and SDMX `/data/{flowRef}/{key}` ([docs](https://www.bundesbank.de/en/statistics/time-series-databases/help-on-the-time-series-databases/download-options))
- **License / terms:** Bundesbank statistical publications — generally open for reuse with attribution; verify per series
- **Refresh model:** Batch CSV/SDMX-CSV by `tsId`
- **Mandatory gates:** G1 P · G2 P · G3 P · G4 **F** (for daily OHLCV) · G5 ~
- **Scores:** S1=2 S2=1 S3=2 S4=3 S5=3 S6=3 S7=2 S8=1 S9=1 · **disqualified for DAX replacement**
- **Layer 2 impact:** High — different schema (often index **level** monthly in capital-market tables, not daily OHLCV)
- **Gold impact:** High — breaks equity OHLCV event-study assumptions
- **Demo policy fit:** P2
- **Risks:** Capital market indicator tables are **monthly** aggregates, not daily DAX OHLCV

### ECB FM — EURO STOXX 50 / government bond yields (open pivot)

- **URL / access:** ECB FM dataset, e.g. EURO STOXX 50 `FM.M.U2.EUR.4F.ST.EURSTOXX50.HSTA` (monthly); 10Y benchmark yield `FM.M.U2.EUR.4F.BB.U2_10Y.YLD`
- **License / terms:** ECB SDW public API
- **Refresh model:** REST / JSON batch
- **Mandatory gates:** G1 P · G2 P · G3 P · G4 ~ · G5 P
- **Scores:** S1=2 S2=1–2 S3=2 S4=3 S5=3 S6=3 S7=1 S8=1 S9=1 · **passes gates but poor S8/S9**
- **Layer 2 impact:** High — new market leg schema; monthly frequency limits event study
- **Gold impact:** High — domain shift from DAX daily returns to rates/index level
- **Demo policy fit:** P2 (new story)
- **Risks:** Loses ADR-004 DAX narrative unless Owner accepts pivot

**Market shortlist for long-term daily equity path:** **STOXX licensed feed**
(entity scope). **No upstream-open daily DAX OHLCV** candidate passes G2.

**Market shortlist after D4:** **live EWG via Alpha Vantage** (upstream default);
**STOXX licensed feed** for entity clones needing literal DAX. **Sample CSV is
not on the shortlist.**

---

## Comparative scorecard

Mandatory gate summary (P=pass, F=fail, ~=partial):

| Candidate | G1 | G2 | G3 | G4 | G5 | Shortlist |
|---|---|---|---|---|---|---|
| ECB MRO (current) | P | P | P | ~ | P | Yes (weak) |
| ECB DFR | P | P | P | P | P | **Yes** |
| ECB MRO+DFR+MLF | P | P | P | P | P | **Yes** |
| DAX sample CSV | F | ~ | ~ | F | P | **Retired** — not shortlist |
| STOXX DAX (licensed) | P | P* | P | P | P | **Yes (entity)** |
| Stooq DAX | ~ | F | P | P | P | No |
| yfinance ^GDAXI | ~ | F | P | ~ | P | No |
| Bundesbank SDMX | P | P | P | F | ~ | No |
| ECB FM STOXX50 / 10Y | P | P | P | ~ | P | Pivot only |

\* G2 passes only when the deploying entity holds a valid STOXX/DAX license.

---

## `L3` decision checklist

The Owner Decision should record:

1. **Outcome** — A / B / C / D from
   [layer1-source-selection-criteria.md](layer1-source-selection-criteria.md)
2. **Demo policy** — **P1 only** (P0 revoked)
3. **Macro leg** — MRO-only (reject), DFR-primary, or multi-rate bundle
4. **Market leg** — **live EWG (Alpha Vantage)**; licensed DAX for entity clones;
   ~~sample CSV~~ **forbidden**
5. **ADR-004** — update required? (yes if domain or primary narrative changes)
6. **Contract changes** — which `fin.*` YAML files and `source_of_truth` strings
7. **Explicit non-goals** — confirm no Kafka, no v3.0, no entity split

---

## References

- [layer1-source-selection-criteria.md](layer1-source-selection-criteria.md) — L1 rubric
- [ADR-004](decisions/ADR-004-financial-dataset.md) — current domain decision
- [ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) — P1, P7 recommendations
- [ECB FM dataset](https://data.ecb.europa.eu/data/datasets/FM) — rates and market statistics
- [STOXX DAX Conditions of Use](https://stoxx.com/legal/dax-conditions-of-use/)
- [Bundesbank download options](https://www.bundesbank.de/en/statistics/time-series-databases/help-on-the-time-series-databases/download-options)
