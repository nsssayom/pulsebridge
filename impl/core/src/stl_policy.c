#include <string.h>

#include "stl_policy.h"

int stl_init(stl_state_t *st, const stl_cfg_t *cfg) {
    if (!st || !cfg) return -1;
    if (cfg->window == 0 || cfg->window > STL_MAX_WINDOW) return -1;
    memset(st, 0, sizeof(*st));
    st->cfg = *cfg;
    return 0;
}

bool stl_step(stl_state_t *st, float residual_abs) {
    st->window_buf[st->head] = residual_abs;
    st->head = (st->head + 1u) % st->cfg.window;
    if (st->filled < st->cfg.window) st->filled++;

    if (st->filled < st->cfg.window) return true;

    for (size_t i = 0; i < st->cfg.window; i++) {
        if (st->window_buf[i] > st->cfg.epsilon) return false;
    }
    return true;
}
