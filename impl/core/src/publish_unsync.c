#include <stdatomic.h>
#include <string.h>

#include "publication.h"

typedef struct {
    _Atomic uint64_t words[8];
} unsync_region_t;

_Static_assert(sizeof(unsync_region_t) == 64, "unsync region is one cache line");

int pub_init(pub_ctx_t *ctx, void *region, size_t region_size) {
    if (!ctx || !region || region_size < sizeof(unsync_region_t)) return PUB_EINVAL;
    if (((uintptr_t)region & (WITNESS_CACHELINE - 1)) != 0) return PUB_EINVAL;
    ctx->region = region;
    ctx->region_size = region_size;
    ctx->publishes = 0;
    ctx->successful_reads = 0;
    ctx->eagain_reads = 0;
    ctx->retries = 0;
    memset(region, 0, sizeof(unsync_region_t));
    return 0;
}

void pub_publish(pub_ctx_t *ctx, const witness_record_t *src) {
    unsync_region_t *r = (unsync_region_t *)ctx->region;
    uint64_t staging[8];
    memcpy(staging, src, sizeof(staging));
    for (size_t i = 0; i < 8; i++) {
        atomic_store_explicit(&r->words[i], staging[i], memory_order_relaxed);
    }
    ctx->publishes++;
}

int pub_read_snapshot(pub_ctx_t *ctx, witness_record_t *dst) {
    unsync_region_t *r = (unsync_region_t *)ctx->region;
    uint64_t staging[8];
    for (size_t i = 0; i < 8; i++) {
        staging[i] = atomic_load_explicit(&r->words[i], memory_order_relaxed);
    }
    memcpy(dst, staging, sizeof(staging));
    ctx->successful_reads++;
    return 0;
}

const char *pub_protocol_name(void) { return "unsync"; }

void pub_set_dma_period_ns(uint64_t period_ns) { (void)period_ns; }

void pub_stats_snapshot(const pub_ctx_t *ctx, pub_stats_t *out) {
    out->publishes        = ctx->publishes;
    out->successful_reads = ctx->successful_reads;
    out->eagain_reads     = ctx->eagain_reads;
    out->retries          = ctx->retries;
}
