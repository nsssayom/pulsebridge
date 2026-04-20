#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "workload.h"
#include "witness_record.h"

#define LINE_MAX_LEN 512

static int parse_witness_line(const char *line, witness_record_t *w) {
    uint64_t epoch;
    uint64_t ts_ns;
    float    a, b, c;
    uint32_t cfg;
    int n = sscanf(line, "%llu,%llu,%f,%f,%f,%u",
                   (unsigned long long *)&epoch,
                   (unsigned long long *)&ts_ns,
                   &a, &b, &c, &cfg);
    if (n != 6) return -1;
    w->epoch     = epoch;
    w->ts_ns     = ts_ns;
    w->duty_a    = a;
    w->duty_b    = b;
    w->duty_c    = c;
    w->config_id = cfg;
    memset(w->mac, 0, sizeof(w->mac));
    w->reserved  = 0;
    return 0;
}

static int parse_evidence_line(const char *line, evidence_sample_t *e,
                               uint64_t *epoch, uint64_t *ts_ns) {
    float a, b, c;
    int n = sscanf(line, "%llu,%llu,%f,%f,%f",
                   (unsigned long long *)epoch,
                   (unsigned long long *)ts_ns,
                   &a, &b, &c);
    if (n != 5) return -1;
    e->duty_a = a;
    e->duty_b = b;
    e->duty_c = c;
    return 0;
}

static size_t count_data_lines(FILE *f) {
    size_t n = 0;
    char buf[LINE_MAX_LEN];
    if (!fgets(buf, sizeof(buf), f)) return 0;
    while (fgets(buf, sizeof(buf), f)) {
        if (buf[0] != '\0' && buf[0] != '\n') n++;
    }
    rewind(f);
    return n;
}

static int load_witness(const char *path, witness_record_t *out, size_t cap) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char buf[LINE_MAX_LEN];
    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return -1; }  /* header */
    size_t i = 0;
    while (i < cap && fgets(buf, sizeof(buf), f)) {
        if (parse_witness_line(buf, &out[i]) != 0) { fclose(f); return -1; }
        i++;
    }
    fclose(f);
    return (int)i;
}

static int load_evidence(const char *path, evidence_sample_t *out,
                         uint64_t *epoch_first, uint64_t *ts_first, size_t cap) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char buf[LINE_MAX_LEN];
    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return -1; }
    size_t i = 0;
    uint64_t epoch, ts_ns;
    while (i < cap && fgets(buf, sizeof(buf), f)) {
        if (parse_evidence_line(buf, &out[i], &epoch, &ts_ns) != 0) {
            fclose(f); return -1;
        }
        if (i == 0) { *epoch_first = epoch; *ts_first = ts_ns; }
        i++;
    }
    fclose(f);
    return (int)i;
}

int workload_load(workload_t *wl, const char *dir) {
    if (!wl || !dir) return -1;
    memset(wl, 0, sizeof(*wl));

    char wpath[512], epath[512];
    snprintf(wpath, sizeof(wpath), "%s/witness.csv", dir);
    snprintf(epath, sizeof(epath), "%s/evidence.csv", dir);

    FILE *fw = fopen(wpath, "r");
    if (!fw) { fprintf(stderr, "workload: open %s: %s\n", wpath, strerror(errno)); return -1; }
    size_t n = count_data_lines(fw);
    fclose(fw);
    if (n == 0) { fprintf(stderr, "workload: %s is empty\n", wpath); return -1; }

    wl->witness  = aligned_alloc(64, n * sizeof(witness_record_t));
    wl->evidence = malloc(n * sizeof(evidence_sample_t));
    if (!wl->witness || !wl->evidence) {
        workload_free(wl);
        return -1;
    }

    int wn = load_witness(wpath, wl->witness, n);
    if (wn < 0 || (size_t)wn != n) {
        fprintf(stderr, "workload: parse witness failed\n");
        workload_free(wl);
        return -1;
    }

    uint64_t e0_epoch = 0, e0_ts = 0;
    int en = load_evidence(epath, wl->evidence, &e0_epoch, &e0_ts, n);
    if (en < 0 || (size_t)en != n) {
        fprintf(stderr, "workload: parse evidence failed\n");
        workload_free(wl);
        return -1;
    }

    if (wl->witness[0].epoch != e0_epoch) {
        fprintf(stderr, "workload: first-epoch mismatch %llu vs %llu\n",
                (unsigned long long)wl->witness[0].epoch,
                (unsigned long long)e0_epoch);
        workload_free(wl);
        return -1;
    }

    wl->count     = n;
    wl->config_id = wl->witness[0].config_id;
    if (n >= 2) {
        uint64_t dts = wl->witness[1].ts_ns - wl->witness[0].ts_ns;
        wl->period_ns = (uint32_t)dts;
    } else {
        wl->period_ns = 100000;
    }

    for (size_t i = 0; i < n; i++) {
        wr_set_epoch_tag(&wl->witness[i], (uint16_t)(wl->witness[i].epoch & 0xFFFFu));
    }

    return 0;
}

void workload_free(workload_t *wl) {
    if (!wl) return;
    free(wl->witness);
    free(wl->evidence);
    wl->witness = NULL;
    wl->evidence = NULL;
    wl->count = 0;
}
