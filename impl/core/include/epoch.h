#ifndef EPOCH_H
#define EPOCH_H

#include <stdbool.h>
#include <stdint.h>

static inline bool epoch_is_even(uint64_t e) { return (e & 1ull) == 0; }
static inline bool epoch_is_odd (uint64_t e) { return (e & 1ull) != 0; }
static inline uint64_t epoch_next_even(uint64_t e) { return e + 2ull; }

static inline bool epoch_monotone(uint64_t prev, uint64_t next) {
    return next > prev;
}

#endif
