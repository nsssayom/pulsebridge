#!/usr/bin/env python3
"""Convert an STM32 per-period CSV into aligned witness/evidence CSVs.

Input: `impl/workloads/captured/source/verified_per_period.csv`
  columns: t_s, period_s_ch0, high_s_ch0, duty_ch0,
           period_s_ch1, high_s_ch1, duty_ch1, ...

Output per variant directory:
  witness.csv    (intended duties, constant nominal on all three phases)
  evidence.csv   (realized duties: ch0 -> A, ch1 -> B, C synthesized)
  PROVENANCE

The captured trace is 2-channel (STM32 BLDC configuration, 50 us period).
Phase C is not captured; we fill it with the nominal (median ch0 steady-state
duty) so downstream code can consume a 3-phase schema. This synthesis is
explicit and recorded in PROVENANCE.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import statistics
import sys
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, type=Path,
                    help="path to verified_per_period.csv")
    ap.add_argument("--out", required=True, type=Path,
                    help="output directory (captured/<variant>/)")
    ap.add_argument("--config-id", type=int, default=0x1,
                    help="config_id value to embed in witness rows")
    ap.add_argument("--max-periods", type=int, default=0,
                    help="cap on number of periods (0 = all)")
    ap.add_argument("--period-ns", type=int, default=50_000,
                    help="declared period in ns (50 us for BLDC capture)")
    args = ap.parse_args()

    src: Path = args.input
    dst: Path = args.out
    dst.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"error: input not found: {src}", file=sys.stderr)
        return 2

    rows: list[tuple[float, float, float]] = []  # (t_s, duty_ch0, duty_ch1)
    with src.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                t_s = float(r["t_s"])
                d0 = float(r["duty_ch0"])
                d1 = float(r["duty_ch1"])
            except (KeyError, ValueError):
                continue
            if not (0.0 <= d0 <= 1.0 and 0.0 <= d1 <= 1.0):
                continue
            rows.append((t_s, d0, d1))

    if args.max_periods > 0:
        rows = rows[: args.max_periods]
    if len(rows) < 10:
        print(f"error: too few valid rows ({len(rows)})", file=sys.stderr)
        return 3

    nominal = statistics.median([d0 for _, d0, _ in rows])
    period_ns = int(args.period_ns)

    witness_path = dst / "witness.csv"
    evidence_path = dst / "evidence.csv"

    with witness_path.open("w", newline="") as fw, \
         evidence_path.open("w", newline="") as fe:
        ww = csv.writer(fw)
        we = csv.writer(fe)
        ww.writerow(["epoch", "ts_ns", "duty_a", "duty_b", "duty_c", "config_id"])
        we.writerow(["epoch", "ts_ns", "duty_a", "duty_b", "duty_c"])
        for i, (_, d0, d1) in enumerate(rows):
            epoch = 2 * (i + 1)  # even, monotone
            ts_ns = i * period_ns
            ww.writerow([epoch, ts_ns,
                         f"{nominal:.6f}", f"{nominal:.6f}", f"{nominal:.6f}",
                         args.config_id])
            we.writerow([epoch, ts_ns,
                         f"{d0:.6f}", f"{d1:.6f}", f"{nominal:.6f}"])

    input_sha = sha256_file(src)
    witness_sha = sha256_file(witness_path)
    evidence_sha = sha256_file(evidence_path)

    prov = dst / "PROVENANCE"
    prov.write_text(
        f"""variant: captured/periodic_suppression
kind: CAPTURED
generated_at: {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
generator: impl/workloads/tools/convert_digital_csv.py
source: {src.as_posix()}
source_sha256: {input_sha}
source_format: STM32 logic-analyzer per-period CSV (2 channels)
channel_mapping:
  duty_a <- captured duty_ch0
  duty_b <- captured duty_ch1
  duty_c <- SYNTHESIZED constant = median(duty_ch0) = {nominal:.6f}
  (phase C was not captured by the 2-channel logic analyzer)
witness_model: intended duty held at median(duty_ch0) for all three phases
period_ns: {period_ns}
periods: {len(rows)}
duration_s: {len(rows) * period_ns / 1e9:.6f}
config_id: {args.config_id}
witness_sha256: {witness_sha}
evidence_sha256: {evidence_sha}
"""
    )
    print(f"wrote {len(rows)} periods to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
