# Memory Ordering Notes (ARMv8-A)

Where the fences go, why, and what we expect under Ruby MESI_Two_Level.

## Host vs. target

The host harness runs on the dev machine (x86_64, TSO). TSO hides the
weak-ordering failure of `unsync`, so a host-only test cannot claim
correctness or failure for weak-ordering behavior.

The gem5 path cross-compiles to aarch64 and runs under Ruby. Ruby is not
a formal model of ARMv8 RMO, but its cache-controller-level reorderings
reproduce the phenomenon (a writer's non-fenced stores can be observed
out of order by another coherent cache). We use it as empirical evidence,
not as a proof. A stretch-goal Herd/cat litmus test backs the ordering
claims that matter.

## Fence placement per protocol

### `unsync`

No fences. Relaxed atomic stores/loads. The expectation is that the
consumer observes at least some records with partially-updated fields under
Ruby ARM. If we never see this under any amount of contention, the
experiment is still valid as a null result but the story becomes "Ruby's
observability of inter-field reordering is weak in this config" rather
than "the unsync protocol is safe."

### `seqlock`

Release fence pairs with acquire fence:

```text
Producer:                           Consumer:
  epoch++  (odd, relaxed)             epoch_before = load_acquire(epoch)
  fence(release)                      if odd: retry
  payload stores (relaxed)            payload loads (relaxed)
  fence(release)                      fence(acquire)
  epoch++  (even, relaxed)            epoch_after = load_acquire(epoch)
                                      if before != after: retry
```

Under ARMv8: the two release fences downgrade to `DMB ISHST` (store
ordering); the two acquire operations use `LDAR` (acquire load). Two
fences + two acquires per successful publish/read pair. The §11
"ordering cost" metric counts these.

### `dblbuf`

Single release / single acquire:

```text
Producer:                           Consumer:
  slot = 1 - published_idx            idx = load_acquire(published_idx)
  write full record to slot           memcpy from slot[idx]
  store_release(published_idx, slot)
```

Under ARMv8: `STLR` for the release store, `LDAR` for the acquire load.
No explicit fences. Cheapest reader by construction; writer pays the
doubled footprint, not extra fences.

## Things we are deliberately NOT doing

- We do not use `volatile`. It is not a synchronization primitive and
  would make the static analysis of the protocols meaningless.
- We do not use `__sync_*` legacy builtins. C11 atomics only.
- We do not use platform-specific barriers (`__DMB()`, `asm("dmb")`).
  C11 `atomic_thread_fence(memory_order_release)` compiles to the right
  ARMv8 instruction; we want the portability.
- We do not rely on compiler-level reordering being the same between host
  and target. Both builds use the same source; the simulator provides the
  hardware-level reordering answer, independent of compiler version.
