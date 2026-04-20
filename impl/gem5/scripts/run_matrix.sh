#!/usr/bin/env bash
#
# Sweep the {protocol} x {workload} x {contention} grid through gem5.
# Writes one output directory per cell under $OUT_DIR, plus a summary
# CSV that the analysis scripts can ingest.
#
# Required env:
#   GEM5_ROOT   gem5 source tree (must contain build/ARM_MESI_Two_Level/gem5.opt
#               and configs/ruby/MESI_Two_Level.py)
#
# Optional env:
#   GEM5_BIN    path to the gem5 binary
#               (default: $GEM5_ROOT/build/ARM_MESI_Two_Level/gem5.opt)
#   OUT_DIR     results root
#               (default: ../results/gem5 relative to this script)
#   PROTOCOLS   space-separated subset of
#               {unsync seqlock dblbuf dma_naive dma_seqlock}
#   WORKLOADS   space-separated workload subdirs under ../workloads/data
#   CONTENTION  space-separated stressor counts (0=nominal)
#   CPU_TYPE    gem5 CPU class (default: TimingSimpleCPU)
#   MAX_TICK    gem5 --abs-max-tick (0=no cap)
#   PACING_NS   harness --pacing-ns
#   DMA_PERIOD_NS  DMA-pull engine tick period in ns (dma_* protocols only;
#               default 1000)
#
# Usage:
#   GEM5_ROOT=/path/to/gem5 ./scripts/run_matrix.sh
#   GEM5_ROOT=/path/to/gem5 PROTOCOLS=seqlock CONTENTION="0 4" \
#       ./scripts/run_matrix.sh
#

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEM5_DIR="$(cd "$HERE/.." && pwd)"
IMPL_DIR="$(cd "$GEM5_DIR/.." && pwd)"

: "${GEM5_ROOT:?set GEM5_ROOT to your gem5 source tree}"
GEM5_BIN="${GEM5_BIN:-$GEM5_ROOT/build/ARM_MESI_Two_Level/gem5.opt}"
OUT_DIR="${OUT_DIR:-$IMPL_DIR/results/gem5}"
PROTOCOLS="${PROTOCOLS:-unsync seqlock dblbuf dma_naive dma_seqlock}"
# Workload paths are relative to ../workloads/ (i.e. impl/workloads/).
WORKLOADS="${WORKLOADS:-captured/periodic_suppression synthesized/duty_bias}"
CONTENTION="${CONTENTION:-0 2 4}"
CPU_TYPE="${CPU_TYPE:-TimingSimpleCPU}"
MAX_TICK="${MAX_TICK:-0}"
PACING_NS="${PACING_NS:-0}"
DMA_PERIOD_NS="${DMA_PERIOD_NS:-1000}"

if [[ ! -x "$GEM5_BIN" ]]; then
    echo "error: gem5 binary not executable: $GEM5_BIN" >&2
    echo "       build it: cd \$GEM5_ROOT && scons build/ARM_MESI_Two_Level/gem5.opt" >&2
    exit 1
fi

CFG="$GEM5_DIR/configs/two_core_ruby.py"
WORKLOAD_BUILD="$GEM5_DIR/workload/build"
WORKLOAD_DATA="$IMPL_DIR/workloads"

STRESSOR_BIN="$WORKLOAD_BUILD/stress-aarch64"

mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/summary.csv"
echo "protocol,workload,stressors,dma_period_ns,cell_dir,host_wall_s,exit_cause" > "$SUMMARY"

run_one() {
    local proto="$1" wl="$2" nstr="$3"
    local bench="$WORKLOAD_BUILD/bench-aarch64-$proto"
    local wl_dir="$WORKLOAD_DATA/$wl"
    # Flatten workload path into the cell name (captured/periodic_suppression -> captured-periodic_suppression)
    local wl_flat="${wl//\//-}"
    local cell="$OUT_DIR/${proto}__${wl_flat}__str${nstr}"
    if [[ "$proto" == dma_* ]]; then
        cell="${cell}__dma${DMA_PERIOD_NS}ns"
    fi
    local cell_m5="$cell/m5out"

    if [[ ! -x "$bench" ]]; then
        echo "skip: bench missing: $bench"
        return 0
    fi
    if [[ ! -d "$wl_dir" ]]; then
        echo "skip: workload missing: $wl_dir"
        return 0
    fi
    if [[ "$nstr" != "0" && ! -x "$STRESSOR_BIN" ]]; then
        echo "skip: stressor missing: $STRESSOR_BIN (needed for stressors=$nstr)"
        return 0
    fi

    mkdir -p "$cell_m5"
    echo "=== $proto / $wl / stressors=$nstr  ->  $cell"

    local -a gem5_args=(
        --outdir="$cell_m5"
    )
    if [[ "$MAX_TICK" != "0" ]]; then
        gem5_args+=(--abs-max-tick="$MAX_TICK")
    fi

    local -a script_args=(
        --bench-bin "$bench"
        --workload-dir "$wl_dir"
        --pacing-ns "$PACING_NS"
        --dma-period-ns "$DMA_PERIOD_NS"
        --cpu-type "$CPU_TYPE"
    )
    if [[ "$proto" == dma_* ]]; then
        script_args+=(--enable-dma-engine)
    fi
    if [[ "$nstr" != "0" ]]; then
        script_args+=(--num-stressors "$nstr" --stressor-binary "$STRESSOR_BIN")
    fi

    local t0 t1 wall exit_cause
    t0=$(date +%s)
    if "$GEM5_BIN" "${gem5_args[@]}" "$CFG" "${script_args[@]}" \
            > "$cell/gem5.stdout" 2> "$cell/gem5.stderr"; then
        exit_cause="ok"
    else
        exit_cause="nonzero($?)"
    fi
    t1=$(date +%s)
    wall=$((t1 - t0))

    echo "$proto,$wl,$nstr,$DMA_PERIOD_NS,$cell,$wall,$exit_cause" >> "$SUMMARY"
}

for proto in $PROTOCOLS; do
    for wl in $WORKLOADS; do
        for nstr in $CONTENTION; do
            run_one "$proto" "$wl" "$nstr"
        done
    done
done

echo
echo "summary: $SUMMARY"
