# Workload CSV schema

Each workload variant produces two aligned CSV files plus a `PROVENANCE` file.

## `witness.csv`

Intended three-phase duty values as the controller believes it is commanding.

| Column    | Type | Units | Meaning                                                         |
|-----------|------|-------|-----------------------------------------------------------------|
| epoch     | u64  | —     | Monotone per-period counter, starts at 2, step 2 (always even)  |
| ts_ns     | u64  | ns    | Period boundary timestamp                                       |
| duty_a    | f32  | —     | Intended duty for phase A, range [0.0, 1.0]                     |
| duty_b    | f32  | —     | Intended duty for phase B                                       |
| duty_c    | f32  | —     | Intended duty for phase C                                       |
| config_id | u32  | —     | Controller configuration identifier                             |

## `evidence.csv`

Realized three-phase duty values measured from actual PWM edges (captured) or
modeled deviation from the intended values (synthesized). Same schema as
`witness.csv` except `config_id` is omitted — the consumer uses the witness's
`config_id`.

| Column | Type | Units | Meaning                                                      |
|--------|------|-------|--------------------------------------------------------------|
| epoch  | u64  | —     | Must match the witness row with the same epoch               |
| ts_ns  | u64  | ns    | Period boundary timestamp (may differ slightly from witness) |
| duty_a | f32  | —     | Realized duty for phase A                                    |
| duty_b | f32  | —     | Realized duty for phase B                                    |
| duty_c | f32  | —     | Realized duty for phase C                                    |

## Alignment invariant

For every row `i`: `witness[i].epoch == evidence[i].epoch`. The prototype and
gem5 harness both assume the two streams can be iterated in lockstep and never
re-sort. `validate_workload.py` enforces this.

Epochs are even because seqlock uses the low bit as "write in progress"; the
lock-free reader treats odd epochs as torn. Passing an even epoch to every
protocol keeps the three protocols' epoch semantics identical from the outside.

## `PROVENANCE`

A free-form text file documenting:

- variant name
- `CAPTURED` or `SYNTHESIZED` (one-word tag)
- source artifacts (paths, commit, sha256 of raw inputs)
- generator script and its arguments
- channel mapping (which physical channels back which duty_a/b/c)
- any synthesized columns or values and the formula used
- number of periods, sample period in ns, total duration
- sha256 of the generated `witness.csv` and `evidence.csv`
