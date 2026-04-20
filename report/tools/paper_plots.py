#!/usr/bin/env python3
"""Generate paper-oriented plots for the report.

This script is intentionally separate from impl/analysis/plot.py. The
analysis script is optimized for exploratory matrices; this one renders a
small set of publication-ready figures with larger typography and a more
compact visual design for the paper.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd


PROTOCOL_ORDER = ["unsync", "dma_naive", "dma_seqlock", "seqlock", "dblbuf"]
CORRECT_ORDER = ["dma_seqlock", "seqlock", "dblbuf"]
CAPTURED = "captured/periodic_suppression"

COLORS = {
    "unsync": "#9E9E9E",
    "dma_naive": "#D55E00",
    "dma_seqlock": "#56B4E9",
    "seqlock": "#0072B2",
    "dblbuf": "#009E73",
}

MARKERS = {
    "unsync": "x",
    "dma_naive": "D",
    "dma_seqlock": "P",
    "seqlock": "o",
    "dblbuf": "^",
}

LABELS = {
    "unsync": "No discipline",
    "dma_naive": "DMA mirror, no discipline",
    "dma_seqlock": "DMA mirror + sequence lock",
    "seqlock": "Sequence lock",
    "dblbuf": "Generation double-buffer",
}

WORKLOAD_LABELS = {
    "captured/periodic_suppression": "Captured sparse-divergence workload",
    "synthesized/duty_bias": "Synthesized sustained-bias workload",
}

plt.rcParams.update({
    "font.size": 16,
    "axes.titlesize": 17,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 13,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})


def _save(fig: plt.Figure, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".png"), dpi=220)
    plt.close(fig)


def _panel_title(letter: str, title: str) -> str:
    return f"({letter}) {title}"


def plot_main_results(df: pd.DataFrame, out_stem: Path) -> None:
    d = df[df["workload"] == CAPTURED].copy()
    if d.empty:
        raise ValueError(f"no rows for workload {CAPTURED}")

    stressors = sorted(d["stressors"].unique().tolist())
    d["roi_ms"] = d["simSeconds"] * 1e3

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 8.8))
    ax_torn, ax_coh, ax_roi, ax_retry = axes.flat

    width = 0.78 / len(PROTOCOL_ORDER)
    for idx, proto in enumerate(PROTOCOL_ORDER):
        s = d[d["proto"] == proto].set_index("stressors").reindex(stressors)
        x = [val + (idx - (len(PROTOCOL_ORDER) - 1) / 2) * width for val in stressors]

        ax_torn.bar(
            x,
            s["torn_read_frac"].values,
            width=width,
            color=COLORS[proto],
            edgecolor="white",
            linewidth=0.5,
            label=LABELS[proto],
        )

        ax_coh.plot(
            stressors,
            s["coherence_msgs_per_publish"].values,
            color=COLORS[proto],
            marker=MARKERS[proto],
            linewidth=2.5,
            markersize=7.5,
            label=LABELS[proto],
        )

        ax_roi.plot(
            stressors,
            s["roi_ms"].values,
            color=COLORS[proto],
            marker=MARKERS[proto],
            linewidth=2.5,
            markersize=7.5,
            label=LABELS[proto],
        )

        ax_retry.plot(
            stressors,
            s["pub.retries"].values,
            color=COLORS[proto],
            marker=MARKERS[proto],
            linewidth=2.5,
            markersize=7.5,
            label=LABELS[proto],
        )

    ax_torn.set_title(_panel_title("a", "Torn-read fraction"))
    ax_torn.set_ylabel("Torn reads / reads attempted")
    ax_torn.set_xticks(stressors)
    ax_torn.set_xlabel("Stressor count")
    ax_torn.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))

    ax_coh.set_title(_panel_title("b", "CPU-side coherence traffic"))
    ax_coh.set_ylabel("Messages per publish")
    ax_coh.set_xticks(stressors)
    ax_coh.set_xlabel("Stressor count")

    ax_roi.set_title(_panel_title("c", "Whole-workload simulated time"))
    ax_roi.set_ylabel("Simulated time (ms)")
    ax_roi.set_xticks(stressors)
    ax_roi.set_xlabel("Stressor count")

    ax_retry.set_title(_panel_title("d", "Reader retries per run"))
    ax_retry.set_ylabel("Retries / run")
    ax_retry.set_xticks(stressors)
    ax_retry.set_xlabel("Stressor count")
    ax_retry.set_yscale("symlog", linthresh=1.0)

    for ax in axes.flat:
        ax.margins(x=0.08)

    handles, labels = ax_coh.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 1.02),
        columnspacing=1.5,
        handletextpad=0.5,
    )
    fig.subplots_adjust(top=0.82, bottom=0.10, left=0.08, right=0.99, wspace=0.28, hspace=0.38)
    _save(fig, out_stem)


def plot_workload_sensitivity(df: pd.DataFrame, out_stem: Path) -> None:
    d = df[df["proto"].isin(CORRECT_ORDER)].copy()
    if d.empty:
        raise ValueError("no rows for correct architectures")
    d["roi_ms"] = d["simSeconds"] * 1e3

    agg = (
        d.groupby(["workload", "proto"], as_index=False)[
            ["coherence_msgs_per_publish", "roi_ms", "pub.retries"]
        ]
        .mean()
    )

    workloads = list(WORKLOAD_LABELS.keys())
    x = range(len(workloads))
    width = 0.24

    fig, ax_coh = plt.subplots(1, 1, figsize=(6.6, 4.2))

    for idx, proto in enumerate(CORRECT_ORDER):
        s = agg[agg["proto"] == proto].set_index("workload").reindex(workloads)
        offsets = [val + (idx - (len(CORRECT_ORDER) - 1) / 2) * width for val in x]
        ax_coh.bar(
            offsets,
            s["coherence_msgs_per_publish"].values,
            width=width,
            color=COLORS[proto],
            edgecolor="white",
            linewidth=0.5,
            label=LABELS[proto],
        )

    tick_labels = ["Captured\nsparse divergence", "Synthesized\nsustained bias"]
    ax_coh.set_ylabel("Messages per publish")
    ax_coh.set_xticks(list(x), tick_labels)
    ax_coh.grid(False)

    handles, labels = ax_coh.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=1,
        frameon=False,
        bbox_to_anchor=(0.5, 0.995),
        columnspacing=1.2,
        handletextpad=0.5,
    )
    fig.subplots_adjust(top=0.78, bottom=0.16, left=0.14, right=0.98)
    _save(fig, out_stem)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metrics",
        type=Path,
        default=repo_root / "impl/results/gem5/matrix_full/metrics.csv",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=repo_root / "report/figures",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.metrics)
    outdir = args.outdir
    plot_main_results(df, outdir / "paper_main_results")
    plot_workload_sensitivity(df, outdir / "paper_workload_sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
