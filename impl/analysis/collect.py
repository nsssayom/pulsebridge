#!/usr/bin/env python3
"""
Collect per-cell metrics from a gem5 matrix sweep into one tidy CSV.

Input: a results directory produced by impl/gem5/scripts/run_matrix.sh,
containing one subdirectory per cell named like

    <protocol>__<workload>__str<N>[__dma<P>ns]

with gem5.stdout, gem5.stderr, and m5out/stats.txt inside each.

Output: <results_dir>/metrics.csv with one row per cell, columns keyed by
RQ relevance (bench correctness counters, ROI duration, CPU cycles,
coherence-traffic totals, and DMA-engine totals when applicable).

Usage:
    python3 collect.py <results_dir>
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path
from typing import Any

# Stat names we want from stats.txt (first dump = ROI window).
# Exact names (no globs) for fast O(1) lookup; globs get a separate pass.
STAT_SCALAR_KEYS = [
    "simSeconds",
    "simTicks",
    "finalTick",
    "simFreq",
    "simInsts",
    "simOps",
    "hostSeconds",
    # DMA-pull engine (only present with --enable-dma-engine):
    "system.witness_pull_engine.ticks",
    "system.witness_pull_engine.pullsCompleted",
    "system.witness_pull_engine.bytesTransferred",
    "system.witness_pull_engine.skippedBusy",
    # DMA controller (only with --enable-dma-engine):
    "system.ruby.dma_cntrl0.requestToDir.m_msg_count",
    "system.ruby.dma_cntrl0.responseFromDir.m_msg_count",
]

# Glob prefixes — we sum across matching keys (for per-core/per-L1 stats).
# MESI_Two_Level naming: l1_cntrlN are the per-core L1 controllers; dir_cntrlN
# owns L2 + memory directory. Cross-level messages flow on requestFromL1Cache
# (L1→Dir/L2) and requestToL1Cache (Dir→L1 invalidations/fetches).
STAT_SUM_PREFIXES = {
    "cpu_numCycles_total": r"^system\.cpu\d+\.numCycles\s",
    "l1_request_from_msgs_total":
        r"^system\.ruby\.l1_cntrl\d+\.requestFromL1Cache\.m_msg_count\s",
    "l1_request_to_msgs_total":
        r"^system\.ruby\.l1_cntrl\d+\.requestToL1Cache\.m_msg_count\s",
    "l1_response_from_msgs_total":
        r"^system\.ruby\.l1_cntrl\d+\.responseFromL1Cache\.m_msg_count\s",
    "l1_response_to_msgs_total":
        r"^system\.ruby\.l1_cntrl\d+\.responseToL1Cache\.m_msg_count\s",
    "dir_request_to_msgs_total":
        r"^system\.ruby\.dir_cntrl\d+\.requestToDir\.m_msg_count\s",
    "dir_response_from_msgs_total":
        r"^system\.ruby\.dir_cntrl\d+\.responseFromDir\.m_msg_count\s",
    "dir_memory_request_msgs_total":
        r"^system\.ruby\.dir_cntrl\d+\.requestToMemory\.m_msg_count\s",
}

# Cell name pattern: proto__workload__strN[__dmaPns]. Workload segments
# that originally contained slashes were flattened with `-` by run_matrix.
# Proto names include an underscore for the dma_naive / dma_seqlock
# variants, so we can't use [a-z]+ — match any sequence of [a-z_] that is
# followed by the `__` delimiter.
CELL_RE = re.compile(
    r"^(?P<proto>[a-z][a-z_]*?)__(?P<workload>[A-Za-z0-9\-_]+)__str(?P<stressors>\d+)"
    r"(?:__dma(?P<dma_period_ns>\d+)ns)?$"
)

# Bench stdout key=value lines we care about. We deliberately skip the
# `workload=` line (it holds a host path that would overwrite the clean
# workload field we already decoded from the cell name) and the `protocol=`
# line (same reason — decoded cell value is canonical).
BENCH_KV_RE = re.compile(r"^(wallclock_ns)\s*=\s*(\S+)")
BENCH_MULTI_RE = re.compile(r"^(periods|period_ns|config_id|pub\.\w+|mon\.\w+)\s*=\s*(\S+)")


def parse_stats_first_dump(path: Path) -> dict[str, float]:
    """Extract scalars (and summed families) from the first dump of stats.txt.

    The first dump is the ROI window: it contains only stats accumulated
    since `m5_reset_stats` was called in the bench. Subsequent dumps include
    post-ROI teardown activity and are less clean.
    """
    if not path.is_file():
        return {}
    scalars: dict[str, float] = {}
    sums: dict[str, float] = {k: 0.0 for k in STAT_SUM_PREFIXES}
    sum_patterns = {k: re.compile(rx) for k, rx in STAT_SUM_PREFIXES.items()}

    in_dump = False
    first_end_seen = False
    with path.open() as f:
        for line in f:
            if first_end_seen:
                break
            if line.startswith("---------- Begin Simulation Statistics"):
                in_dump = True
                continue
            if line.startswith("---------- End Simulation Statistics"):
                first_end_seen = True
                continue
            if not in_dump:
                continue
            # Stat line: name<ws>value<ws>[...]
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue
            name, value = parts[0], parts[1]
            if name in STAT_SCALAR_KEYS:
                try:
                    scalars[name] = float(value)
                except ValueError:
                    pass
            for sum_key, pat in sum_patterns.items():
                if pat.match(line):
                    try:
                        sums[sum_key] += float(value)
                    except ValueError:
                        pass
    scalars.update(sums)
    return scalars


def parse_bench_stdout(path: Path) -> dict[str, str]:
    """Extract the key=value and `key=value key=value ...` printfs from main.c."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    with path.open() as f:
        for line in f:
            # Single-kv lines: protocol=dma, workload=..., wallclock_ns=...
            m = BENCH_KV_RE.match(line.strip())
            if m:
                out[m.group(1)] = m.group(2)
                continue
            # Multi-kv lines: "pub.publishes=20000 pub.reads=13327 ..."
            for token in line.strip().split():
                m2 = BENCH_MULTI_RE.match(token)
                if m2:
                    out[m2.group(1)] = m2.group(2)
    return out


def decode_cell_name(name: str) -> dict[str, Any] | None:
    m = CELL_RE.match(name)
    if not m:
        return None
    out = m.groupdict()
    out["stressors"] = int(out["stressors"])
    out["dma_period_ns"] = int(out["dma_period_ns"]) if out["dma_period_ns"] else None
    # Re-expand the workload slash: duty_bias stays, captured-periodic_suppression
    # → captured/periodic_suppression on a best-effort basis using the first `-`.
    wl = out["workload"]
    if "-" in wl and not wl.startswith("-"):
        head, rest = wl.split("-", 1)
        if head in ("captured", "synthesized"):
            out["workload"] = f"{head}/{rest}"
    return out


def derive_metrics(row: dict[str, Any]) -> None:
    """Add derived columns the plotting layer will want."""
    publishes = _to_int(row.get("pub.publishes"))
    sim_seconds = _to_float(row.get("simSeconds"))
    consumed = _to_int(row.get("mon.samples_consumed"))
    torn = _to_int(row.get("mon.torn_reads"))

    # Throughput / cadence
    if publishes and sim_seconds:
        row["publishes_per_sec"] = publishes / sim_seconds
    if consumed and sim_seconds:
        row["consumed_per_sec"] = consumed / sim_seconds

    # Correctness rates (as a fraction of attempted reads)
    attempted = _to_int(row.get("mon.reads_attempted"))
    if attempted:
        row["torn_read_frac"] = torn / attempted
        row["consume_success_frac"] = consumed / attempted

    # Per-direction coherence traffic per publish (keep these for drill-down).
    if publishes:
        for col in ("l1_request_from_msgs_total", "l1_request_to_msgs_total",
                    "l1_response_from_msgs_total", "l1_response_to_msgs_total",
                    "dir_request_to_msgs_total", "dir_response_from_msgs_total",
                    "dir_memory_request_msgs_total",
                    "system.ruby.dma_cntrl0.requestToDir.m_msg_count"):
            v = _to_float(row.get(col))
            if v is not None:
                row[f"{col}__per_publish"] = v / publishes

    # Total coherence traffic — the single RQ1 headline metric. Sum of all
    # cross-level Ruby request+response messages (L1↔Dir both directions,
    # Dir→memory). Excludes DMA-controller traffic so the value is
    # comparable across protocols that do and do not enable the engine.
    coherence_cols = ("l1_request_from_msgs_total", "l1_request_to_msgs_total",
                      "l1_response_from_msgs_total", "l1_response_to_msgs_total",
                      "dir_request_to_msgs_total", "dir_response_from_msgs_total",
                      "dir_memory_request_msgs_total")
    total = 0.0
    any_present = False
    for col in coherence_cols:
        v = _to_float(row.get(col))
        if v is not None:
            total += v
            any_present = True
    if any_present:
        row["coherence_msgs_total"] = total
        if publishes:
            row["coherence_msgs_per_publish"] = total / publishes


def _to_int(x: Any) -> int | None:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def collect(results_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for child in sorted(results_dir.iterdir()):
        if not child.is_dir():
            continue
        decoded = decode_cell_name(child.name)
        if decoded is None:
            continue

        row: dict[str, Any] = {"cell": child.name, **decoded}
        row.update(parse_stats_first_dump(child / "m5out" / "stats.txt"))
        row.update(parse_bench_stdout(child / "gem5.stdout"))
        derive_metrics(row)
        rows.append(row)
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: collect.py <results_dir>", file=sys.stderr)
        return 2
    results_dir = Path(sys.argv[1]).resolve()
    if not results_dir.is_dir():
        print(f"error: not a directory: {results_dir}", file=sys.stderr)
        return 2

    rows = collect(results_dir)
    if not rows:
        print(f"error: no cell subdirectories under {results_dir}", file=sys.stderr)
        return 1

    all_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    out = results_dir / "metrics.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {out} ({len(rows)} cells, {len(all_keys)} columns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
