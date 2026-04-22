# Witness Publication Channel Evaluation

This repository contains the implementation and experimental artifacts for a
controller-to-monitor witness channel study. The setup models a controller
publishing a latest-state witness record, a monitor reading that record on
another core, and a residual check against independently acquired evidence.

The implementation focus is the publication path itself: how a fixed-size
multi-field witness record should be handed off so the monitor never accepts a
mixed snapshot, and what that choice costs under interference.

## What Is Evaluated

The study uses a 64-byte witness record and compares five publication
architectures:

| Architecture | Transport | Publication rule |
| --- | --- | --- |
| `unsync` | direct shared record | none |
| `seqlock` | direct shared record | odd/even sequence validation |
| `dblbuf` | double-buffered shared record | released slot handoff |
| `dma_naive` | mirrored record | none |
| `dma_seqlock` | mirrored record | odd/even sequence validation |

The main evaluation runs in gem5 Arm SE mode with Ruby
`MESI_Two_Level`. The matrix spans:

- 5 publication architectures
- 2 workload variants
- 3 interference levels

That gives a 30-cell experimental matrix over correctness and cost.

## Workloads

The repository includes one captured workload and one synthesized workload:

- `captured/periodic_suppression`: a per-period witness/evidence trace derived
  from a PWM actuation-integrity benchmark
- `synthesized/duty_bias`: a generated workload with a persistent `+15%`
  multiplicative bias in the evidence path

Workload generation and provenance files live under [impl/workloads](impl/workloads).

## Quick Start

Build the host-side components:

```text
make -C impl core
make -C impl prototype
make -C impl workloads
```

The supported gem5 reproduction path is the Docker workflow under
[impl/gem5/docker](impl/gem5/docker). It expects an external gem5 checkout via
`GEM5_SRC`.

```text
cd impl/gem5/docker
cp .env.example .env
# set GEM5_SRC=/abs/path/to/your/gem5 checkout
make image
make build-gem5
make build-m5
make build-workload
make smoke
make matrix
```

For more detail on the gem5 setup, use [impl/gem5/README.md](impl/gem5/README.md).

## Repository Layout

- [impl/](impl): implementation tree
- [impl/core/](impl/core): shared C11 record and publication code
- [impl/prototype/](impl/prototype): pthread-based host harness
- [impl/workloads/](impl/workloads): captured and synthesized workload inputs
- [impl/gem5/](impl/gem5): gem5 configs, workload build, and Docker workflow
- [impl/analysis/](impl/analysis): metric extraction and plotting helpers
- [impl/docs/](impl/docs): record, protocol, ordering, and metric specs
- [impl/results/](impl/results): experimental outputs

## Notes

- The host prototype is a functional validation path. The main architecture
  measurements come from the gem5 workflow.
- The checked-in result artifacts are curated because the analysis and plotting
  flow depend on them.
