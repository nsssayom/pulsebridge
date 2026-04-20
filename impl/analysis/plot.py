#!/usr/bin/env python3
"""
Produce RQ-aligned plots from the tidy CSV emitted by collect.py.

Writes PNG files next to metrics.csv. Missing metrics are silently skipped;
this script is safe to run on partial matrices.

Design choices:
- One consistent protocol color (Okabe-Ito palette, colorblind-safe) reused
  across every plot so the reader only learns the legend once.
- Each figure is faceted by workload so the two workloads never share an
  axis; stressor count is the ordinal x-axis inside each facet.
- Markers differ per protocol so the plots also read correctly in grayscale.

Usage:
    python3 plot.py <results_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

PROTOCOL_ORDER = ["unsync", "dma_naive", "dma_seqlock", "seqlock", "dblbuf"]

# Okabe-Ito colorblind-safe palette. Grey/orange/vermillion on the "no
# atomicity" protocols (unsync, dma_naive); blue/green on the protocols
# with a publication discipline (dma_seqlock, seqlock, dblbuf).
PROTOCOL_COLORS = {
    "unsync":      "#999999",
    "dma_naive":   "#D55E00",
    "dma_seqlock": "#56B4E9",
    "seqlock":     "#0072B2",
    "dblbuf":      "#009E73",
}
PROTOCOL_MARKERS = {
    "unsync": "x", "dma_naive": "D", "dma_seqlock": "P",
    "seqlock": "o", "dblbuf": "^",
}
PROTOCOL_LABELS = {
    "unsync":      "No discipline (baseline)",
    "dma_naive":   "DMA mirror, no discipline",
    "dma_seqlock": "DMA mirror + sequence lock",
    "seqlock":     "Sequence lock (coherent)",
    "dblbuf":      "Generation double-buffer",
}

WORKLOAD_LABELS = {
    "captured/periodic_suppression": "Captured workload (sparse divergence)",
    "synthesized/duty_bias":         "Synthesized workload (duty bias)",
}

PAPER_WORKLOAD = "captured/periodic_suppression"

plt.rcParams.update({
    "figure.dpi":        150,
    "savefig.dpi":       220,
    "font.size":         14,
    "axes.titlesize":    15,
    "axes.labelsize":    14,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "grid.linestyle":    "--",
    "legend.frameon":    False,
    "legend.fontsize":   12,
})


def _workloads(df: pd.DataFrame) -> list[str]:
    present = [w for w in WORKLOAD_LABELS if w in df["workload"].unique()]
    if not present:
        present = sorted(df["workload"].unique().tolist())
    return present


def _stressor_ticks(df: pd.DataFrame) -> list[int]:
    return sorted(df["stressors"].unique().tolist())


def _plot_lines(ax, sub: pd.DataFrame, y_col: str) -> None:
    """Protocol-colored line per facet, stressor count on x."""
    for proto in PROTOCOL_ORDER:
        s = sub[sub["proto"] == proto].sort_values("stressors")
        if s.empty:
            continue
        ax.plot(
            s["stressors"], s[y_col],
            color=PROTOCOL_COLORS[proto],
            marker=PROTOCOL_MARKERS[proto],
            markersize=6, linewidth=1.8,
            label=PROTOCOL_LABELS[proto],
        )


def _plot_grouped_bars(ax, sub: pd.DataFrame, y_col: str) -> None:
    """Grouped bars — one bar per protocol, groups clustered by stressor."""
    xs = _stressor_ticks(sub)
    n_proto = len(PROTOCOL_ORDER)
    width = 0.8 / n_proto
    for i, proto in enumerate(PROTOCOL_ORDER):
        s = sub[sub["proto"] == proto].set_index("stressors").reindex(xs)
        offsets = [x + (i - (n_proto - 1) / 2) * width for x in xs]
        ax.bar(
            offsets, s[y_col].values, width=width,
            color=PROTOCOL_COLORS[proto],
            edgecolor="white", linewidth=0.3,
            label=PROTOCOL_LABELS[proto],
        )
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs])


def _faceted(df: pd.DataFrame, title: str, ylabel: str, y_col: str,
             kind: str, out: Path, y_formatter=None, y_log=False) -> None:
    workloads = _workloads(df)
    n = len(workloads)
    fig, axes = plt.subplots(
        1, n, figsize=(5.8 * n, 4.8), sharey=True,
    )
    if n == 1:
        axes = [axes]

    for ax, wl in zip(axes, workloads):
        sub = df[df["workload"] == wl]
        if kind == "line":
            _plot_lines(ax, sub, y_col)
            ax.set_xticks(_stressor_ticks(df))
        else:
            _plot_grouped_bars(ax, sub, y_col)
        ax.set_title(WORKLOAD_LABELS.get(wl, wl), pad=6)
        ax.set_xlabel("stressor count (extra CPUs thrashing cache)")
        if y_log:
            ax.set_yscale("symlog", linthresh=1e-3)
        if y_formatter is not None:
            ax.yaxis.set_major_formatter(y_formatter)
        ax.margins(x=0.08)

    axes[0].set_ylabel(ylabel)

    # Stacked top band: suptitle on row 1, legend on row 2, facets below.
    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.98)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="upper center", ncol=len(handles),
        bbox_to_anchor=(0.5, 0.91), frameon=False, handletextpad=0.5,
        columnspacing=1.8,
    )
    fig.subplots_adjust(top=0.80, bottom=0.12, left=0.08, right=0.98,
                        wspace=0.10)
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def _single_panel(df: pd.DataFrame, title: str, ylabel: str, y_col: str,
                  kind: str, out: Path, y_formatter=None, y_log=False) -> None:
    """Paper-ready single-panel plot on the captured workload only.

    Sized for inclusion across both columns (figure*) so the fonts stay
    readable at the rendered paper size.
    """
    d = df[df["workload"] == PAPER_WORKLOAD]
    if d.empty:
        print(f"skip {out.name}: no rows for {PAPER_WORKLOAD}")
        return
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    if kind == "line":
        _plot_lines(ax, d, y_col)
        ax.set_xticks(_stressor_ticks(d))
    else:
        _plot_grouped_bars(ax, d, y_col)
    ax.set_xlabel("Stressor count (extra cores thrashing cache)")
    ax.set_ylabel(ylabel)
    if y_log:
        ax.set_yscale("symlog", linthresh=1e-3)
    if y_formatter is not None:
        ax.yaxis.set_major_formatter(y_formatter)
    ax.margins(x=0.08)

    fig.suptitle(title, fontsize=17, fontweight="bold", y=0.99)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="upper center", ncol=3,
        bbox_to_anchor=(0.5, 0.92), frameon=False,
        handletextpad=0.5, columnspacing=1.4,
        fontsize=13,
    )
    fig.subplots_adjust(top=0.73, bottom=0.14, left=0.09, right=0.98)
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def plot_rq1_coherence_per_publish(df: pd.DataFrame, out: Path) -> None:
    """CPU-side L1-to-directory Ruby coherence messages per witness publish.

    Sum of L1-to-directory request and response messages in both
    directions plus directory-to-memory requests. DMA-controller traffic
    is not included; the DMA-side cost for the mirror variants is
    plotted separately by plot_rq1_dma_traffic_per_publish.
    """
    col = "coherence_msgs_per_publish"
    if col not in df.columns or df[col].isna().all():
        print(f"skip {out.name}: {col} absent")
        return
    d = df.dropna(subset=[col])
    if d.empty:
        return
    _single_panel(
        d,
        title="CPU-side coherence messages per witness publish",
        ylabel="Ruby L1$\\leftrightarrow$Dir messages per publish",
        y_col=col, kind="line", out=out,
    )


def plot_rq1_dma_traffic_per_publish(df: pd.DataFrame, out: Path) -> None:
    """DMA-controller request traffic per witness publish (mirror only).

    Companion to the CPU-side coherence plot. Makes the extra
    explicit-transfer cost visible for the two DMA-mirror protocols so
    the L1-to-directory headline is not mistaken for the total
    transport cost.
    """
    col = "system.ruby.dma_cntrl0.requestToDir.m_msg_count__per_publish"
    if col not in df.columns or df[col].isna().all():
        print(f"skip {out.name}: {col} absent")
        return
    d = df.dropna(subset=[col]).copy()
    if d.empty:
        return
    _single_panel(
        d,
        title="DMA-controller requests per witness publish",
        ylabel="DMA controller requests per publish",
        y_col=col, kind="line", out=out,
    )


def plot_rq1_torn_reads(df: pd.DataFrame, out: Path) -> None:
    if "torn_read_frac" not in df.columns or df["torn_read_frac"].isna().all():
        print(f"skip {out.name}: torn_read_frac absent")
        return
    d = df.dropna(subset=["torn_read_frac"]).copy()
    _single_panel(
        d,
        title="Torn-read fraction by protocol",
        ylabel="Torn reads / reads attempted",
        y_col="torn_read_frac", kind="bar", out=out,
        y_formatter=PercentFormatter(xmax=1, decimals=0),
    )


def plot_rq3_roi_duration(df: pd.DataFrame, out: Path) -> None:
    """Whole-ROI simulated time vs stressor count.

    This is not per-publication-to-alarm latency. It is the total
    simulated time between m5_reset_stats and bench_dump_stats, i.e.\ the
    wall clock to retire the full workload under each protocol. Per-
    publish latency is deferred to follow-on bench instrumentation.
    """
    if "simSeconds" not in df.columns:
        print(f"skip {out.name}: simSeconds absent")
        return
    d = df.dropna(subset=["simSeconds"]).copy()
    d["roi_ms"] = d["simSeconds"] * 1e3
    _single_panel(
        d,
        title="Whole-workload simulated time",
        ylabel="Simulated wall time (ms)",
        y_col="roi_ms", kind="line", out=out,
    )


def print_summary(df: pd.DataFrame) -> None:
    cols = [c for c in ("proto", "workload", "stressors",
                        "simSeconds", "pub.publishes", "mon.samples_consumed",
                        "mon.torn_reads", "torn_read_frac",
                        "l1_request_from_msgs_total__per_publish")
            if c in df.columns]
    d = df.copy()
    d["proto"] = pd.Categorical(d["proto"], categories=PROTOCOL_ORDER, ordered=True)
    print(d.sort_values(["workload", "proto", "stressors"])[cols]
            .to_string(index=False))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: plot.py <results_dir>", file=sys.stderr)
        return 2
    results_dir = Path(sys.argv[1]).resolve()
    metrics = results_dir / "metrics.csv"
    if not metrics.is_file():
        print(f"error: run collect.py first — {metrics} missing", file=sys.stderr)
        return 1
    df = pd.read_csv(metrics)
    if df.empty:
        print("error: metrics.csv is empty", file=sys.stderr)
        return 1

    print_summary(df)
    plot_rq1_coherence_per_publish(df, results_dir / "rq1_coherence_per_publish.png")
    plot_rq1_dma_traffic_per_publish(df, results_dir / "rq1_dma_traffic_per_publish.png")
    plot_rq1_torn_reads(df, results_dir / "rq1_torn_reads.png")
    plot_rq3_roi_duration(df, results_dir / "rq3_roi_duration.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
