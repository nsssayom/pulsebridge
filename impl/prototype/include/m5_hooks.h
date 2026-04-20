#ifndef GEM5_BENCH_M5_HOOKS_H
#define GEM5_BENCH_M5_HOOKS_H

/* Wrappers around gem5 m5ops. When GEM5_M5OPS is defined, these call the
 * real pseudo-instructions; otherwise they compile to no-ops so the same
 * source can be built and exercised on the host for debugging. The gem5
 * Makefile links against the static m5op library. */

#ifdef GEM5_M5OPS
#include <gem5/m5ops.h>

static inline void bench_reset_stats(void)   { m5_reset_stats(0, 0); }
static inline void bench_dump_stats(void)    { m5_dump_stats(0, 0); }
static inline void bench_work_begin(int id)  { m5_work_begin(id, 0); }
static inline void bench_work_end(int id)    { m5_work_end(id, 0); }
static inline void bench_exit_clean(void)    { m5_exit(0); }
#else
static inline void bench_reset_stats(void)   { }
static inline void bench_dump_stats(void)    { }
static inline void bench_work_begin(int id)  { (void)id; }
static inline void bench_work_end(int id)    { (void)id; }
static inline void bench_exit_clean(void)    { }
#endif

#define ROI_ID_PRODUCER 1
#define ROI_ID_MONITOR  2
#define ROI_ID_END_TO_END 3

#endif
