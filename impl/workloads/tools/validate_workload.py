#!/usr/bin/env python3
"""Validate an aligned workload directory against the schema invariants.

Usage: validate_workload.py <dir>
  where <dir> contains witness.csv, evidence.csv, PROVENANCE
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def fail(msg: str) -> "never":
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_workload.py <dir>", file=sys.stderr)
        return 2
    d = Path(sys.argv[1])
    w_path = d / "witness.csv"
    e_path = d / "evidence.csv"
    p_path = d / "PROVENANCE"
    for p in (w_path, e_path, p_path):
        if not p.exists():
            fail(f"missing {p}")

    witness = list(csv.DictReader(w_path.open()))
    evidence = list(csv.DictReader(e_path.open()))

    if len(witness) != len(evidence):
        fail(f"row count mismatch witness={len(witness)} evidence={len(evidence)}")
    if len(witness) < 10:
        fail(f"too few rows: {len(witness)}")

    want_w = {"epoch", "ts_ns", "duty_a", "duty_b", "duty_c", "config_id"}
    want_e = {"epoch", "ts_ns", "duty_a", "duty_b", "duty_c"}
    if set(witness[0].keys()) != want_w:
        fail(f"witness columns: {set(witness[0].keys())} != {want_w}")
    if set(evidence[0].keys()) != want_e:
        fail(f"evidence columns: {set(evidence[0].keys())} != {want_e}")

    prev_epoch = -1
    for i, (w, e) in enumerate(zip(witness, evidence)):
        we = int(w["epoch"])
        ee = int(e["epoch"])
        if we != ee:
            fail(f"row {i}: epoch mismatch witness={we} evidence={ee}")
        if we & 1:
            fail(f"row {i}: epoch {we} is odd (must be even)")
        if we <= prev_epoch:
            fail(f"row {i}: epoch {we} not monotone (prev {prev_epoch})")
        prev_epoch = we
        for k in ("duty_a", "duty_b", "duty_c"):
            for src, label in ((w, "witness"), (e, "evidence")):
                v = float(src[k])
                if not (0.0 <= v <= 1.0):
                    fail(f"row {i}: {label}.{k}={v} out of [0,1]")

    print(f"OK: {len(witness)} periods, first epoch {witness[0]['epoch']}, "
          f"last epoch {witness[-1]['epoch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
