# District Forecast

<!-- [M09 · 2026-11-23] Second workload onboarded from the ML delivery template. -->

**Status:** accepted 2026-11-23 · [ML Engineering](../README.md) · [Template](../09-platform-factory/template/ONBOARDING.md)

The second workload of M09: next-day hourly charging demand aggregated to
the six districts, issued at the same 06:00 Europe/Berlin instant as the
station-level model. It was instantiated from
[`09-platform-factory/template`](../09-platform-factory/template/ONBOARDING.md)
and proves the template end to end: its own dataset contract, feature
contract, baseline report, release manifest and model card — without
touching the reference workload.

## Delivery shape

- **Dataset contract.** `build-dataset` consumes the pinned
  `dataset-v001` release and aggregates station-hour demand to
  district-hour (`available_at` = max over contributing stations), with
  the tariff schedule collapsed per district (uniformity enforced), plus
  deterministic release manifests under `releases/dataset-district/`.
- **Feature contract.** The M02 availability table at district grain:
  calendar and tariff/event schedules join by schedule semantics,
  day-ahead weather forecasts need `available_at <= T`, demand lags
  (24 h / 168 h) anchor at the issue time T with a 7-day rolling mean
  over [T − 168 h, T − 2 h], and same-day demand is never readable. A
  shift test freezes the stamp semantics.
- **Evaluation.** The template's fold harness (23 rolling monthly folds,
  1-day embargo, paired bootstrap, deterministic report bytes) with
  district-level seasonal-naive and (hour, weekday) median baselines.
- **Model and gate.** One gradient-boosted regressor under the frozen
  M04 discipline (`OMP_NUM_THREADS=1`, pinned config); the promotion
  gate refuses a candidate that does not strictly beat both baselines.
- **Releases.** `releases/models-district/<id>/manifest.json` committed
  with full lineage (data/feature manifest SHA-256s, git SHA, artifact
  checksum) and a model card; the artifact stays outside Git under
  `data/models/`. Reruns reuse every step by content
  (full-scale rerun: 0.86 s vs 54 s fresh, bytes identical).

## Result

`model-district-2a1a4b7a6bd8eb34` (2026-11-23): pooled protocol MAE
**22.338 kWh** over 100,368 labeled rows — strictly better than the
seasonal-naive 30.980 and the district median 33.629. See the
[model card](releases/models-district/model-district-2a1a4b7a6bd8eb34/model-card.md)
and the [acceptance record](../09-platform-factory/evidence/m09-acceptance.md).

## Run it

```bash
uv sync --locked
uv run --locked pytest
uv run --locked district-forecast --config configs/district-v001.yaml run-pipeline \
    --source-release ../reference-workload/data/releases/dataset/v001 --workdir .
```

Consuming the reference release reads `../reference-workload/data/...`;
everything this workload writes stays inside its own directory. The CI
workflow is scoped to `Mlops-engineering/district-forecast/**`.
