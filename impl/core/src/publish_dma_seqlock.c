/*
 * publish_dma_seqlock.c — DMA-pull baseline *with* a seqlock handshake.
 *
 * Uses the same WitnessPullEngine as publish_dma_naive.c, but wraps the
 * producer-writes / monitor-reads sides in a seqlock discipline so that
 * the explicit-transfer case has the same atomicity guarantee as
 * coherent peer publication. This is the fair explicit-transfer baseline.
 *
 * The shared region on each page is laid out as:
 *
 *     +-- offset 0 -----------------------------------+
 *     | epoch (u64, seq counter: odd=writing, even=ok)|
 *     | ts_ns (u64)                                   |
 *     | duty_a_bits, duty_b_bits, duty_c_bits (3×u32) |
 *     | config_id (u32)                               |
 *     | mac_lo (u64)                                  |
 *     | reserved (u64)                                |
 *     +-- offset 48 ----------------------------------+
 *
 * i.e. the same seqlock_region_t layout used by publish_seqlock.c. The
 * DMA engine copies the full 64-byte witness cache line into the mirror
 * page each tick. Atomicity holds even though the engine is naive about
 * the seqlock state because the seqlock check happens *on the monitor
 * side* reading the mirror:
 *   - If the engine snapshotted the witness mid-write, the mirror's
 *     epoch is odd → the monitor rejects the read (EAGAIN).
 *   - If the monitor reads the mirror mid-DMA-write, the epoch_before /
 *     epoch_after check on the mirror will fail → EAGAIN.
 *
 * Producer discipline (writer side, exact mirror of publish_seqlock.c):
 *   epoch ← src.epoch - 1  (odd, "writing")
 *   payload stores
 *   epoch ← src.epoch       (even, "published")
 *
 * The engine just copies the bytes; correctness is recovered by the
 * seqlock on the consumer side.
 *
 * Simulator-behavior assumption: this correctness argument relies on
 * Ruby modeling the 64-byte mirror-page DMA write as a single atomic
 * transaction that the monitor either observes fully or not at all
 * (witness_pull_engine.cc:~106 issues one PullPacket per tick, which
 * the DMASequencer services as one Ruby request). On real silicon a
 * 64-byte bus write may become multiple smaller transactions and the
 * mid-write "monitor reads the mirror" case would need an additional
 * producer-side epoch bump on the mirror, not just on the witness.
 * Flagged here so follow-on work on a real PL330/CDMA engine does not
 * inherit the assumption silently.
 */
#include <stdatomic.h>
#include <stdalign.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <gem5/m5ops.h>

#include "publication.h"
#include "witness_record.h"

#define DMA_PAGE_SIZE          4096u
#define DMA_REGION_SIZE        WITNESS_CACHELINE  /* 64 B */
#define DMA_PERIOD_NS_DEFAULT  1000u
#define SEQLOCK_MAX_RETRIES    8

typedef struct {
    _Atomic uint64_t epoch;
    _Atomic uint64_t ts_ns;
    _Atomic uint32_t duty_a_bits;
    _Atomic uint32_t duty_b_bits;
    _Atomic uint32_t duty_c_bits;
    _Atomic uint32_t config_id;
    _Atomic uint64_t mac_lo;
    _Atomic uint64_t reserved;
} seqlock_region_t;

_Static_assert(sizeof(seqlock_region_t) == 48, "seqlock payload is 48 B");
_Static_assert(sizeof(seqlock_region_t) <= DMA_REGION_SIZE,
               "seqlock payload must fit in the DMA'd cache line");

static alignas(DMA_PAGE_SIZE) uint8_t witness_page[DMA_PAGE_SIZE];
static alignas(DMA_PAGE_SIZE) uint8_t mirror_page [DMA_PAGE_SIZE];

static uint64_t g_dma_period_ns = DMA_PERIOD_NS_DEFAULT;

void pub_set_dma_period_ns(uint64_t period_ns) {
    g_dma_period_ns = period_ns ? period_ns : DMA_PERIOD_NS_DEFAULT;
}

static inline uint32_t f2u(float f) {
    uint32_t u;
    memcpy(&u, &f, 4);
    return u;
}

static inline float u2f(uint32_t u) {
    float f;
    memcpy(&f, &u, 4);
    return f;
}

int pub_init(pub_ctx_t *ctx, void *region, size_t region_size) {
    (void)region;
    (void)region_size;

    if (!ctx) return PUB_EINVAL;
    if (((uintptr_t)witness_page & (DMA_PAGE_SIZE - 1)) != 0 ||
        ((uintptr_t)mirror_page  & (DMA_PAGE_SIZE - 1)) != 0) {
        fprintf(stderr, "publish_dma_seqlock: static pages not 4KiB-aligned\n");
        return PUB_EINVAL;
    }

    memset(witness_page, 0, DMA_PAGE_SIZE);
    memset(mirror_page,  0, DMA_PAGE_SIZE);

    ctx->region           = witness_page;
    ctx->region_size      = DMA_REGION_SIZE;
    ctx->publishes        = 0;
    ctx->successful_reads = 0;
    ctx->eagain_reads     = 0;
    ctx->retries          = 0;

    m5_dma_setup((uint64_t)(uintptr_t)witness_page,
                 (uint64_t)(uintptr_t)mirror_page,
                 (uint64_t)DMA_REGION_SIZE,
                 g_dma_period_ns);
    m5_dma_start();

    return 0;
}

void pub_publish(pub_ctx_t *ctx, const witness_record_t *src) {
    seqlock_region_t *r = (seqlock_region_t *)witness_page;

    /* Mark "writing" by making epoch odd. The DMA engine may snapshot
     * at any instant; a mirror snapshotted here will look torn to the
     * monitor's seqlock check. */
    atomic_store_explicit(&r->epoch, src->epoch - 1, memory_order_relaxed);
    atomic_thread_fence(memory_order_release);

    atomic_store_explicit(&r->ts_ns,       src->ts_ns,       memory_order_relaxed);
    atomic_store_explicit(&r->duty_a_bits, f2u(src->duty_a), memory_order_relaxed);
    atomic_store_explicit(&r->duty_b_bits, f2u(src->duty_b), memory_order_relaxed);
    atomic_store_explicit(&r->duty_c_bits, f2u(src->duty_c), memory_order_relaxed);
    atomic_store_explicit(&r->config_id,   src->config_id,   memory_order_relaxed);
    uint64_t mac_lo;
    memcpy(&mac_lo, src->mac, 8);
    atomic_store_explicit(&r->mac_lo,      mac_lo,           memory_order_relaxed);
    atomic_store_explicit(&r->reserved,    src->reserved,    memory_order_relaxed);

    atomic_thread_fence(memory_order_release);
    atomic_store_explicit(&r->epoch, src->epoch, memory_order_relaxed);

    ctx->publishes++;
}

int pub_read_snapshot(pub_ctx_t *ctx, witness_record_t *dst) {
    seqlock_region_t *r = (seqlock_region_t *)mirror_page;

    for (int attempt = 0; attempt < SEQLOCK_MAX_RETRIES; attempt++) {
        uint64_t e_before = atomic_load_explicit(&r->epoch, memory_order_acquire);
        if (e_before & 1ull) {
            /* DMA snapshotted witness mid-write; retry next tick. */
            ctx->retries++;
            continue;
        }

        dst->epoch     = e_before;
        dst->ts_ns     = atomic_load_explicit(&r->ts_ns,       memory_order_relaxed);
        dst->duty_a    = u2f(atomic_load_explicit(&r->duty_a_bits, memory_order_relaxed));
        dst->duty_b    = u2f(atomic_load_explicit(&r->duty_b_bits, memory_order_relaxed));
        dst->duty_c    = u2f(atomic_load_explicit(&r->duty_c_bits, memory_order_relaxed));
        dst->config_id = atomic_load_explicit(&r->config_id,   memory_order_relaxed);
        uint64_t mac_lo = atomic_load_explicit(&r->mac_lo,     memory_order_relaxed);
        memcpy(dst->mac, &mac_lo, 8);
        dst->reserved  = atomic_load_explicit(&r->reserved,    memory_order_relaxed);

        atomic_thread_fence(memory_order_acquire);
        uint64_t e_after = atomic_load_explicit(&r->epoch, memory_order_acquire);

        if (e_before == e_after) {
            ctx->successful_reads++;
            return 0;
        }
        /* DMA wrote a newer snapshot between our payload loads. */
        ctx->retries++;
    }

    ctx->eagain_reads++;
    return PUB_EAGAIN;
}

const char *pub_protocol_name(void) { return "dma_seqlock"; }

void pub_stats_snapshot(const pub_ctx_t *ctx, pub_stats_t *out) {
    out->publishes        = ctx->publishes;
    out->successful_reads = ctx->successful_reads;
    out->eagain_reads     = ctx->eagain_reads;
    out->retries          = ctx->retries;
}
