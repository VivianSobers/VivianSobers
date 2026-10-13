#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
repo=${1:-"$root/../Differentiable Rasterizer"}
repo=$(CDPATH= cd -- "$repo" && pwd)
out=$(mktemp -d /tmp/profile-raster.XXXXXX)
cpu=$("$root/.venv/bin/python" -c 'import os; print(min(os.sched_getaffinity(0)))')
taskset -c "$cpu" "$repo/target/release/fit" "$repo/docs/target.png" \
    --tris 150 --iters 800 --seed 0 --out "$out"
"$root/.venv/bin/python" "$root/figures/raster/extract.py" "$repo" --out "$out"
echo "Raw fit retained in $out"
