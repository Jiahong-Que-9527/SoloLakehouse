# Aviation project roadmap

<!-- [Codex · 2026-11-13] Design proposal. -->

Start at the [Aviation project page](README.md) for source ownership and
reproduction boundaries. The [public case](../../docs/workloads/aviation.md)
records historical observations and the limits of the available evidence.
Keep implementation acceptance with the private project and publish only
approved, sanitized summaries. Use the [active queue](../../TASKS.md) for
shared SLH work.

| Stage | Exercise and deliverable | Acceptance |
|---|---|---|
| Beginner | Learn the observation schema, time windows, arrival candidates and taxi-in proxies. Prepare a small synthetic or explicitly approved fixture with expected candidate, proxy and missing-target examples. | Explain how each expected row follows from the observations, including missingness. Report proxies as proxies and distinguish airport ground truth. |
| Foundation | Reproduce a single-event or small-batch ETL. Define deduplication, late observations, label availability and the feature cutoff. Produce a versioned fixture, expected rows and repeatable commands. | Two runs agree on event identity, coverage and output. Assert that post-cutoff observations cannot enter the features. Include insufficient-coverage and duplicate cases. |
| Intermediate | Design private PR checks and release to an isolated Aviation target. Validate ingestion contracts, event rules, feature cutoffs and artifact packaging. | A private push runs Aviation CI. A failing required check blocks merge. A reviewed release traces from source SHA to artifact and a verified test run. |
| Advanced | Rehearse source-authentication failure, no-new-data rerun, backfill, and model artifact reload. Record data, contract, feature and model versions. | A failed acquisition has a clear status and recovery path. Reruns preserve data consistency. Report label coverage and experimental reproducibility with scope and dates. |
| Mastery | Demonstrate isolated data recovery and application rollback. Optionally design a small GCP or Databricks portability exercise with synthetic or approved data. | Recover a known snapshot and verify outputs independently of application rollback. Any cloud comparison records source permission, identity, cost and limitations. |

Proxy labels support a reproducible engineering exercise. They do not establish
airport-validated outcomes or a closed-loop cargo workflow. Keep published
claims within the [case limitations](../../docs/workloads/aviation.md#uses-and-limitations).
