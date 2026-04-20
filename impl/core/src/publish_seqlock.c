#include <stdatomic.h>
#include <string.h>

#include "publication.h"

#define SEQLOCK_MAX_RETRIES 8

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
    if (!ctx || !region || region_size < WITNESS_CACHELINE) return PUB_EINVAL;
    if (((uintptr_t)region & (WITNESS_CACHELINE - 1)) != 0) return PUB_EINVAL;
    ctx->region = region;
    ctx->region_size = region_size;
    ctx->publishes = 0;
    ctx->successful_reads = 0;
    ctx->eagain_reads = 0;
    ctx->retries = 0;
    memset(region, 0, WITNESS_CACHELINE);
    return 0;
}

void pub_publish(pub_ctx_t *ctx, const witness_record_t *src) {
    seqlock_region_t *r = (seqlock_region_t *)ctx->region;

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
    seqlock_region_t *r = (seqlock_region_t *)ctx->region;

    for (int attempt = 0; attempt < SEQLOCK_MAX_RETRIES; attempt++) {
        uint64_t e_before = atomic_load_explicit(&r->epoch, memory_order_acquire);
        if (e_before & 1ull) {
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
        ctx->retries++;
    }

    ctx->eagain_reads++;
    return PUB_EAGAIN;
}

const char *pub_protocol_name(void) { return "seqlock"; }

void pub_set_dma_period_ns(uint64_t period_ns) { (void)period_ns; }

void pub_stats_snapshot(const pub_ctx_t *ctx, pub_stats_t *out) {
    out->publishes        = ctx->publishes;
    out->successful_reads = ctx->successful_reads;
    out->eagain_reads     = ctx->eagain_reads;
    out->retries          = ctx->retries;
}
