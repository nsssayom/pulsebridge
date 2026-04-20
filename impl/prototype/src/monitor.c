#include <stdio.h>

#include "harness.h"
#include "m5_hooks.h"
#include "publication.h"
#include "residual.h"
#include "stl_policy.h"

void *monitor_thread(void *arg) {
    monitor_args_t *a = (monitor_args_t *)arg;
    const workload_t *wl = a->wl;

    residual_cfg_t rcfg = {
        .bias_a = 0.0f, .bias_b = 0.0f, .bias_c = 0.0f,
        .epsilon = a->epsilon,
    };
    stl_cfg_t scfg = { .window = a->stl_window, .epsilon = a->epsilon };
    stl_state_t stl;
    stl_init(&stl, &scfg);

    witness_record_t snap;
    size_t evidence_idx = 0;
    uint64_t last_epoch_consumed = 0;

    bench_work_begin(ROI_ID_MONITOR);

    while (atomic_load_explicit(a->done, memory_order_acquire) == 0 ||
           evidence_idx < wl->count) {
        a->stats->reads_attempted++;
        int rc = pub_read_snapshot(a->pub, &snap);
        if (rc == PUB_EAGAIN) {
            a->stats->reads_eagain++;
            continue;
        }

        if (torn_is_torn(&snap)) {
            a->stats->torn_reads++;
        }

        if (snap.epoch == 0 || snap.epoch == last_epoch_consumed) {
            continue;
        }
        last_epoch_consumed = snap.epoch;

        while (evidence_idx < wl->count &&
               wl->witness[evidence_idx].epoch < snap.epoch) {
            evidence_idx++;
        }
        if (evidence_idx >= wl->count) break;
        if (wl->witness[evidence_idx].epoch != snap.epoch) {
            continue;
        }

        realized_sample_t ev = {
            .duty_a = wl->evidence[evidence_idx].duty_a,
            .duty_b = wl->evidence[evidence_idx].duty_b,
            .duty_c = wl->evidence[evidence_idx].duty_c,
        };
        residual_out_t rout;
        residual_compute(&snap, &ev, &rcfg, &rout);
        if (rout.alarm) a->stats->residual_alarms++;

        bool ok = stl_step(&stl, rout.max_abs);
        if (!ok) a->stats->stl_violations++;

        a->stats->samples_consumed++;
        evidence_idx++;
    }

    bench_work_end(ROI_ID_MONITOR);
    return NULL;
}
