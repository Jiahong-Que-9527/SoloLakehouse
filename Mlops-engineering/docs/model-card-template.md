# Model card template

<!-- [魏征·2026-11-21] Add the model card template for model releases. -->

Every model release registered from M05 onward ships a completed copy of this card next to its manifest.

## 1. Identification

- Model name, release ID, registry version, git SHA, training data release ID, card date.

## 2. Intended use

- The decision the prediction supports and its owner. What the model must not be used for.

## 3. Training data

- Data release ID, period, station coverage, exclusions and the label definition with its coverage rate.

## 4. Evaluation

- Backtest protocol (folds, embargo), headline metrics with the pinned baseline for comparison, segment tables (hour, station, district) and the acceptance outcome (beats baseline: yes/no, with numbers).

## 5. Limitations

- Known failure modes, segments where error concentrates, coverage gaps of the synthetic domain, and what a real deployment would additionally require.

## 6. Maintenance

- Retraining triggers in force, monitoring thresholds, last drill date and the rollback procedure reference.
