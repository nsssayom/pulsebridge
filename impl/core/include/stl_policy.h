#ifndef STL_POLICY_H
#define STL_POLICY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define STL_MAX_WINDOW  2048u

typedef struct stl_cfg {
    float  epsilon;
    size_t window;
} stl_cfg_t;

typedef struct stl_state {
    stl_cfg_t cfg;
    float     window_buf[STL_MAX_WINDOW];
    size_t    head;
    size_t    filled;
} stl_state_t;

int  stl_init(stl_state_t *st, const stl_cfg_t *cfg);
bool stl_step(stl_state_t *st, float residual_abs);

#endif
