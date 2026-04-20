#ifndef PROTOTYPE_HARNESS_H
#define PROTOTYPE_HARNESS_H

#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>

#include "publication.h"
#include "witness_record.h"
#include "workload.h"

typedef struct {
    uint64_t torn_reads;
    uint64_t residual_alarms;
    uint64_t stl_violations;
    uint64_t samples_consumed;
    uint64_t reads_attempted;
    uint64_t reads_eagain;
} monitor_stats_t;

typedef struct {
    const workload_t *wl;
    pub_ctx_t        *pub;
    atomic_int       *done;
    uint64_t          pacing_ns;
} producer_args_t;

typedef struct {
    const workload_t *wl;
    pub_ctx_t        *pub;
    atomic_int       *done;
    monitor_stats_t  *stats;
    float             epsilon;
    size_t            stl_window;
} monitor_args_t;

void *producer_thread(void *arg);
void *monitor_thread(void *arg);

int torn_is_torn(const witness_record_t *r);

#endif
