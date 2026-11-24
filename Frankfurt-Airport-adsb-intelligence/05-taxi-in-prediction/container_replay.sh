#!/bin/sh
set -eu
if [ "$#" -ne 5 ]; then
    echo 'Usage: container_replay.sh TRAINING_FEATURES EVALUATION_FEATURES BASELINE_REPORT VALIDATION_DATE OUTPUT' >&2
    exit 2
fi
python=/app/.venv/bin/python
"$python" /app/boosted_candidate.py --features "$1" --baseline-report "$3" \
    --validation-from "$4" --output "$5/candidate" --tracking-dir "$5/tracking"
"$python" /app/frozen_evaluation.py --training-features "$1" --evaluation-features "$2" \
    --candidate "$5/candidate" --baseline-report "$3" --output "$5/evaluation" \
    --tracking-dir "$5/tracking"
