# ADR-004: Why ECB Interest Rate + DAX Index Data

**Status:** Accepted
**Date:** 2024-01

## Context

v1 needs a real-world dataset to demonstrate the complete pipeline. Candidate datasets evaluated: financial market data (ECB + DAX), weather data (DWD), e-commerce data (synthetic), IoT sensor data (synthetic).

## Decision

The project uses ECB Main Refinancing Operations (MRO) rate data combined with
DAX-style daily price data.

For the reference pipeline, the ECB portion is fetched live from the
public ECB SDW API, while the DAX portion is represented by a repository-bundled
simulated sample CSV. This keeps the demo runnable without introducing third-party
market data licensing or API dependencies.

## Rationale

**1. Geographic and market resonance with Frankfurt.**
The European Central Bank is headquartered in Frankfurt. ECB monetary policy decisions directly affect German financial markets, including the DAX. For a portfolio targeting Frankfurt FinTech companies (Deutsche Bank, DWS, Commerzbank, ING, N26, Adyen), using ECB + DAX data signals awareness of the local market context. This is a non-trivial signal that differentiates from generic "Titanic" or "Iris" dataset projects.

**2. The data has realistic engineering challenges.**
Financial time series data comes with data engineering challenges that demonstrate real skill:
- **Non-trading days**: weekends and public holidays must be filtered from market data
- **Sparse rate change events**: ECB only changes rates ~10-20 times over a 10-year period; the pipeline must handle this correctly
- **Date alignment**: ECB decisions happen on specific dates that may not align with the next trading day
- **Missing values**: rate data may have gaps that require principled handling (forward-fill, not zero-fill)

**3. The ECB-DAX event study is a complete, meaningful ML use case.**
The Gold layer (event study feature table) has genuine financial meaning: does ECB rate policy affect DAX short-term returns? This is a real research question studied in academic finance. The ML framing (binary classification: DAX up/down after rate change) is simple but defensible. A hiring manager from a FinTech background will recognise the domain context and understand why the features were designed the way they were.

**4. Public-source compatibility with a repo-safe demo path.**
ECB SDW REST API is free and open. DAX historical data exists publicly, but
this repository ships with a simulated sample CSV instead of redistributing
or depending on a third-party market data feed. This keeps the demo free of API
keys, registration barriers, and licensing ambiguity.

**5. Appropriate data volume for a v1 demo.**
A compact simulated DAX sample plus ~80 ECB meeting observations is large enough
to demonstrate the pipeline while remaining fast to run on a laptop.

## Rejected Alternatives

**Weather data (DWD):** Technically interesting but lacks the domain resonance with Frankfurt FinTech hiring managers. The ML use case (weather forecasting) is also less directly relevant to the target market.

**Synthetic e-commerce data:** Too generic. Every beginner tutorial uses this data. It doesn't differentiate.

**IoT sensor data:** Interesting for v2's streaming ingestion feature, not the best fit for a batch Lakehouse demonstration.
