/*
 * publish_dma_naive.c — DMA-pull baseline *without* publication handshake.
 *
 * This is the deliberately-unsynchronized explicit-transfer baseline: it
 * measures the cost of treating "DMA transfer" as synonymous with "atomic
 * publication." The producer writes witness_page with plain relaxed
 * stores (no version stamp, no handshake), a gem5-internal DMA engine
 * (WitnessPullEngine) periodically snapshots witness_page into
 * mirror_page, and the monitor reads mirror_page with plain loads.
 * Tearing can happen on either side of the hop:
 *   1. The DMA engine snapshots witness mid-write (producer has only
 *      committed k of 8 payload words to coherence).
 *   2. The monitor loads mirror mid-DMA-write (DMA has only committed k
 *      of 8 words to the mirror).
 *
 * The sibling baseline `publish_dma_seqlock.c` wraps the same engine in
 * a versioned handshake and is the *fair* explicit-transfer comparison
 * point for the paper. Both pages are statically allocated in .bss with
 * fixed 4 KiB-aligned VAs so the SE page table maps each to exactly one
 * physical frame; pub_init() hands both VAs to the engine via
 * m5_dma_setup() / m5_dma_start() and then steps out of the way.
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

#define DMA_PAGE_SIZE   4096u
#define DMA_REGION_SIZE WITNESS_CACHELINE  /* 64 B — one line, the witness payload */
#define DMA_PERIOD_NS_DEFAULT 1000u        /* matches default workload period */

typedef struct {
    _Atomic uint64_t words[8];
} dma_region_t;

_Static_assert(sizeof(dma_region_t) == DMA_REGION_SIZE,
               "dma_region must be one cache line");

static alignas(DMA_PAGE_SIZE) uint8_t witness_page[DMA_PAGE_SIZE];
static alignas(DMA_PAGE_SIZE) uint8_t mirror_page [DMA_PAGE_SIZE];

/* Overridden via pub_set_dma_period_ns() before pub_init(). */
static uint64_t g_dma_period_ns = DMA_PERIOD_NS_DEFAULT;

void pub_set_dma_period_ns(uint64_t period_ns) {
    g_dma_period_ns = period_ns ? period_ns : DMA_PERIOD_NS_DEFAULT;
}

int pub_init(pub_ctx_t *ctx, void *region, size_t region_size) {
    /* The caller's `region` is unused for DMA — we own both endpoints. */
    (void)region;
    (void)region_size;

    if (!ctx) return PUB_EINVAL;
    if (((uintptr_t)witness_page & (DMA_PAGE_SIZE - 1)) != 0 ||
        ((uintptr_t)mirror_page  & (DMA_PAGE_SIZE - 1)) != 0) {
        fprintf(stderr, "publish_dma_naive: static pages not 4KiB-aligned\n");
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

    /* On gem5 this hands both VAs to the WitnessPullEngine, which
     * translates them to PAs via the SE page table and arms a periodic
     * dmaRead(witness_pa)->dmaWrite(mirror_pa) loop. On bare metal (or
     * a non-gem5 emulator) these m5ops would trap; the bench is only
     * ever run under gem5. */
    m5_dma_setup((uint64_t)(uintptr_t)witness_page,
                 (uint64_t)(uintptr_t)mirror_page,
                 (uint64_t)DMA_REGION_SIZE,
                 g_dma_period_ns);
    m5_dma_start();

    return 0;
}

void pub_publish(pub_ctx_t *ctx, const witness_record_t *src) {
    dma_region_t *r = (dma_region_t *)witness_page;
    uint64_t staging[8];
    memcpy(staging, src, sizeof(staging));
    for (size_t i = 0; i < 8; i++) {
        atomic_store_explicit(&r->words[i], staging[i], memory_order_relaxed);
    }
    ctx->publishes++;
}

int pub_read_snapshot(pub_ctx_t *ctx, witness_record_t *dst) {
    dma_region_t *r = (dma_region_t *)mirror_page;
    uint64_t staging[8];
    for (size_t i = 0; i < 8; i++) {
        staging[i] = atomic_load_explicit(&r->words[i], memory_order_relaxed);
    }
    memcpy(dst, staging, sizeof(staging));
    ctx->successful_reads++;
    return 0;
}

const char *pub_protocol_name(void) { return "dma_naive"; }

void pub_stats_snapshot(const pub_ctx_t *ctx, pub_stats_t *out) {
    out->publishes        = ctx->publishes;
    out->successful_reads = ctx->successful_reads;
    out->eagain_reads     = ctx->eagain_reads;
    out->retries          = ctx->retries;
}
