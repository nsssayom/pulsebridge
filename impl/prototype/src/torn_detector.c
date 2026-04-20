#include "harness.h"
#include "witness_record.h"

int torn_is_torn(const witness_record_t *r) {
    uint16_t stored = wr_epoch_tag(r);
    uint16_t want   = (uint16_t)(r->epoch & 0xFFFFu);
    return stored != want;
}
