# Baseline report

- Source data release: `dataset-v001` (manifest `e0c8096c8233…`, config `8c0dd791fa25…`).
- Fold plan: 23 monthly folds, embargo 1 d, min train issues 14, skipped months: 2025-01.
- Baselines: seasonal naive (demand at target hour − 168 h) and per-station median by (hour, weekday), fitted per fold on a trailing 90 d window.

## Per-fold MAE (kWh)

| Fold | Issues | Rows | Seasonal naive | Station median |
|---|---|---|---|---|
| 2025-02-01 → 2025-02-28 | 28 | 26880 | 7.821 | 7.145 |
| 2025-03-01 → 2025-03-31 | 31 | 29760 | 7.941 | 7.002 |
| 2025-04-01 → 2025-04-30 | 30 | 28800 | 10.918 | 10.110 |
| 2025-05-01 → 2025-05-31 | 31 | 29760 | 9.354 | 6.920 |
| 2025-06-01 → 2025-06-30 | 30 | 28800 | 9.553 | 6.812 |
| 2025-07-01 → 2025-07-31 | 31 | 29760 | 8.538 | 7.254 |
| 2025-08-01 → 2025-08-31 | 31 | 29760 | 9.026 | 7.895 |
| 2025-09-01 → 2025-09-30 | 30 | 28800 | 8.049 | 7.648 |
| 2025-10-01 → 2025-10-31 | 31 | 29760 | 9.942 | 7.626 |
| 2025-11-01 → 2025-11-30 | 30 | 28800 | 8.514 | 6.944 |
| 2025-12-01 → 2025-12-31 | 31 | 29760 | 10.600 | 8.805 |
| 2026-01-01 → 2026-01-31 | 31 | 29760 | 10.467 | 7.264 |
| 2026-02-01 → 2026-02-28 | 28 | 26880 | 8.466 | 7.424 |
| 2026-03-01 → 2026-03-31 | 31 | 29760 | 8.170 | 8.157 |
| 2026-04-01 → 2026-04-30 | 30 | 28800 | 10.946 | 10.077 |
| 2026-05-01 → 2026-05-31 | 31 | 29760 | 10.244 | 7.397 |
| 2026-06-01 → 2026-06-30 | 30 | 28800 | 8.323 | 6.435 |
| 2026-07-01 → 2026-07-31 | 31 | 29760 | 9.809 | 8.287 |
| 2026-08-01 → 2026-08-31 | 31 | 29760 | 8.319 | 7.771 |
| 2026-09-01 → 2026-09-30 | 30 | 28800 | 8.589 | 7.796 |
| 2026-10-01 → 2026-10-31 | 31 | 29760 | 9.089 | 7.904 |
| 2026-11-01 → 2026-11-30 | 30 | 28800 | 8.161 | 6.579 |
| 2026-12-01 → 2026-12-30 | 30 | 28800 | 9.516 | 7.656 |

## Pooled overall metrics

| Baseline | MAE | RMSE | sMAPE | Rows |
|---|---|---|---|---|
| Seasonal naive | 9.152 | 15.329 | 10.587 | 625944 |
| Station median | 7.690 | 12.851 | 8.916 | 624144 |

## Paired comparison (station median vs seasonal naive)

Mean absolute-error difference -1.4700 kWh (positive: median worse), 95% bootstrap CI [-1.4947, -1.4453] over 2000 resamples (seed 20261122, n 624144).

The numbers in this report are reproducible from the data release ID and the parameters above; the same inputs render these exact bytes.
