# impl/

Implementation tree for the witness-publication channel study in this
repository.

## Layout

```text
impl/
├── core/           C11 library: witness record, publication protocols, residual, STL
├── prototype/      Host harness (pthreads on the dev machine)
├── workloads/      Producer workload data + generators (captured + synthesized)
├── gem5/           gem5 ARM Ruby configs and SE workload
├── analysis/       Metric extraction and figures
├── docs/           Design specs (record layout, protocols, ordering, metrics)
└── results/        Experimental outputs (gitignored; curated artifacts kept)
```

## Build

```text
make core           # host build of core library
make prototype      # host harness
make workloads      # regenerate synthesized workload CSVs
make gem5-workload  # cross-compile the gem5 SE benchmark (aarch64)
make clean
```

## Design authority

`docs/` holds the specs that pin down invariants the code must uphold.
When code and spec disagree, the spec wins; update the code or update the
spec deliberately, not silently.

- `docs/witness_record_spec.md` — field layout, alignment, version rules
- `docs/publication_protocols.md` — the three protocols and their invariants
- `docs/memory_ordering_notes.md` — where fences go and why (ARMv8)
- `docs/metrics_definitions.md` — how each §11 metric is computed

The tree is organized so the same `core/` code is reused by the host
prototype and the gem5 workload, with workload generation and analysis
kept in separate subtrees.
