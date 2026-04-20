# Metrics Definitions

Exact computational definitions of the §11 metrics. A metric listed here
has a single computation path across all experiments; diverging from this
spec is a bug.

## Primary architecture metrics

### Witness visibility latency

- Definition: cycles from the producer store that makes `epoch` even
  (seqlock) / `published_idx` released (dblbuf) / last-field relaxed store
  (unsync) to the consumer's acquire load of the same.
- Source: gem5 `m5_work_begin` at the producer, `m5_work_end` at the
  consumer, diffed per record.
- Unit: simulated cycles.

### End-to-end publication-to-alarm latency

- Definition: cycles from the producer `m5_work_begin` to the monitor
  issuing an alarm (if any) for the same epoch.
- Source: `m5_work_begin` at producer, `m5_work_end` at alarm generation.
- Unit: simulated cycles and ns.
- Budget: 2·T_s = 200 µs (PMSM benchmark target, CDC §IV-B).

### Latency tail under contention

- Definition: 99th- and 99.9th-percentile witness visibility latency.
- Requires: ≥ 10⁴ records per run for stable percentiles.

### Publication-side cost per record

- Definition: cycles spent in `pub_publish` per record.
- Source: `m5_reset_stats` around `pub_publish`; read `simTicks`.

### Ordering cost per record

- Definition: cycles attributable to fences/release stores, separate from
  data-write cycles.
- Source: gem5 stats — fence occupancy on the MSHR (Ruby-level counters).
- Reporting: total ordering cycles and percent of per-record publication cost.

### Fences/barriers executed per record

- Definition: integer count per `pub_publish` invocation.
- Source: static per-protocol constant (verified once) plus Ruby counter
  confirmation.

### Coherence traffic volume per record

- Definition: (invalidations, data transfers, directory transactions)
  issued per record, per core.
- Source: Ruby statistics: `system.ruby.L1Cache_Controller.*`,
  `system.ruby.Directory_Controller.*`.

### Consumer-side read cost

- Definition: cycles spent in `pub_read_snapshot`, decomposed by the
  starting state of the witness line in the consumer's L1 (clean/shared/
  invalid/owned-elsewhere).
- Source: prime the line to a known state, then measure.

### Effect of witness-region layout

- Compare the above metrics across `LAYOUT_SINGLE_LINE`, `LAYOUT_SPLIT_LINE`,
  `LAYOUT_SHARED_LINE`.

## Correctness metrics

### Torn-read rate

- Definition: fraction of consumer reads whose payload fields correspond
  to two different producer publication events.
- Detection mechanism: the producer records a second independent check
  field `epoch` into both `epoch` and `config_id`'s low 16 bits; any
  consumer read where these disagree is torn.
- Applies to: `unsync` and `dma_naive` — both lack a publication
  handshake and are *expected* to tear (dma_naive tears because the DMA
  engine can snapshot the witness mid-write; torn reads there measure
  the cost of the missing handshake, not a bug).
- `seqlock` and `dma_seqlock` must return 0 torn reads by construction —
  the reader validates a version counter before and after the payload
  copy and retries (or returns `EAGAIN`) on mismatch. Any nonzero
  reading there is a bug. `dma_seqlock` is the fair explicit-transfer
  baseline: same DMA engine as `dma_naive`, but the monitor validates a
  seqlock on the mirror so mid-DMA-write snapshots are rejected.
- `dblbuf` returns 0 torn reads *only under bounded producer rate*
  (producer ≲ reader, so the producer cannot get two publishes ahead
  during a single reader memcpy). When the producer is much faster than
  the reader, publish #(k+2) can overwrite the slot the reader is
  mid-copy on — a narrow but real race. A small nonzero dblbuf torn
  rate (≪ `dma_naive`, ≪ `unsync`) is consistent with this geometry,
  not a correctness bug in the atomic index hand-off. True zero-torn
  under arbitrary rates would need triple-buffering or a seqlock on the
  slot payload.

### Mixed-snapshot rate

- Like torn-read rate, but at the field level. Counts how many fields of
  a torn read belong to "old" vs. "new" epochs.

### Epoch monotonicity failures

- Definition: consumer observes a successful `pub_read_snapshot` whose
  epoch is ≤ the previously observed epoch.
- Reported as count and rate.

### False alarm / missed alarm counts

- False alarm: alarm raised for a record that is nominal by ground truth.
- Missed alarm: ground-truth divergence event with no alarm within the
  detection budget.
- Ground truth: the workload generator writes a side-channel label stream
  the monitor never reads.

## Workload-validation sanity checks

### Alarm rate by workload variant

- Must be 0 under nominal, nonzero under divergence. Sanity only, not a
  primary finding.

### Publication-to-alarm latency by workload variant

- Reported as a sanity median; the primary metric is the latency tail.

### Sensitivity of end-to-end latency to protocol × contention level

- Reported as a grid over `{unsync, dma_naive, dma_seqlock, seqlock,
  dblbuf} × {none, moderate, heavy}`. Heavy-contention torn-read rates
  for `unsync` and `dma_naive` are expected to climb; tail latencies for
  `seqlock` / `dma_seqlock` are expected to climb via retry; `dblbuf`'s
  reader is expected to be insensitive to contention.
