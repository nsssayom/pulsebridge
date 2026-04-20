#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "harness.h"
#include "m5_hooks.h"
#include "publication.h"
#include "workload.h"

#define SHARED_REGION_BYTES 4096u

typedef struct {
    const char *workload_dir;
    uint64_t    pacing_ns;
    uint64_t    dma_period_ns;
    float       epsilon;
    size_t      stl_window;
    int         verbose;
} options_t;

static void usage(const char *argv0) {
    fprintf(stderr,
        "usage: %s --workload DIR [--pacing-ns N] [--epsilon F] [--stl-window N] [-v]\n"
        "  DIR must contain witness.csv, evidence.csv, PROVENANCE\n"
        "  linked protocol: %s\n",
        argv0, pub_protocol_name());
}

static int parse_args(int argc, char **argv, options_t *o) {
    o->workload_dir   = NULL;
    o->pacing_ns      = 0;
    o->dma_period_ns  = 1000;
    o->epsilon        = 0.10f;
    o->stl_window     = 8;
    o->verbose        = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--workload") == 0 && i + 1 < argc) {
            o->workload_dir = argv[++i];
        } else if (strcmp(argv[i], "--pacing-ns") == 0 && i + 1 < argc) {
            o->pacing_ns = strtoull(argv[++i], NULL, 10);
        } else if (strcmp(argv[i], "--dma-period-ns") == 0 && i + 1 < argc) {
            o->dma_period_ns = strtoull(argv[++i], NULL, 10);
        } else if (strcmp(argv[i], "--epsilon") == 0 && i + 1 < argc) {
            o->epsilon = strtof(argv[++i], NULL);
        } else if (strcmp(argv[i], "--stl-window") == 0 && i + 1 < argc) {
            o->stl_window = (size_t)strtoul(argv[++i], NULL, 10);
        } else if (strcmp(argv[i], "-v") == 0) {
            o->verbose = 1;
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 1;
        } else {
            fprintf(stderr, "unknown arg: %s\n", argv[i]);
            return -1;
        }
    }
    if (!o->workload_dir) { usage(argv[0]); return -1; }
    return 0;
}

static uint64_t now_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}

int main(int argc, char **argv) {
    options_t opt;
    int rc = parse_args(argc, argv, &opt);
    if (rc != 0) return rc == 1 ? 0 : 2;

    workload_t wl;
    if (workload_load(&wl, opt.workload_dir) != 0) {
        fprintf(stderr, "failed to load workload from %s\n", opt.workload_dir);
        return 3;
    }

    void *region = aligned_alloc(64, SHARED_REGION_BYTES);
    if (!region) { workload_free(&wl); return 4; }
    memset(region, 0, SHARED_REGION_BYTES);

    pub_set_dma_period_ns(opt.dma_period_ns);

    pub_ctx_t ctx;
    if (pub_init(&ctx, region, SHARED_REGION_BYTES) != 0) {
        fprintf(stderr, "pub_init failed\n");
        free(region); workload_free(&wl); return 5;
    }

    monitor_stats_t stats = {0};
    atomic_int done;
    atomic_init(&done, 0);

    producer_args_t pa = { .wl = &wl, .pub = &ctx, .done = &done, .pacing_ns = opt.pacing_ns };
    monitor_args_t  ma = { .wl = &wl, .pub = &ctx, .done = &done, .stats = &stats,
                           .epsilon = opt.epsilon, .stl_window = opt.stl_window };

    bench_reset_stats();
    bench_work_begin(ROI_ID_END_TO_END);
    uint64_t t0 = now_ns();

    pthread_t p_thr, m_thr;
    if (pthread_create(&p_thr, NULL, producer_thread, &pa) != 0) {
        fprintf(stderr, "pthread_create producer: %s\n", strerror(errno));
        free(region); workload_free(&wl); return 6;
    }
    if (pthread_create(&m_thr, NULL, monitor_thread, &ma) != 0) {
        fprintf(stderr, "pthread_create monitor: %s\n", strerror(errno));
        pthread_join(p_thr, NULL);
        free(region); workload_free(&wl); return 7;
    }
    pthread_join(p_thr, NULL);
    pthread_join(m_thr, NULL);

    uint64_t dt_ns = now_ns() - t0;
    bench_work_end(ROI_ID_END_TO_END);
    bench_dump_stats();

    pub_stats_t ps;
    pub_stats_snapshot(&ctx, &ps);

    printf("protocol=%s\n", pub_protocol_name());
    printf("workload=%s\n", opt.workload_dir);
    printf("periods=%zu period_ns=%u config_id=%u\n",
           wl.count, wl.period_ns, wl.config_id);
    printf("wallclock_ns=%llu\n", (unsigned long long)dt_ns);
    printf("pub.publishes=%llu pub.reads=%llu pub.eagain=%llu pub.retries=%llu\n",
           (unsigned long long)ps.publishes,
           (unsigned long long)ps.successful_reads,
           (unsigned long long)ps.eagain_reads,
           (unsigned long long)ps.retries);
    printf("mon.reads_attempted=%llu mon.reads_eagain=%llu mon.samples_consumed=%llu\n",
           (unsigned long long)stats.reads_attempted,
           (unsigned long long)stats.reads_eagain,
           (unsigned long long)stats.samples_consumed);
    printf("mon.torn_reads=%llu mon.residual_alarms=%llu mon.stl_violations=%llu\n",
           (unsigned long long)stats.torn_reads,
           (unsigned long long)stats.residual_alarms,
           (unsigned long long)stats.stl_violations);

    free(region);
    workload_free(&wl);
    /* Flush before m5_exit — stdout is fully buffered when redirected to
     * gem5.stdout, and m5_exit kills the sim before libc drains the buffer. */
    fflush(stdout);
    /* Force gem5 to exit immediately. Without this, stressor processes
     * (infinite loops on extra CPUs) keep the simulation alive long after
     * the bench's ROI and teardown are done. */
    bench_exit_clean();
    return 0;
}
