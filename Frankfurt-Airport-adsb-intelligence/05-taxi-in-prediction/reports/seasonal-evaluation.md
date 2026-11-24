# EDDF taxi-in candidate evaluation

Evaluation `seasonal-007f14573a94cc7e` used model release
`frankfurt-airport-taxi-in-ca2c8f9b21863f18` (models:/frankfurt-airport-taxi-in/1) and the frozen
299.0-second global median. Each season is represented by one
held-out month. Overall MAE pools all usable labels. Coverage divides usable
labels by all predictions. Positive improvement means lower candidate MAE.

The inputs use ADS-B proxy labels and a simulated 5-second observation delay.
Hourly groups use Europe/Berlin time, including daylight-saving changes. Traffic
counts arrival triggers made available during the previous 60 minutes, including
unlabeled arrivals and excluding the current second. The first incomplete hour
of each month has its own group. Sparse groups have less evidence.

## Overall and by season

| Group | Predictions | Usable labels | Coverage | Baseline MAE (s) | Candidate MAE (s) | Improvement (s) |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 65,981 | 51,319 | 77.8% | 180.2 | 171.3 | +8.9 |
| Winter · 2024-12 | 8,249 | 7,182 | 87.1% | 148.6 | 137.5 | +11.2 |
| Spring · 2025-04 | 15,892 | 10,792 | 67.9% | 155.7 | 151.7 | +4.0 |
| Summer · 2025-07 | 17,244 | 13,099 | 76.0% | 160.8 | 152.3 | +8.5 |
| Autumn · 2025-10 | 24,596 | 20,246 | 82.3% | 217.1 | 206.0 | +11.1 |

## By local hour

| Group | Predictions | Usable labels | Coverage | Baseline MAE (s) | Candidate MAE (s) | Improvement (s) |
|---|---:|---:|---:|---:|---:|---:|
| 00 | 4 | 2 | 50.0% | 776.5 | 759.3 | +17.2 |
| 01 | 11 | 1 | 9.1% | 102.0 | 256.1 | -154.1 **worse** |
| 02 | 9 | 0 | 0.0% | — | — | — |
| 03 | 6 | 0 | 0.0% | — | — | — |
| 04 | 27 | 5 | 18.5% | 251.0 | 212.7 | +38.3 |
| 05 | 2,368 | 2,060 | 87.0% | 193.1 | 152.4 | +40.7 |
| 06 | 2,684 | 2,185 | 81.4% | 214.1 | 168.2 | +45.8 |
| 07 | 5,179 | 3,988 | 77.0% | 183.5 | 166.0 | +17.5 |
| 08 | 5,182 | 4,246 | 81.9% | 181.3 | 179.0 | +2.3 |
| 09 | 4,305 | 3,568 | 82.9% | 186.7 | 185.5 | +1.2 |
| 10 | 3,485 | 2,888 | 82.9% | 214.5 | 214.5 | +0.0 |
| 11 | 4,035 | 3,398 | 84.2% | 181.4 | 182.0 | -0.6 **worse** |
| 12 | 3,485 | 2,889 | 82.9% | 175.9 | 174.1 | +1.8 |
| 13 | 2,772 | 2,235 | 80.6% | 203.3 | 197.0 | +6.3 |
| 14 | 2,494 | 1,963 | 78.7% | 178.9 | 173.1 | +5.8 |
| 15 | 4,272 | 3,313 | 77.6% | 150.9 | 146.6 | +4.4 |
| 16 | 4,396 | 3,395 | 77.2% | 166.1 | 162.1 | +4.0 |
| 17 | 2,605 | 1,966 | 75.5% | 168.7 | 160.0 | +8.7 |
| 18 | 3,262 | 2,505 | 76.8% | 154.2 | 147.4 | +6.8 |
| 19 | 4,407 | 3,410 | 77.4% | 155.6 | 150.6 | +5.0 |
| 20 | 5,935 | 4,132 | 69.6% | 198.4 | 189.2 | +9.3 |
| 21 | 2,781 | 1,698 | 61.1% | 166.6 | 155.4 | +11.2 |
| 22 | 2,031 | 1,283 | 63.2% | 171.1 | 153.1 | +18.0 |
| 23 | 246 | 189 | 76.8% | 147.4 | 132.9 | +14.5 |

## By arrival triggers in the previous hour

| Group | Predictions | Usable labels | Coverage | Baseline MAE (s) | Candidate MAE (s) | Improvement (s) |
|---|---:|---:|---:|---:|---:|---:|
| 0–9 | 2,519 | 2,172 | 86.2% | 168.3 | 144.0 | +24.4 |
| 10–19 | 11,108 | 9,211 | 82.9% | 160.0 | 144.9 | +15.1 |
| 20–29 | 12,120 | 9,568 | 78.9% | 162.7 | 150.7 | +12.0 |
| 30+ | 40,234 | 30,368 | 75.5% | 192.7 | 187.7 | +5.0 |
| insufficient history | 0 | 0 | — | — | — | — |
