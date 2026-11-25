#!/usr/bin/env bash
# Preview retirement of one disposable G06 stack. Never applies the plan.
set -euo pipefail

if [[ $# -ne 1 || ( "$1" != alpha && "$1" != bravo ) ]]; then
    echo "Usage: bash $0 {alpha|bravo}" >&2
    exit 2
fi

infra_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
stack_dir="$infra_dir/stacks/$1"

echo "Preview only: slh-gcp-test / G06 / $1"
terraform -chdir="$stack_dir" init -input=false
terraform -chdir="$stack_dir" plan -destroy -input=false -lock=false
