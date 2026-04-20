# Witness Record Specification

Canonical, versioned layout of the multi-field record the producer publishes
and the monitor consumes. This spec is the authority; `core/include/witness_record.h`
implements it.

## Canonical record (v1)

| Offset | Size | Field        | Type         |
|--------|------|--------------|--------------|
| 0      | 8    | `epoch`      | `uint64_t`   |
| 8      | 8    | `ts_ns`      | `uint64_t`   |
| 16     | 4    | `duty_a`     | `float`      |
| 20     | 4    | `duty_b`     | `float`      |
| 24     | 4    | `duty_c`     | `float`      |
| 28     | 4    | `config_id`  | `uint32_t`   |
| 32     | 8    | `mac`        | `uint8_t[8]` |
| 40     | 8    | `reserved`   | `uint64_t`   |

Total: **48 bytes**. Single-line layout fits in one 64 B line; multi-line
layout straddles two lines when placed with a 32 B offset.

Field notes:

- `epoch` — monotonic control-step counter. The seqlock protocol reuses
  its low bit (odd = publication in progress, even = stable). Other
  protocols must publish only even `epoch` values.
- `ts_ns` — producer-side timestamp in nanoseconds. Informational only;
  snapshot correctness does not depend on it.
- `duty_a/b/c` — intended duty cycle per channel, in `[0.0, 1.0]`.
- `config_id` — controller configuration identifier. Low 16 bits carry a
  duplicate epoch-tag for the torn-read detector (see
  `metrics_definitions.md`).
- `mac` — opaque placeholder. Not evaluated in this study; present so the
  record crosses 32 B and makes the single-line vs. multi-line comparison
  nondegenerate.
- `reserved` — zero. Pads the record to 48 B.

## Alignment and layout variants

`witness_record_t` is declared `_Alignas(64)` in the canonical layout.
Layout variants exercised as a §11 metric:

- `LAYOUT_SINGLE_LINE` — `_Alignas(64)`, record fits in one 64 B line.
- `LAYOUT_SPLIT_LINE` — record deliberately placed to straddle a cache-line
  boundary. The record struct is offset by 32 B from the line base.
- `LAYOUT_SHARED_LINE` — record placed on a line that also holds unrelated
  writable data being touched by a third core.

All three share the same record definition; the difference is allocation
and placement, not field layout.

## Invariants

1. **Field offsets are stable within version 1.** Adding or removing a
   field requires bumping `config_id`'s high byte to encode a new version
   and updating this spec.
2. **`epoch` is the linearization point.** A monitor read is valid iff it
   observed a stable `epoch` across the read window for the protocol in use.
3. **The seqlock protocol reuses `epoch`'s low bit.** Protocols other than
   seqlock MUST publish only even `epoch` values so a cross-protocol trace
   still carries meaningful monotonicity.
4. **`ts_ns` is informational.** Snapshot correctness does not depend on it.
5. **Producer writes only to the canonical record slot(s) of its
   publication context.** The double-buffer protocol uses two slots; the
   producer alternates. No protocol shares slots with unrelated data.
6. **`mac` is never inspected.** Present only to make the record
   nontrivially larger than a pointer pair.

## Size rationale

48 B is the smallest size that (a) holds the real producer state from the
CDC workload, (b) cannot fit in one 32 B line, and (c) fits in one 64 B
line. This makes the single-line vs. multi-line layout comparison
nondegenerate without bloating the record with synthetic padding.
