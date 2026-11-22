# Model report (M04)

- Source data release: `dataset-v001` (manifest `e0c8096c8233…`), features `feat-v1-dataset-v001` (manifest `0d12d224c599…`).
- Candidate: sklearn HistGradientBoostingRegressor, selected config `{'learning_rate': 0.1, 'max_leaf_nodes': 63, 'min_samples_leaf': 40}` (max_iter 300, seed 20261122, early stopping off).
- Selection split: issues ≤ 2026-08-31 for training, 2026-09-01 … 2026-09-30 for validation; 8 grid configs evaluated.
- Fold plan: 23 monthly folds, embargo 1 d, skipped months: 2025-01.

## Headline (pooled over the M03 folds)

| Model | MAE | RMSE | sMAPE | Rows |
|---|---|---|---|---|
| Model (selected config) | 6.353 | 9.837 | 8.451 | 626376 |
| Station median (M03) | 7.690 | 12.851 | 8.916 | 624144 |
| Seasonal naive (M03) | 9.152 | 15.329 | 10.587 | 625944 |

Gate: seasonal-naive MAE 9.152 kWh — candidate **beats** the baseline; station median MAE 7.690 kWh — beats the stronger baseline.

## Paired comparisons (positive difference: model worse)

| Comparison | Mean |err| difference (kWh) | Bootstrap 95% CI |
|---|---|---|
| model vs station median | -1.3343 | [-1.3534, -1.3156] |
| model vs seasonal naive | -2.7996 | [-2.8244, -2.7745] |

## Per-fold MAE (kWh)

| Fold | Model | Seasonal naive | Station median |
|---|---|---|---|
| 2025-02-01 → 2025-02-28 | 6.578 | 7.821 | 7.145 |
| 2025-03-01 → 2025-03-31 | 6.346 | 7.941 | 7.002 |
| 2025-04-01 → 2025-04-30 | 9.048 | 10.918 | 10.110 |
| 2025-05-01 → 2025-05-31 | 6.507 | 9.354 | 6.920 |
| 2025-06-01 → 2025-06-30 | 5.977 | 9.553 | 6.812 |
| 2025-07-01 → 2025-07-31 | 6.104 | 8.538 | 7.254 |
| 2025-08-01 → 2025-08-31 | 6.153 | 9.026 | 7.895 |
| 2025-09-01 → 2025-09-30 | 6.147 | 8.049 | 7.648 |
| 2025-10-01 → 2025-10-31 | 6.383 | 9.942 | 7.626 |
| 2025-11-01 → 2025-11-30 | 6.714 | 8.514 | 6.944 |
| 2025-12-01 → 2025-12-31 | 6.692 | 10.600 | 8.805 |
| 2026-01-01 → 2026-01-31 | 6.291 | 10.467 | 7.264 |
| 2026-02-01 → 2026-02-28 | 5.957 | 8.466 | 7.424 |
| 2026-03-01 → 2026-03-31 | 5.956 | 8.170 | 8.157 |
| 2026-04-01 → 2026-04-30 | 6.161 | 10.946 | 10.077 |
| 2026-05-01 → 2026-05-31 | 5.783 | 10.244 | 7.397 |
| 2026-06-01 → 2026-06-30 | 5.848 | 8.323 | 6.435 |
| 2026-07-01 → 2026-07-31 | 6.924 | 9.809 | 8.287 |
| 2026-08-01 → 2026-08-31 | 6.066 | 8.319 | 7.771 |
| 2026-09-01 → 2026-09-30 | 6.096 | 8.589 | 7.796 |
| 2026-10-01 → 2026-10-31 | 6.262 | 9.089 | 7.904 |
| 2026-11-01 → 2026-11-30 | 6.093 | 8.161 | 6.579 |
| 2026-12-01 → 2026-12-30 | 6.087 | 9.516 | 7.656 |

## District segments — model vs station median

| District | Model MAE | Median MAE | Delta (model − median) |
|---|---|---|---|
| D1 | 7.434 | 8.858 | -1.424 |
| D2 | 6.328 | 7.757 | -1.429 |
| D3 | 5.214 | 6.143 | -0.929 |
| D4 | 6.827 | 8.458 | -1.631 |
| D5 | 6.464 | 7.811 | -1.347 |
| D6 | 5.020 | 6.148 | -1.128 |

## Station segments — model vs station median

| Station | Model MAE | Median MAE | Delta |
|---|---|---|---|
| S001 | 10.392 | 12.777 | -2.385 |
| S002 | 11.380 | 12.716 | -1.336 |
| S003 | 4.231 | 5.035 | -0.804 |
| S004 | 8.534 | 10.191 | -1.657 |
| S005 | 9.991 | 12.089 | -2.098 |
| S006 | 4.943 | 6.221 | -1.277 |
| S007 | 3.467 | 4.170 | -0.703 |
| S008 | 6.530 | 7.664 | -1.134 |
| S009 | 5.772 | 7.453 | -1.681 |
| S010 | 7.498 | 9.452 | -1.954 |
| S011 | 6.085 | 7.124 | -1.038 |
| S012 | 6.406 | 7.683 | -1.277 |
| S013 | 9.070 | 11.018 | -1.949 |
| S014 | 3.137 | 3.815 | -0.677 |
| S015 | 4.574 | 5.122 | -0.548 |
| S016 | 6.252 | 7.446 | -1.193 |
| S017 | 6.843 | 8.472 | -1.629 |
| S018 | 2.523 | 3.013 | -0.490 |
| S019 | 8.336 | 9.841 | -1.505 |
| S020 | 4.978 | 5.488 | -0.510 |
| S021 | 2.994 | 3.621 | -0.627 |
| S022 | 8.106 | 9.746 | -1.641 |
| S023 | 10.311 | 12.978 | -2.668 |
| S024 | 8.305 | 10.552 | -2.247 |
| S025 | 2.840 | 3.491 | -0.651 |
| S026 | 4.246 | 4.822 | -0.576 |
| S027 | 8.346 | 10.438 | -2.092 |
| S028 | 5.634 | 7.177 | -1.544 |
| S029 | 4.541 | 5.512 | -0.971 |
| S030 | 8.005 | 9.372 | -1.367 |
| S031 | 4.982 | 6.291 | -1.309 |
| S032 | 4.595 | 5.466 | -0.871 |
| S033 | 5.652 | 6.543 | -0.891 |
| S034 | 11.010 | 13.684 | -2.673 |
| S035 | 5.197 | 6.682 | -1.485 |
| S036 | 2.851 | 3.488 | -0.637 |
| S037 | 7.165 | 8.498 | -1.333 |
| S038 | 4.682 | 5.949 | -1.267 |
| S039 | 6.368 | 6.988 | -0.620 |
| S040 | 2.838 | 2.896 | -0.058 |

## Selection grid (internal split, validation MAE)

| Config | Val MAE | Val RMSE |
|---|---|---|
| learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=20 | 6.4907 | 9.5608 |
| learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40 | 6.4964 | 9.5775 |
| learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=20 | 6.2185 | 9.3020 |
| learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=40 | 6.2023 | 9.3034 |
| learning_rate=0.1, max_leaf_nodes=31, min_samples_leaf=20 | 6.3130 | 9.3909 |
| learning_rate=0.1, max_leaf_nodes=31, min_samples_leaf=40 | 6.2874 | 9.3714 |
| learning_rate=0.1, max_leaf_nodes=63, min_samples_leaf=20 | 6.1069 | 9.2292 |
| learning_rate=0.1, max_leaf_nodes=63, min_samples_leaf=40 | 6.0867 | 9.2006 |

## Feature importance (permutation, MAE increase in kWh)

| Feature | Importance |
|---|---|
| hour_of_day | 45.6350 |
| demand_rolling_7d_mean | 17.8158 |
| capacity_kw | 13.4768 |
| day_of_week | 12.1022 |
| poi_category | 10.8169 |
| demand_latest | 4.9216 |
| demand_lag_24h | 1.1394 |
| event_boost | 0.3248 |
| demand_lag_168h | 0.2442 |
| district | 0.1051 |
| fcst_precipitation_mm | 0.0878 |
| fcst_temperature_c | 0.0216 |
| price_current | 0.0160 |
| price_at_target | 0.0032 |
| days_active | 0.0000 |

## Residual summary (model − label over pooled fold rows)

Bias +0.0739 kWh, mean |residual| 6.3556 kWh, p90 |residual| 15.4824 kWh, p99 |residual| 34.2514 kWh.

The numbers in this report are reproducible from the release IDs and the parameters above; the same inputs render these exact bytes.
