"""Charts for the deck. Numbers are copied from the repo; each function names its source.

Run: python charts.py   (writes the PNGs next to this file)
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "")
NAVY = "#1F3B5C"
ACCENT = "#D9822B"
GREY = "#6B7280"
GRID = "#E5E7EB"
plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 16,
    "axes.edgecolor": "#9CA3AF",
    "axes.labelcolor": "#374151",
    "xtick.color": "#374151",
    "ytick.color": "#374151",
    "hatch.linewidth": 1.5,
})


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# 1. nbody ladder -- results/compare_nbody.txt, compare_nbody_native.txt, report_nbody.txt
def nbody_ladder():
    names = ["Original Python", "Optimized Python", "Python + Rust"]
    ms = [231.20, 143.13, 9.530]
    lab = ["231.2 ms\n1.00x", "143.1 ms\n1.62x", "9.53 ms\n24.26x"]
    cols = [NAVY, NAVY, ACCENT]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
    bars = ax.bar(names, ms, color=cols, width=0.55)
    ax.set_yscale("log")
    ax.set_ylim(3, 600)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_yticks([5, 10, 50, 100, 500])
    ax.set_ylabel("Time per run (ms, log scale)")
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)
    for b, t in zip(bars, lab):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.12, t,
                ha="center", va="bottom", fontsize=15, color="#111827", fontweight="bold")
    clean(ax)
    ax.tick_params(axis="x", labelsize=16, length=0)
    fig.tight_layout()
    fig.savefig(OUT + "nbody_ladder.png", facecolor="white")


# 2. Barnes-Hut crossover -- results/bigN_sweep.txt (VM, theta 0.5, best of 7)
def bh_crossover():
    N = [5, 50, 100, 200, 300, 400, 600, 800, 1200, 1600]
    r = [0.077 / 0.020, 2.712 / 1.188, 8.410 / 4.746, 23.781 / 18.998, 42.489 / 42.977,
         61.996 / 77.424, 108.429 / 174.530, 158.846 / 313.489, 265.361 / 702.259,
         382.471 / 1254.660]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
    ax.axhspan(1, 6, color="#FDF2E9", zorder=0)
    ax.axhline(1, color=GREY, lw=1.5, ls="--", zorder=1)
    ax.plot(N, r, color=NAVY, lw=2.5, marker="o", ms=8, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(3.5, 2600)
    ax.set_ylim(0.2, 6)
    ax.set_xticks([5, 50, 100, 300, 1600])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_yticks([0.25, 0.5, 1, 2, 4])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}x"))
    ax.minorticks_off()
    ax.set_xlabel("Bodies N (log scale)")
    ax.set_ylabel("Tree time / direct time")
    ax.grid(color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.text(2500, 4.6, "tree slower", ha="right", color=ACCENT, fontsize=15, fontweight="bold")
    ax.text(2500, 0.6, "tree faster", ha="right", color=GREY, fontsize=15, fontweight="bold")
    ax.annotate("N = 5, the benchmark:\n3.92x slower", (5, r[0]), xytext=(6.5, 1.35),
                fontsize=14, color="#111827", va="center")
    ax.annotate("break-even near N = 300", (300, r[4]), xytext=(330, 1.5),
                fontsize=14, color="#111827",
                arrowprops=dict(arrowstyle="-", color=GREY, lw=1))
    ax.annotate("N = 1,600: 0.30x", (1600, r[-1]), xytext=(420, 0.235),
                fontsize=14, color="#111827")
    clean(ax)
    fig.tight_layout()
    fig.savefig(OUT + "bh_crossover.png", facecolor="white")


# 3. pyflate ladder -- results/compare_pyflate*.txt (pyperf) and
#    results/pyflate_ladder_20261005/README.md (best of 7, starred)
def pyflate_ladder():
    rows = [
        ("Original Python", 1123.5, "1123.5 ms  1.00x", NAVY),
        ("+ per-byte fixes, faster move-to-front", 676, "676 ms*  1.67x", NAVY),
        ("+ canonical Huffman decode", 455, "455 ms*  2.48x", NAVY),
        ("+ flat table, regex run-length (shipped)", 281.2, "281.2 ms  4.00x", NAVY),
        ("+ Rust symbol loop", 170.0, "170.0 ms  6.61x", ACCENT),
    ]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
    y = list(range(len(rows)))[::-1]
    for yi, (n, v, t, c) in zip(y, rows):
        ax.barh(yi, v, color=c, height=0.62)
        ax.text(v + 15, yi, t, va="center", fontsize=15, color="#111827", fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=15)
    ax.set_xlim(0, 1900); ax.set_xticks([0, 500, 1000]); ax.spines["bottom"].set_bounds(0, 1123.5)
    ax.set_xlabel("Time per run on the course VM (ms)")
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    clean(ax)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT + "pyflate_ladder.png", facecolor="white")


# 4. pyflate ladder + the post-submission experiment bar.  The extra bar is
#    results/bwt_rust_20261005/rest2.log on branch experiment/bwt-rust: pyperf
#    14.6 ms vs 161 ms for the submitted build in the same session (11.06x).
#    It is labelled against 161 ms, not the 170 ms bar, so sessions are not mixed.
def pyflate_ladder_experiment():
    rows = [
        ("Original Python", 1123.5, "1123.5 ms  1.00x", "solid", NAVY),
        ("+ per-byte fixes, faster move-to-front", 676, "676 ms*  1.67x", "solid", NAVY),
        ("+ canonical Huffman decode", 455, "455 ms*  2.48x", "solid", NAVY),
        ("+ flat table, regex run-length (shipped)", 281.2, "281.2 ms  4.00x", "solid", NAVY),
        ("+ Rust symbol loop", 170.0, "170.0 ms  6.61x", "solid", ACCENT),
        ("+ inverse BWT, run-length in Rust\u2020", 14.6, "14.6 ms\u2020  11.06x vs 161 ms", "hatch", ACCENT),
    ]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
    y = list(range(len(rows)))[::-1]
    for yi, (n, v, t, style, c) in zip(y, rows):
        if style == "solid":
            ax.barh(yi, v, color=c, height=0.62)
        else:
            ax.barh(yi, v, color="white", edgecolor=c, hatch="///", linewidth=1.5, height=0.62)
        ax.text(v + 15, yi, t, va="center", fontsize=15, fontweight="bold",
                color="#111827" if style == "solid" else c)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=15)
    ax.get_yticklabels()[-1].set_color(ACCENT)
    ax.set_xlim(0, 1900); ax.set_xticks([0, 500, 1000]); ax.spines["bottom"].set_bounds(0, 1123.5)
    ax.set_xlabel("Time per run on the course VM (ms)")
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    clean(ax)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT + "pyflate_ladder_experiment.png", facecolor="white")


if __name__ == "__main__":
    nbody_ladder()
    bh_crossover()
    pyflate_ladder()
    pyflate_ladder_experiment()
    print("ok")
