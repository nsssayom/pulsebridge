#ifndef PUBLICATION_H
#define PUBLICATION_H

#include <stddef.h>
#include <stdint.h>

#include "witness_record.h"

#define PUB_EAGAIN  (-11)
#define PUB_EINVAL  (-22)

#define PUB_MIN_REGION_BYTES   256u

typedef struct pub_ctx pub_ctx_t;

int  pub_init(pub_ctx_t *ctx, void *region, size_t region_size);
void pub_publish(pub_ctx_t *ctx, const witness_record_t *src);
int  pub_read_snapshot(pub_ctx_t *ctx, witness_record_t *dst);

const char *pub_protocol_name(void);

/* Configure the DMA-pull engine's tick period. Must be called before
 * pub_init() to take effect. No-op for non-DMA protocols. */
void pub_set_dma_period_ns(uint64_t period_ns);

typedef struct pub_stats {
    uint64_t publishes;
    uint64_t successful_reads;
    uint64_t eagain_reads;
    uint64_t retries;
} pub_stats_t;

void pub_stats_snapshot(const pub_ctx_t *ctx, pub_stats_t *out);

struct pub_ctx {
    void    *region;
    size_t   region_size;
    uint64_t publishes;
    uint64_t successful_reads;
    uint64_t eagain_reads;
    uint64_t retries;
};

#endif
