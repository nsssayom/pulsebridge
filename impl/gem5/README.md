# gem5 Integration

ARM SE-mode gem5 setup for the coherent-witness-export study. Runs the
producer/monitor harness on two cores with Ruby MESI_Two_Level and,
optionally, cache-thrash stressors on additional cores for the
contention sweep.

## Layout

```text
gem5/
├── configs/
│   └── two_core_ruby.py      # SE + Ruby MESI_Two_Level config, 2+N cores
├── docker/
│   ├── Dockerfile            # ubuntu:22.04 + gem5 deps + aarch64 cross-toolchain
│   ├── compose.yaml          # the `gem5` service + bind mounts
│   ├── Makefile              # wrappers: image / build-gem5 / build-workload / smoke / matrix
│   └── .env.example          # copy to .env and set GEM5_SRC
├── workload/
│   ├── Makefile              # aarch64 cross-compile for the harness + stressor
│   └── stress.c              # cache-thrash stressor (for --num-stressors>0)
└── scripts/
    └── run_matrix.sh         # sweep {protocol}×{workload}×{contention}
```

## Quickstart — Docker (recommended on macOS)

The `docker/` subtree provides a reproducible build/run environment and
is the blessed path on Apple Silicon, where upstream gem5 does not
cleanly build natively.

```text
# 1. clone gem5 somewhere (outside or inside this repo — doesn't matter)
git clone https://github.com/gem5/gem5.git ~/src/gem5

# 2. point the compose env at it
cd impl/gem5/docker
cp .env.example .env && $EDITOR .env    # set GEM5_SRC=~/src/gem5

# 3. build the image + gem5 + aarch64 m5ops + the SE workload
make image
make build-gem5     # ~20-40 min the first time (ARM_MESI_Two_Level)
make build-m5       # aarch64 libm5.a
make build-workload # bench-aarch64-{unsync,seqlock,dblbuf} + stress-aarch64

# 4. smoke test one cell
make smoke

# 5. run the full sweep
make matrix
```

`docker compose run --rm gem5 bash` (via `make shell`) drops into the
container if you want to poke at things directly.

The container keeps `gem5/build/` on a named docker volume to avoid
thrashing macOS's virtiofs layer with the build's tens of thousands of
.o files; everything else is a live bind mount so editing
`configs/two_core_ruby.py`, `scripts/run_matrix.sh`, the workload
sources, etc. takes effect immediately in the container.

## Native prerequisites (non-Docker, not recommended on macOS)

1. **aarch64 cross-compiler.** On Linux: `apt install gcc-aarch64-linux-gnu`.
   On macOS: `brew install aarch64-elf-gcc` and pass `CC=/opt/homebrew/bin/aarch64-elf-gcc`.
2. **gem5 source tree with the MESI_Two_Level build.**
   ```text
   git clone https://github.com/gem5/gem5.git
   cd gem5
   scons -j$(nproc) build/ARM_MESI_Two_Level/gem5.opt
   ```
3. **gem5 m5ops library for aarch64** (ROI markers / stats control):
   ```text
   cd $GEM5_ROOT/util/m5 && scons build/arm64/out/m5
   ```
   That produces `util/m5/build/arm64/out/libm5.a`.

## Build the SE-mode workload (native)

```text
cd impl/gem5/workload
make CC=aarch64-linux-gnu-gcc M5_DIR=$GEM5_ROOT/util/m5/build/arm64
```

Output in `build/`:
- `bench-aarch64-unsync`, `bench-aarch64-seqlock`, `bench-aarch64-dblbuf` — the
  harness statically linked against the selected publication protocol.
- `stress-aarch64` — the cache-thrash stressor.

The harness sources are shared with the host prototype. `m5_hooks.h`
expands to real `m5_reset_stats` / `m5_work_begin` / `m5_work_end` /
`m5_dump_stats` calls when `-DGEM5_M5OPS=1` is set (the Makefile does
this); the same sources still compile on the host with the hooks as
no-ops, which is how the host harness is tested.

## Smoke test (one cell)

```text
export GEM5_ROOT=/abs/path/to/gem5
$GEM5_ROOT/build/ARM_MESI_Two_Level/gem5.opt \
    --outdir=../../results/gem5/smoke/m5out \
    configs/two_core_ruby.py \
    --bench-bin workload/build/bench-aarch64-seqlock \
    --workload-dir ../workloads/synthesized/duty_bias \
    --cpu-type TimingSimpleCPU
```

Expected outputs in `../../results/gem5/smoke/m5out/`:
- `stats.txt` — gem5 counters, including the `workbegin/workend` ROI
  segments emitted by the harness.
- `config.ini` — materialized SimObject tree.
- Harness stdout (bench summary with protocol / workload / per-monitor
  counters) appears in gem5's stdout.

## Run the matrix

```text
GEM5_ROOT=/abs/path/to/gem5 ./scripts/run_matrix.sh
```

Defaults: `PROTOCOLS="unsync seqlock dblbuf dma_naive dma_seqlock"`,
`WORKLOADS="captured/periodic_suppression synthesized/duty_bias"`,
`CONTENTION="0 2 4"`. Workload paths are relative to `impl/workloads/`.
Override any of these as env vars.

Outputs land under `../../results/gem5/`:
- One directory per `(protocol, workload, stressor-count)` cell, with
  `gem5.stdout`, `gem5.stderr`, and the full `m5out/` from that run.
- `summary.csv` — one row per cell: protocol, workload, stressor count,
  host wallclock seconds, and exit cause. The analysis scripts
  ingest this and the per-cell `stats.txt` files.

## Config knobs

All passed to `two_core_ruby.py`:

| Flag                  | Default        | Purpose                                              |
| --------------------- | -------------- | ---------------------------------------------------- |
| `--bench-bin`         | _(required)_   | aarch64 `bench-aarch64-<proto>` binary               |
| `--workload-dir`      | _(required)_   | workload directory (witness.csv, evidence.csv, …)    |
| `--pacing-ns`         | `0`            | forwarded to harness — producer pacing               |
| `--epsilon`           | `0.10`         | forwarded — residual threshold                       |
| `--stl-window`        | `8`            | forwarded — STL window length                        |
| `--cpu-type`          | gem5 default   | `TimingSimpleCPU` (fast) or `DerivO3CPU` (realistic) |
| `--num-stressors`     | `0`            | extra CPUs running the cache-thrash stressor         |
| `--stressor-binary`   | _(none)_       | `workload/build/stress-aarch64`                      |
| `--stressor-footprint`| `4 MiB`        | per-stressor memory footprint                        |
| `--stressor-stride`   | `64`           | per-stressor walk stride                             |

Everything `common.Options.addCommonOptions`, `addSEOptions`, and
`Ruby.define_options` register is also available (e.g., `--num-dirs`,
`--num-l2caches`, `--l1d_size`, …).

## Mapping back to §11 metrics

- **Witness visibility latency** — difference between
  `m5_work_begin(ROI_ID_PRODUCER=1)` and `m5_work_end(ROI_ID_MONITOR=2)`
  per record (planned in `../analysis/`).
- **End-to-end publication-to-alarm latency** — start of
  `ROI_ID_END_TO_END=3` (main) to the monitor's STL-violation event.
- **Ordering / publication cost per record** — Ruby stats partitioned
  by the two ROI segments.
- **Torn-read rate** — monitor counter `mon.torn_reads` printed at end
  of the run. `unsync` and `dma_naive` are expected to tear under
  contention (no publication handshake — torn reads there measure the
  gap we are trying to close). `seqlock` and `dma_seqlock` must read 0
  by construction (version-counter validation). `dblbuf` is 0 only when
  the producer is rate-bounded relative to the reader; a small nonzero
  rate at producer≫reader is the narrow mid-memcpy race, not an
  atomicity bug (see `../docs/metrics_definitions.md`). Any other value
  is a bug.

## Known limitations

- Full-system ARM is out of scope. SE mode is sufficient for the
  coherence and ordering study for this repository.
- The stressor generates disjoint-line interference (separate
  footprint). Shared-line / witness-line interference is a stretch
  experiment and would need either shared-memory IPC between the
  harness and the stressor or deliberate line-collision placement.
- gem5's Ruby MESI_Two_Level is not a formal ARMv8 RMO model; we use it
  as empirical evidence of inter-field reordering observability, per
  `../docs/memory_ordering_notes.md`.
