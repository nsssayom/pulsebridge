#ifndef RESIDUAL_H
#define RESIDUAL_H

#include <stdint.h>

#include "witness_record.h"

typedef struct realized_sample {
    uint64_t epoch;
    float    duty_a;
    float    duty_b;
    float    duty_c;
} realized_sample_t;

typedef struct residual_cfg {
    float bias_a;
    float bias_b;
    float bias_c;
    float epsilon;
} residual_cfg_t;

typedef struct residual_out {
    float max_abs;
    int   alarm;
} residual_out_t;

void residual_compute(
    const witness_record_t  *witness,
    const realized_sample_t *evidence,
    const residual_cfg_t    *cfg,
    residual_out_t          *out);

#endif
