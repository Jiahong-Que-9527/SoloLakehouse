# 05 · Taxi-in Prediction

<!-- [GLM·2026-11-20] Replace the Vertex AI runtime with the cloud-neutral MLflow path; see docs/adr/ADR-005. -->

**Runtime:** Local training first, packaged as a container; MLflow for experiment tracking and the model registry ([ADR-005](../docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md)).

Train and evaluate a model that predicts taxi-in time for arrivals at `EDDF`.
Start with a simple baseline and add complexity only when it improves a
measured result.

## Important caveat

Taxi-in labels derive from ADS-B state vectors. They are proxy labels, not
airport ground truth. Report label coverage and definition with every result.

## Scope

- Define the target: start and end events, and the rules for edge cases.
- Train from the pinned Parquet dataset and feature manifest produced by
  project 04. The Geometry v2 release from project 02 supplies proxy labels.
- Use a time-ordered split. Never shuffle across time.
- Establish baselines first (historical mean or median by condition), then a
  gradient-boosted model.
- Track experiments, parameters, metrics and model artifacts in MLflow.
- Store model artifacts outside Git. Version them and link each to a source
  commit and training data version.

## Milestones

- **M1.** Label definition and coverage report. The November 2024 feature
  artifact provides 7,607 usable proxy labels.
- **M2.** Historical global-median baseline on a time-ordered split. The
  November 2024 run was evaluated and logged locally in MLflow.
- **M3.** Histogram gradient-boosted candidate selected on the inner time
  split and evaluated against the pinned November holdout in local MLflow.
- **M4.** Repeat the training as a containerized job, register the model version in MLflow and publish its release manifest (ADR-005).
- **M5.** Evaluation report with error by hour, season and traffic level.

## Acceptance

- Training is reproducible from the label release ID, label and training
  manifest hashes, source and dependency lock hashes, and recorded split dates.
- The feature manifest gives the prediction cutoff, timestamp provenance and
  passed leakage checks for the rows used in training.
- The model beats the baseline on the held-out period, or the report says it
  does not.

## Depends on

The [project 04 feature handoff](../04-aviation-lakehouse/README.md#first-delivery)
supplies the versioned local training artifact. Record label coverage,
matching losses and any simulated historical availability when reporting
baseline results in MLflow.

## Outputs

A versioned model artifact and an evaluation report, used by project 06.

## November 2024 baseline

Use `prediction_at` in UTC. Fit one constant median on predictions before
2024-11-21, and score the predictions from that cutoff onward. Training
uses only `matched_labeled` targets and excludes a training label if the
latest possible taxi end could fall at or after the holdout start. That
bound uses the 90-second matching window and the 2,700-second label limit.
The holdout coverage denominator includes every prediction in the holdout.

```bash
cd Fraport-adsb-intelligence/05-taxi-in-prediction
uv sync --locked
uv run --locked python -m unittest -v
run_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
features="$run_root/features/features-2024-11-947edc9a58661dcd"
out=$(mktemp -d /tmp/fraport-baseline.XXXXXX)
uv run --locked python median_baseline.py --features "$features" \
  --holdout-from 2024-11-21 --output "$out/first"
uv run --locked python median_baseline.py --features "$features" \
  --holdout-from 2024-11-21 --output "$out/replay"
cmp "$out/first/baseline-report.json" "$out/replay/baseline-report.json"
```

The median was **299 seconds**, fitted on **5,080** labels. The holdout had
**2,527** usable labels out of **2,870** predictions (88.0%). MAE was **140.3
seconds**, RMSE **180.5 seconds** and median absolute error **118 seconds**.
The experiment uses the feature replay's five-second simulated availability
and retrospective proxy labels. The metrics apply to the evaluated matched
predictions. The report records input and code hashes, the split and
metrics. Each execution records its own local MLflow run ID in `run.json`.

## November 2024 boosted candidate

The candidate uses the seven approved project 04 predictors. An eight-point
grid chooses the tree size, iteration count and regularization on labeled
predictions from November 16 through 20. The tuning fit uses earlier labels.
Both cutoffs use the baseline's label-maturity rule. After selection the
candidate refits on the same 5,080 labels used by the baseline, then scores
the same 2,527 holdout labels. The selected configuration limits each tree
to seven leaves, runs 60 iterations and uses L2 regularization of 1.0.

| Holdout metric | Global median | Boosted candidate |
|---|---:|---:|
| MAE | 140.3 s | 129.3 s |
| RMSE | 180.5 s | 170.2 s |
| Median absolute error | 118.0 s | 105.0 s |

The MAE improvement is 11.0 seconds (7.8%). This was measured on one
month using proxy labels and a five-second simulated observation delay.
Evaluate additional months and validate observation availability before
promoting a serving candidate.

```bash
cd Fraport-adsb-intelligence/05-taxi-in-prediction
uv sync --locked
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run --locked python -m unittest -v
run_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
features="$run_root/features/features-2024-11-947edc9a58661dcd"
baseline="$run_root/baselines/geometry-v2-2024-11-median"
out=$(mktemp -d /tmp/fraport-candidate.XXXXXX)
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run --locked python boosted_candidate.py \
  --features "$features" --baseline-report "$baseline/first/baseline-report.json" \
  --validation-from 2024-11-16 --output "$out/first"
```

The local output includes `model.pkl`, the model's feature order and SHA-256,
the full search, the baseline comparison and the MLflow run ID.
