# Host harness

Software-only prototype of the coherent witness-export pipeline. Runs producer
and monitor as two pthreads on the dev machine, exercising one of the three
publication protocols per binary.

Per-protocol binaries (built from a single source set linked against different
`libcore-<proto>.a`):

```text
build/harness-unsync
build/harness-seqlock
build/harness-dblbuf
```

## Running

```text
./build/harness-<proto> --workload ../workloads/<variant> [--pacing-ns N]
                       [--epsilon F] [--stl-window N]
```

Workload directory must contain `witness.csv`, `evidence.csv`, `PROVENANCE`
as specified in `../workloads/SCHEMA.md`.

## What each protocol demonstrates

This harness is not a timing-accurate model — x86 TSO hides much of what
ARM-style weak ordering exposes. It validates the three libcore-*.a APIs
end-to-end and establishes the torn-read detector's signal before we take
the same binaries into gem5.

Expected qualitative signal (observed locally):

- **unsync**: non-zero torn-read count — tag and epoch can be observed
  out of step because the multi-field write has no publication fence.
- **seqlock**: zero torn reads, but `pub.retries` grows with contention and
  `pub.eagain` becomes non-zero when the reader exhausts its retry budget.
- **dblbuf**: zero or very low torn reads under bounded producer rate; rises
  when the producer wraps back to a slot the reader is still consuming.
  This is a known property of index-only double buffering and will be
  characterized explicitly in the gem5 experiments.

## Output

Single-line `key=value` records on stdout, suitable for ingestion by the
analysis pipeline in `../analysis/`.
