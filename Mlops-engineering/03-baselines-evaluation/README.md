# M03 · Baselines and evaluation harness

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Fix the rules of comparison before training anything: a rolling backtest protocol, a segment-aware metric suite and a deterministic report that every later stage reuses.

## Deliverables

- The `eval` package: rolling-origin fold builder with embargo, the metric suite (MAE, RMSE, sMAPE; by hour, station and district) and the paired-comparison method (bootstrap confidence intervals) chosen in the [delivery plan](../docs/delivery-plan.md).
- Baseline models: seasonal naive (same hour last week) and per-station median by hour and weekday.
- The report template rendered to a deterministic artifact: the same inputs produce the same report bytes.
- The committed baseline report over the M01 data release, with segment tables and the fold plan recorded.

## Acceptance

1. The fold builder refuses an embargo violation, and its fold boundaries are stable across reruns.
2. Two harness runs over the same features and fold plan produce byte-identical reports.
3. The baseline report states, per segment, the error that M04's model must beat, and the numbers are reproducible from the release ID.

M04 may not change the metric suite or fold plan without a recorded decision in the delivery plan.
