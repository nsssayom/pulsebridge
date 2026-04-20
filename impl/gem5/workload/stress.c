/*
 * Cache-thrashing stressor for the Phase 4 contention study.
 *
 * One instance runs per stressor CPU in gem5. Each walks a large
 * footprint at a configurable stride and touches every line, generating
 * L1/L2 evictions and coherence traffic that competes with the witness
 * region accessed by the producer/monitor cores.
 *
 * The loop never exits — gem5 terminates the simulation when the main
 * benchmark returns. Writes are store-only (no reads before write) so
 * the access pattern is dominated by RFO upgrades on the L1, which is
 * the kind of traffic we want to stress.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "m5_hooks.h"

#ifndef STRESS_DEFAULT_BYTES
#define STRESS_DEFAULT_BYTES (4u * 1024u * 1024u)
#endif

#ifndef STRESS_STRIDE
#define STRESS_STRIDE 64u
#endif

int main(int argc, char **argv) {
    size_t bytes  = STRESS_DEFAULT_BYTES;
    size_t stride = STRESS_STRIDE;
    if (argc > 1) bytes  = (size_t)strtoull(argv[1], NULL, 10);
    if (argc > 2) stride = (size_t)strtoull(argv[2], NULL, 10);
    if (bytes < stride) bytes = stride;

    volatile uint8_t *buf = aligned_alloc(64, bytes);
    if (!buf) {
        fprintf(stderr, "stressor: aligned_alloc(%zu) failed\n", bytes);
        return 1;
    }
    memset((void *)buf, 0, bytes);

    bench_work_begin(9);
    uint64_t tick = 0;
    for (;;) {
        for (size_t i = 0; i < bytes; i += stride) {
            buf[i] = (uint8_t)(buf[i] + 1);
        }
        tick++;
        if ((tick & 0xFFFF) == 0) {
            __asm__ __volatile__("" ::: "memory");
        }
    }
    /* unreachable */
    bench_work_end(9);
    return 0;
}
