#!/usr/bin/env python3
"""Generate a synthesized sustained-small-divergence workload.

Produces an aligned witness/evidence CSV pair where the evidence continuously
deviates from the intended duty by a fixed multiplicative bias, following
the CDC paper's `+15%` duty-bias definition. Witness is a balanced three-phase
sinusoidal duty profile around 0.5 midpoint (PMSM-style SVPWM reference).

This workload exercises the consumer's residual noise floor and the long-run
publication stability of the channel under a sustained non-zero residual.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import sys
import time
from pathlib import Path


TWO_PI_OVER_3 = 2.0 * math.pi / 3.0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def clip(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def intended_duty(t_s: float, f_elec_hz: float, amplitude: float, phase: float) -> float:
    """Balanced SPWM reference: 0.5 + amplitude * sin(omega t + phase)."""
    return 0.5 + amplitude * math.sin(2.0 * math.pi * f_elec_hz * t_s + phase)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path,
                    help="output directory (synthesized/<variant>/)")
    ap.add_argument("--periods", type=int, default=20_000,
                    help="number of periods to synthesize")
    ap.add_argument("--period-ns", type=int, default=100_000,
                    help="PWM period (100 us for PMSM-style)")
    ap.add_argument("--bias-pct", type=float, default=15.0,
                    help="multiplicative duty bias in percent (CDC default +15%%)")
    ap.add_argument("--f-elec-hz", type=float, default=20.0,
                    help="electrical frequency of the synthesized reference")
    ap.add_argument("--amplitude", type=float, default=0.3,
                    help="duty reference amplitude around 0.5 midpoint")
    ap.add_argument("--config-id", type=int, default=0x2,
                    help="config_id value to embed in witness rows")
    args = ap.parse_args()

    dst: Path = args.out
    dst.mkdir(parents=True, exist_ok=True)

    bias = 1.0 + args.bias_pct / 100.0
    period_ns = int(args.period_ns)
    period_s = period_ns / 1e9

    witness_path = dst / "witness.csv"
    evidence_path = dst / "evidence.csv"

    with witness_path.open("w", newline="") as fw, \
         evidence_path.open("w", newline="") as fe:
        ww = csv.writer(fw)
        we = csv.writer(fe)
        ww.writerow(["epoch", "ts_ns", "duty_a", "duty_b", "duty_c", "config_id"])
        we.writerow(["epoch", "ts_ns", "duty_a", "duty_b", "duty_c"])
        for i in range(args.periods):
            epoch = 2 * (i + 1)
            ts_ns = i * period_ns
            t_s = i * period_s
            w_a = intended_duty(t_s, args.f_elec_hz, args.amplitude, 0.0)
            w_b = intended_duty(t_s, args.f_elec_hz, args.amplitude, -TWO_PI_OVER_3)
            w_c = intended_duty(t_s, args.f_elec_hz, args.amplitude, +TWO_PI_OVER_3)
            e_a = clip(w_a * bias)
            e_b = clip(w_b * bias)
            e_c = clip(w_c * bias)
            ww.writerow([epoch, ts_ns,
                         f"{w_a:.6f}", f"{w_b:.6f}", f"{w_c:.6f}",
                         args.config_id])
            we.writerow([epoch, ts_ns,
                         f"{e_a:.6f}", f"{e_b:.6f}", f"{e_c:.6f}"])

    witness_sha = sha256_file(witness_path)
    evidence_sha = sha256_file(evidence_path)

    prov = dst / "PROVENANCE"
    prov.write_text(
        f"""variant: synthesized/duty_bias
kind: SYNTHESIZED
generated_at: {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
generator: impl/workloads/tools/synthesize_duty_bias.py
source: none (fully synthesized)
witness_model: 0.5 + {args.amplitude} * sin(2*pi*{args.f_elec_hz} Hz * t + phase)
  phase offsets: A=0, B=-2pi/3, C=+2pi/3
evidence_model: clip(witness * {bias:.4f}, 0, 1)  # CDC +{args.bias_pct}%% duty bias
period_ns: {period_ns}
periods: {args.periods}
duration_s: {args.periods * period_s:.6f}
config_id: {args.config_id}
witness_sha256: {witness_sha}
evidence_sha256: {evidence_sha}
"""
    )
    print(f"wrote {args.periods} periods to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
