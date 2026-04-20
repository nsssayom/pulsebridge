#ifndef PROTOTYPE_WORKLOAD_H
#define PROTOTYPE_WORKLOAD_H

#include <stddef.h>
#include <stdint.h>

#include "witness_record.h"

typedef struct {
    float duty_a;
    float duty_b;
    float duty_c;
} evidence_sample_t;

typedef struct workload {
    witness_record_t  *witness;
    evidence_sample_t *evidence;
    size_t             count;
    uint32_t           period_ns;
    uint32_t           config_id;
} workload_t;

int  workload_load(workload_t *wl, const char *dir);
void workload_free(workload_t *wl);

#endif
