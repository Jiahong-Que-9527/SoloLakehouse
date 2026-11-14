# 03 · Airport Analytics

**Runtime:** BigQuery.

Model the Silver layer as analytical tables and answer operational questions
about Frankfurt Airport traffic with SQL. The focus is data modeling and SQL,
not infrastructure.

## Scope

- Load Silver data from GCS into BigQuery, with partitioning and clustering
  chosen from the query patterns.
- Define a dimensional or wide-table model for aircraft, arrivals and
  surface movement. Document grain, keys and definitions.
- Write reusable views or models for traffic volume, arrival rate by hour,
  runway-area activity and surface-time distributions.
- Check results against the Silver quality report and record row counts.
- Record query cost for the main queries.

## Milestones

- **M1.** Load one month of Silver into BigQuery and document the model.
- **M2.** Core analytics queries with expected results on a fixed sample.
- **M3.** Full-year model, cost record and short findings report.

## Acceptance

- Every table has a documented grain and a uniqueness check.
- Query results reconcile with Silver row counts.
- Findings state the data period, source and known limits. Surface times are
  proxies from state vectors, not airport ground truth.

## Depends on

Project 02 Silver output.

## Outputs

BigQuery dataset, model documentation and an analytics report. Project 05 can
use the same definitions for features.
