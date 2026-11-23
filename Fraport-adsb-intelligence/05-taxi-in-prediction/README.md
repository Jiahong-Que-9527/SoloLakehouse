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
  split and evaluated against the pinned November holdout and an independent
  December replay in local MLflow.
- **M4.** Offline Docker replay verified the model and both reports byte for
  byte. The candidate is registered in local MLflow and recorded in the
  [release manifest](releases/fraport-taxi-in-f3b6b1ebf360fce8.json).
- **M5.** Completed the frozen evaluation across four held-out months and
  recorded [error and label coverage by season, local hour and traffic level](reports/seasonal-evaluation.md).

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

The MAE improvement is 11.0 seconds (7.8%). See the subsequent December
evaluation below for the frozen model.

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

## December 2024 independent evaluation

The November candidate and the 299-second baseline were frozen before
scoring the December replay. The feature dataset uses the November rules,
feature order and five-second simulated availability. All 8,249 predictions
were scored, and 7,182 had usable labels (87.1% coverage). The report pins
the model, baseline report and both feature manifests by hash.

| December metric | Frozen global median | Frozen boosted candidate |
|---|---:|---:|
| MAE | 148.6 s | 137.5 s |
| RMSE | 201.2 s | 190.0 s |
| Median absolute error | 118.0 s | 105.9 s |

MAE improved by 11.2 seconds (7.5%). The candidate had lower MAE on all
31 scored UTC days. December feature replays matched byte-for-byte, as did
the two evaluation reports. Both evaluation runs are recorded in the local
MLflow experiment. The evaluation uses proxy labels and simulated
observation availability. Validate measured availability before serving.

```bash
cd Fraport-adsb-intelligence/05-taxi-in-prediction
run_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
baseline="$run_root/baselines/geometry-v2-2024-11-median"
out=$(mktemp -d /tmp/fraport-december-evaluation.XXXXXX)
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run --locked python frozen_evaluation.py \
  --training-features "$run_root/features/features-2024-11-947edc9a58661dcd" \
  --evaluation-features "$run_root/features/features-2024-12-cc0d68f941eb2b79" \
  --candidate "$run_root/candidates/geometry-v2-2024-11-boosted/first" \
  --baseline-report "$baseline/first/baseline-report.json" \
  --tracking-dir "$baseline/mlflow" --output "$out/first"
```

## Local candidate release

Release `fraport-taxi-in-f3b6b1ebf360fce8` maps to local MLflow version
`models:/fraport-taxi-in/1`. The manifest pins the image ID, Git commit,
data manifests, evaluation reports and model checksum. The model and the
registry database are stored locally. The manifest records the five-second
simulated observation delay used in the evaluation. Verify measured
availability before promoting a version for serving.

Run from this directory in a clean checkout with Docker, GNU tar and uv.
Set `run_root` to the directory containing the pinned local artifacts.
The container runs without network access and reads copies of the inputs.
Use the manifest's `source_commit` to rebuild the recorded code version.

```bash
set -euo pipefail
run_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
training=features/features-2024-11-947edc9a58661dcd
evaluation=features/features-2024-12-cc0d68f941eb2b79
baseline=baselines/geometry-v2-2024-11-median
baseline_report=$baseline/first/baseline-report.json
commit=$(git rev-parse HEAD)
image=fraport-taxi-in:m4
out=$(mktemp -d /tmp/fraport-model-release.XXXXXX)

docker build --build-arg "SOURCE_COMMIT=$commit" -t "$image" .
docker run --rm --network none "$image"
container=$(docker create --network none "$image" /bin/sh /app/container_replay.sh \
  "/input/$training" "/input/$evaluation" "/input/$baseline_report" 2024-11-16 /output)
trap 'docker rm -f "$container" >/dev/null' EXIT
tar -C "$run_root" --mode=a+rX -cf - "$training" "$evaluation" "$baseline_report" \
  | docker cp - "$container:/input"
docker start -a "$container"
test "$(docker inspect "$container" --format '{{.State.ExitCode}}')" = 0
mkdir "$out/replay"
docker cp "$container:/output/." - | tar -xf - -C "$out/replay"

candidate="$run_root/candidates/geometry-v2-2024-11-boosted/first"
frozen="$run_root/evaluations/geometry-v2-2024-12-frozen/first"
uv run --locked python model_release.py verify-container \
  --candidate "$candidate" --evaluation "$frozen" --replay "$out/replay" \
  --image-id "$(docker image inspect "$image" --format '{{.Id}}')" \
  --source-commit "$commit" --output "$out/container-verification.json"
uv run --locked python model_release.py register \
  --candidate "$candidate" --evaluation "$frozen" \
  --container-evidence "$out/container-verification.json" \
  --tracking-dir "$run_root/$baseline/mlflow" --output "$out/release"
```

Registration checks that the model and both reports match the verified SHA-256
values and that the candidate improves MAE on both scored windows. It then
checks that the version can be loaded from MLflow and emits `manifest.json`
alongside the pinned model. Repeating registration with the same evidence in
the same local registry reuses the version.

## Cross-season evaluation

MLflow candidate version 1 and the frozen 299-second median both scored
65,981 replayed predictions, of which 51,319 had usable proxy labels (77.8%).
Pooled MAE fell from 180.2 to 171.3 seconds (4.9%). The candidate improved in
all four sampled months. It lost by 0.6 seconds during the 11:00 local hour
(3,398 usable labels) and lost at 01:00 (one usable label). At 30 or more arrival
triggers in the prior hour, it improved MAE by 5.0 seconds with 75.5% label coverage.
April had the lowest monthly coverage (67.9%). The simulation and proxy labels
remain limitations when deciding what to serve.

The [report](reports/seasonal-evaluation.md) contains all slices. The
[JSON evidence](reports/seasonal-evaluation.json) pins the release, baseline,
each input manifest and Parquet checksum, and the scoring code and dependency lock.

From this directory, rebuild the three later feature datasets with the phase 04
replayer and score them together with the pinned December dataset.

```bash
set -euo pipefail
run_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
out=$(mktemp -d /tmp/fraport-seasonal.XXXXXX)
for month in 2025-04 2025-07 2025-10; do
  (
    cd ../04-aviation-lakehouse
    uv run --locked python feature_replay.py --silver-root "$run_root/silver" \
      --label-release "$run_root/releases-geometry-v2/geometry-v2-$month" \
      --output "$out/$month" --simulated-delay-seconds 5
  )
done
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run --locked python seasonal_evaluation.py \
  --release-manifest releases/fraport-taxi-in-f3b6b1ebf360fce8.json \
  --model "$run_root/model-releases/geometry-v2-2024-11-m4/release/model.pkl" \
  --training-features "$run_root/features/features-2024-11-947edc9a58661dcd" \
  --baseline-report "$run_root/baselines/geometry-v2-2024-11-median/first/baseline-report.json" \
  --evaluation-features "$run_root/features/features-2024-12-cc0d68f941eb2b79" \
    "$out/2025-04" "$out/2025-07" "$out/2025-10" --output "$out/evaluation"
```
