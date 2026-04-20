#include <errno.h>
#include <stdio.h>
#include <time.h>

#include "harness.h"
#include "m5_hooks.h"
#include "publication.h"

static void sleep_ns(uint64_t ns) {
    if (ns == 0) return;
    struct timespec req;
    req.tv_sec  = (time_t)(ns / 1000000000ull);
    req.tv_nsec = (long)  (ns % 1000000000ull);
    while (nanosleep(&req, &req) == -1 && errno == EINTR) { }
}

void *producer_thread(void *arg) {
    producer_args_t *a = (producer_args_t *)arg;
    const workload_t *wl = a->wl;

    bench_work_begin(ROI_ID_PRODUCER);
    for (size_t i = 0; i < wl->count; i++) {
        pub_publish(a->pub, &wl->witness[i]);
        if (a->pacing_ns) sleep_ns(a->pacing_ns);
    }
    bench_work_end(ROI_ID_PRODUCER);
    atomic_store_explicit(a->done, 1, memory_order_release);
    return NULL;
}
