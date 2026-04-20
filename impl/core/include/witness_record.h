#ifndef WITNESS_RECORD_H
#define WITNESS_RECORD_H

#include <stdalign.h>
#include <stddef.h>
#include <stdint.h>

#define WITNESS_RECORD_VERSION 1u
#define WITNESS_RECORD_SIZE    48u

#define WITNESS_CACHELINE      64u

typedef struct witness_record {
    alignas(WITNESS_CACHELINE) uint64_t epoch;
    uint64_t ts_ns;
    float    duty_a;
    float    duty_b;
    float    duty_c;
    uint32_t config_id;
    uint8_t  mac[8];
    uint64_t reserved;
} witness_record_t;

_Static_assert(sizeof(witness_record_t) == 64,
    "witness_record_t pads to 64 B under cacheline alignment");

_Static_assert(offsetof(witness_record_t, epoch)     == 0,  "epoch offset");
_Static_assert(offsetof(witness_record_t, ts_ns)     == 8,  "ts_ns offset");
_Static_assert(offsetof(witness_record_t, duty_a)    == 16, "duty_a offset");
_Static_assert(offsetof(witness_record_t, duty_b)    == 20, "duty_b offset");
_Static_assert(offsetof(witness_record_t, duty_c)    == 24, "duty_c offset");
_Static_assert(offsetof(witness_record_t, config_id) == 28, "config_id offset");
_Static_assert(offsetof(witness_record_t, mac)       == 32, "mac offset");
_Static_assert(offsetof(witness_record_t, reserved)  == 40, "reserved offset");

static inline uint16_t wr_epoch_tag(const witness_record_t *r) {
    return (uint16_t)(r->config_id & 0xFFFFu);
}

static inline void wr_set_epoch_tag(witness_record_t *r, uint16_t tag) {
    r->config_id = (r->config_id & 0xFFFF0000u) | (uint32_t)tag;
}

#endif
