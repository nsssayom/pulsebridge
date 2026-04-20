# Publication Protocols

Three publication disciplines implementing the same `publication.h` API.
They compile as separate translation units; a protocol is selected at link
time via `-DPUB_PROTOCOL=unsync|seqlock|dblbuf`.

## Common API

```c
typedef struct pub_ctx pub_ctx_t;

void pub_init(pub_ctx_t *ctx, void *region, size_t region_size);
void pub_publish(pub_ctx_t *ctx, const witness_record_t *src);
int  pub_read_snapshot(pub_ctx_t *ctx, witness_record_t *dst);
```

`pub_read_snapshot` returns 0 on success, `-EAGAIN` if the protocol
cannot currently produce a stable snapshot (only possible for seqlock under
contention), or `-EINVAL` if the region is malformed.

## Protocol 1: `unsync`

Naive multi-field write with no ordering discipline.

- Producer: memcpy the record into the slot using `memory_order_relaxed`
  atomic stores for each 8 B word.
- Consumer: memcpy out using `memory_order_relaxed` loads.
- No epoch parity, no fence.

Expected to produce torn snapshots under weak ordering and/or preemption.
Baseline for §11 torn-read rate. Relaxed atomics (not plain writes) because
we do not want the compiler optimizing the data race in ways that hide what
the coherence protocol would do at runtime.

## Protocol 2: `seqlock`

Linux-kernel-style seqlock reusing the `epoch` low bit.

- Producer:
  1. Load `epoch`, write `epoch := epoch + 1` (odd, in-progress) with
     `memory_order_relaxed`.
  2. `atomic_thread_fence(memory_order_release)`.
  3. Write all payload fields with relaxed stores.
  4. `atomic_thread_fence(memory_order_release)`.
  5. Write `epoch := epoch + 1` (even, published) with relaxed store.
- Consumer:
  1. Load `epoch_before` with `memory_order_acquire`.
  2. If odd, retry or return `-EAGAIN` per `pub_read_snapshot` contract.
  3. Read payload with relaxed loads.
  4. `atomic_thread_fence(memory_order_acquire)`.
  5. Load `epoch_after` with `memory_order_acquire`.
  6. If `epoch_before != epoch_after`, retry.

Invariant: consumer returns a payload iff `epoch_before == epoch_after` and
both are even. The consumer's retry budget is bounded (small constant);
exceeding it returns `-EAGAIN` so the monitor can still progress.

## Protocol 3: `dblbuf`

Two-slot double buffer with a released publish index.

- Region layout: `[published_idx: u32 | pad | slot0: record | slot1: record]`.
- Producer: alternates slots. Writes full record to inactive slot, then
  stores `published_idx` (0 or 1) with `memory_order_release`.
- Consumer: loads `published_idx` with `memory_order_acquire`, reads the
  corresponding slot with relaxed loads.

Invariant: the slot indexed by a released `published_idx` is stable for
the duration of the consumer's read, because the producer alternates and
the writer never touches the slot it just published until the next cycle.

Assumes: producer period ≫ consumer read latency. This is true for our
target T_c = 100 µs vs. expected read latency O(100 ns). The spec records
this assumption so it is falsifiable under contention experiments.

## Per-protocol invariants the harness checks

- `unsync`: none — used to demonstrate the failure mode.
- `seqlock`: consumer never returns a torn snapshot; retry count is bounded.
- `dblbuf`: consumer never returns a torn snapshot; published_idx advances
  monotonically modulo 2 per successful publish.

## Why three, not more

Unsync is the correctness baseline. Seqlock and dblbuf span the two main
points on the "writer cost vs. reader cost" Pareto curve: seqlock is cheap
to write (two epoch increments, two fences) but expensive to read under
contention (retry loop); dblbuf is cheap to read (one acquire + one load)
but doubles the write footprint. Adding more points would not change
any §5 RQ answer.
