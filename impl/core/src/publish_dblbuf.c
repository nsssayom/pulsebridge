/*
 * publish_dblbuf.c — double-buffered publication with a generation counter.
 *
 * Layout: one header cacheline (atomic generation) + two payload slots,
 * each a full witness cacheline. Producer always writes the "other"
 * slot and then releases a monotonically-increasing generation; reader
 * picks the slot by generation parity and validates that the producer
 * didn't lap twice during its copy.
 *
 * Why a generation counter instead of a 2-state published_idx:
 *   With a 2-state flag the reader picks a slot, begins its 64-byte
 *   memcpy, and if the producer publishes twice during that copy
 *   (k+1 → other slot, k+2 → back to reader's slot), the second publish
 *   silently overwrites the slot the reader is in the middle of copying.
 *   The flag has no way to detect this because it is back to its
 *   previous value. A monotonic generation captures the lap directly:
 *     retry when gen_after - gen_before >= 2.
 *   That restores the zero-torn contract under arbitrary producer rate,
 *   while preserving dblbuf's advantage over a single-slot seqlock:
 *   the reader retries only when the producer laps twice, not on every
 *   publish.
 */
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>

#include "publication.h"

#define DBLBUF_MAX_RETRIES 8

typedef struct {
    alignas(WITNESS_CACHELINE) _Atomic uint64_t published_gen;
    uint64_t         _pad0;
    uint8_t          _pad1[WITNESS_CACHELINE - 16];
} dblbuf_header_t;

_Static_assert(sizeof(dblbuf_header_t) == WITNESS_CACHELINE, "dblbuf header = 1 line");

typedef struct {
    dblbuf_header_t  hdr;
    witness_record_t slots[2];
} dblbuf_region_t;

int pub_init(pub_ctx_t *ctx, void *region, size_t region_size) {
    if (!ctx || !region || region_size < sizeof(dblbuf_region_t)) return PUB_EINVAL;
    if (((uintptr_t)region & (WITNESS_CACHELINE - 1)) != 0) return PUB_EINVAL;
    ctx->region = region;
    ctx->region_size = region_size;
    ctx->publishes = 0;
    ctx->successful_reads = 0;
    ctx->eagain_reads = 0;
    ctx->retries = 0;
    memset(region, 0, sizeof(dblbuf_region_t));
    return 0;
}

void pub_publish(pub_ctx_t *ctx, const witness_record_t *src) {
    dblbuf_region_t *r = (dblbuf_region_t *)ctx->region;
    uint64_t g = atomic_load_explicit(&r->hdr.published_gen, memory_order_relaxed);
    uint64_t g_next = g + 1u;
    uint32_t slot = (uint32_t)(g_next & 1u);
    memcpy(&r->slots[slot], src, sizeof(witness_record_t));
    atomic_store_explicit(&r->hdr.published_gen, g_next, memory_order_release);
    ctx->publishes++;
}

int pub_read_snapshot(pub_ctx_t *ctx, witness_record_t *dst) {
    dblbuf_region_t *r = (dblbuf_region_t *)ctx->region;

    for (int attempt = 0; attempt < DBLBUF_MAX_RETRIES; attempt++) {
        uint64_t g0 = atomic_load_explicit(&r->hdr.published_gen, memory_order_acquire);
        uint32_t slot = (uint32_t)(g0 & 1u);
        memcpy(dst, &r->slots[slot], sizeof(witness_record_t));
        atomic_thread_fence(memory_order_acquire);
        uint64_t g1 = atomic_load_explicit(&r->hdr.published_gen, memory_order_acquire);

        /* If the producer advanced by at most 1 during our copy, it
         * wrote the *other* slot and our slot is quiescent. Only a
         * 2-advance means the producer lapped back onto our slot. */
        if (g1 - g0 < 2u) {
            ctx->successful_reads++;
            return 0;
        }
        ctx->retries++;
    }

    ctx->eagain_reads++;
    return PUB_EAGAIN;
}

const char *pub_protocol_name(void) { return "dblbuf"; }

void pub_set_dma_period_ns(uint64_t period_ns) { (void)period_ns; }

void pub_stats_snapshot(const pub_ctx_t *ctx, pub_stats_t *out) {
    out->publishes        = ctx->publishes;
    out->successful_reads = ctx->successful_reads;
    out->eagain_reads     = ctx->eagain_reads;
    out->retries          = ctx->retries;
}
