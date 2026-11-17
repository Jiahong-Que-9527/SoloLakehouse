# ECB Delta Lakehouse implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** planned. [Brief](../README.md) · [Design](design.md)

## First delivery

Produce one versioned quarterly dataset that a reviewer can reconstruct before and after an ECB correction. Start with the public USD-per-EUR series and one explicitly named policy-rate series. Record the selected quarter, series keys, units, retrieval dates and file hashes with the fixture.

## Implementation sequence

1. Before implementation, write expected results for two FX dates, a duplicate input, a missing observation and a policy rate effective across multiple dates. Record the chosen publication calendar. Define expected Silver keys and which Gold rows carry a prior policy rate.

2. Land the original input with a stable source batch ID. Preserve source text and units. Normalize to one Silver row per series and observation date. Reject ambiguous conflicting values within the same batch and exercise replay of an identical batch.

3. Derive the Gold indicators from a specific Silver version. Check an FX value and a carried-forward rate by hand. Record the source observation date for the carried value so a consumer can distinguish an observation from an imputation.

4. In an isolated workspace schema, apply a synthetic revision to one observation by MERGE. Query the old and new table versions and reconcile the one changed key, its unit and its source batch. Rerun the correction and check that the logical result stays the same.

5. Publish a release record containing source hashes, transformation commit, Silver and Gold table identities and Delta versions, quality result and row count. Give D02 the transform revision and D05 a reproducible snapshot reference.

## Portfolio evidence

Evidence: before/after SQL results for one corrected key, a replay comparison and one release record. Explain where original observations, derived values and published versions are distinguished. Link measured results from the brief after execution.
