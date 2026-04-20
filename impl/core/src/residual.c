#include <math.h>

#include "residual.h"

void residual_compute(
    const witness_record_t  *witness,
    const realized_sample_t *evidence,
    const residual_cfg_t    *cfg,
    residual_out_t          *out)
{
    float ra = fabsf(evidence->duty_a - witness->duty_a - cfg->bias_a);
    float rb = fabsf(evidence->duty_b - witness->duty_b - cfg->bias_b);
    float rc = fabsf(evidence->duty_c - witness->duty_c - cfg->bias_c);
    float m = ra;
    if (rb > m) m = rb;
    if (rc > m) m = rc;
    out->max_abs = m;
    out->alarm = (m > cfg->epsilon) ? 1 : 0;
}
