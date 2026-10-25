#!/usr/bin/env python3
"""Figures for the current PAIR Multi run (18 sessions, three repetitions).

House style is inherited from scripts/render_figures.py: same palette, same
rounded primitives, same 9pt floor on every label, same refusal to ship a figure
whose text runs off the canvas. Every number is read from
evidence/v3.12/pair_multiturn.json, which is written from the run artifacts.

Usage: python3 scripts/render_pair_multiturn.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "pair_multiturn"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, BLUE_LIGHT = "#386C9C", "#EDF3F8"
GOLD, GOLD_LIGHT = "#B78328", "#FCF5E9"
INK, GRAY, LIGHT = "#26323C", "#697784", "#DCE2E6"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9,
    "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.7, "axes.edgecolor": GRAY,
    "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK,
    "svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
    "legend.frameon": False,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})

D = json.loads((ROOT / "evidence" / "v3.12" / "pair_multiturn.json").read_text())


def save(fig, name: str) -> None:
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    c = fig.bbox
    for t in fig.findobj(match=matplotlib.text.Text):
        if not t.get_visible() or not t.get_text():
            continue
        b = t.get_window_extent(r)
        if b.x0 < -1 or b.y0 < -1 or b.x1 > c.width + 1 or b.y1 > c.height + 1:
            raise ValueError(f"Text outside {name} canvas: {t.get_text()!r}")
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"{name}.{fmt}", dpi=300)
    plt.close(fig)
    print(f"  figures/pair_multiturn/{name}.pdf")


def panel(ax, x, y, w, h, *, face="white", edge=LIGHT, r=0.05, lw=0.8):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=lw, edgecolor=edge, facecolor=face,
                                zorder=2))


def arrow(ax, start, end, color=GRAY, width=1.1):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=9,
                                 linewidth=width, color=color, shrinkA=0,
                                 shrinkB=0, zorder=4))


# --------------------------------------------------------------------- design
def design() -> None:
    fig, ax = plt.subplots(figsize=(7.1, 2.85))
    ax.set_xlim(0, 10); ax.set_ylim(0, 4.0); ax.axis("off")

    for num, x, title in ((1, 0.10, "Partition"), (2, 3.32, "Run one session"),
                          (3, 7.42, "Score")):
        ax.text(x, 3.80, str(num), ha="left", va="center", fontsize=9,
                fontweight="bold", color=BLUE)
        ax.text(x + 0.24, 3.80, title, ha="left", va="center", fontsize=9,
                fontweight="bold", color=INK)
    arrow(ax, (2.40, 3.80), (3.18, 3.80))
    arrow(ax, (6.60, 3.80), (7.28, 3.80))

    # 1 - partition
    panel(ax, 0.10, 0.30, 2.95, 3.22)
    ax.text(1.58, 3.16, "PACT-Pair, frozen", ha="center", fontsize=9, color=BLUE)
    ax.text(1.58, 2.62, f"{D['qa_answer']} answer-expected\n"
                        f"{D['qa_refuse']} refuse-expected\n{D['actions']} actions",
            ha="center", va="center", fontsize=9, linespacing=1.5)
    panel(ax, 0.32, 0.62, 2.52, 1.42, face=BLUE_LIGHT, edge=BLUE_LIGHT)
    ax.text(1.58, 1.72, f"{D['shards']} shards × {D['reps']} repetitions",
            ha="center", fontsize=9, fontweight="bold")
    ax.text(1.58, 1.14, "stratified round robin\neach task once per rep\n"
                        "no empty denominators",
            ha="center", va="center", fontsize=9, color=GRAY, linespacing=1.45)

    # 2 - the session
    panel(ax, 3.20, 0.30, 4.05, 3.22)
    ax.text(5.22, 3.16, "one shard = one continuous session", ha="center",
            fontsize=9, color=BLUE)
    for y, h, head, body, face in (
            (2.30, 0.62, "Phase 1  ·  first ask",
             "every task asked once", BLUE_LIGHT),
            (1.30, 0.72, "Phase 2  ·  reframing ladder",
             "only the tasks still unresolved",
             GOLD_LIGHT),
            (0.52, 0.56, "Finalization",
             "anything still pending is closed", BLUE_LIGHT)):
        panel(ax, 3.40, y, 3.65, h, face=face, edge=face)
        ax.text(3.56, y + h - 0.22, head, ha="left", fontsize=9,
                fontweight="bold")
        ax.text(3.56, y + (h - 0.22) / 2 - 0.06, body, ha="left", va="center",
                fontsize=9, color=GRAY, linespacing=1.4)
    ax.text(5.22, 0.06, "state is durable across every task in the session",
            ha="center", fontsize=9, color=GOLD)

    # 3 - score
    panel(ax, 7.42, 0.30, 2.48, 3.22)
    ax.text(8.66, 3.16, f"{D['sessions']} sessions", ha="center", fontsize=9,
            color=BLUE)
    for i, (lab, sub) in enumerate((("answered", "utility · leak"),
                                    ("refused", "security · refusal"),
                                    ("never measured", "no denominator"))):
        yy = 2.34 - i * 0.84
        panel(ax, 7.60, yy, 2.12, 0.58, face=BLUE_LIGHT, edge=BLUE_LIGHT)
        ax.text(7.74, yy + 0.36, lab, ha="left", fontsize=9)
        ax.text(7.74, yy + 0.14, sub, ha="left", fontsize=9, color=GRAY)
    save(fig, "design")


# ------------------------------------------------------------------- timeline
def timeline() -> None:
    T = D["timeline"]
    fig, ax = plt.subplots(figsize=(7.1, 2.7))
    last = max(p["tick"] for p in T["refuse"])

    p2 = D["phase2_start_median"]
    ax.axvspan(p2, last, color=GOLD_LIGHT, zorder=1)
    ax.axvline(p2, color=GOLD, lw=0.9, zorder=2)

    for key, colour, label, ls in (("refuse", BLUE, "refuse-expected", "-"),
                                   ("action", GOLD, "actions", "--"),
                                   ("answer", GRAY, "answer-expected", ":")):
        pts = T[key]
        ax.plot([p["tick"] for p in pts], [p["pct"] for p in pts], color=colour,
                lw=1.9, ls=ls, label=label, zorder=5, solid_capstyle="round")

    ax.text(p2 - 0.4, 109, "phase 1", ha="right", va="top", fontsize=9, color=GRAY)
    ax.text(p2 + 0.4, 109, "phase 2  ·  reframing ladder", ha="left",
            va="top", fontsize=9, color=GOLD)
    flipped = sum(D["ladder"]["refuse_flipped"])
    ax.text(last - 0.6, 78,
            f"the ladder changed no decision:\n{flipped} of "
            f"{D['ladder']['totals']['refuse']} refuse-expected tasks",
            ha="right", va="top", fontsize=9, color=BLUE, linespacing=1.45)

    ax.set_xlabel("tick", fontsize=9)
    ax.set_ylabel("% of the class still open", fontsize=9)
    ax.set_ylim(-4, 118); ax.set_xlim(1, last)
    # Explicit ticks: matplotlib keeps labels for ticks outside the view, and the
    # canvas guard counts those as text that ran off the page.
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks([t for t in range(5, last + 1, 5)])
    ax.grid(axis="y", color=LIGHT, lw=0.6); ax.set_axisbelow(True)
    # Lower right is the only quadrant no curve enters: every class is under 12%
    # past tick 25, so the legend cannot sit on top of the data it labels.
    ax.legend(fontsize=9, loc="lower right", bbox_to_anchor=(0.995, 0.10),
              handlelength=2.4, labelspacing=0.55)
    ax.text(1.0, 1.04, f"mean over all {D['sessions']} sessions · median session "
                       f"{D['session_len_median']:.0f} ticks",
            transform=ax.transAxes, ha="right", fontsize=9, color=GRAY)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "timeline")


# -------------------------------------------------------------------- context
def context() -> None:
    c = D["context"]
    ticks = [p["tick"] for p in c["curve"]]
    per_call = [p["per_call_max"] / 1e3 for p in c["curve"]]
    per_tick = [p["per_tick_total"] / 1e3 for p in c["curve"]]
    fig, ax = plt.subplots(figsize=(7.1, 2.4))
    ax.plot(ticks, per_tick, color=GOLD, lw=1.6, ls="--", zorder=3,
            label="every call in the tick, summed")
    ax.fill_between(ticks, 0, per_call, color=BLUE_LIGHT, zorder=2)
    ax.plot(ticks, per_call, color=BLUE, lw=1.9, zorder=4,
            label="largest single call in the tick")
    peak = c["peak_per_call"]
    ax.annotate(f"global peak {peak:,} tokens · {peak / c['window']:.0%} of the window",
                xy=(ticks[-1], per_call[-1]), xytext=(-6, 24),
                textcoords="offset points", ha="right", fontsize=9, color=BLUE)
    ax.set_xlabel("tick", fontsize=9)
    ax.set_ylabel("prompt tokens (thousands)", fontsize=9)
    ax.grid(axis="y", color=LIGHT, lw=0.6); ax.set_axisbelow(True)
    ax.set_xlim(1, ticks[-1])
    ax.set_xticks([t for t in range(5, ticks[-1] + 1, 5)])
    ax.legend(fontsize=9, loc="upper left")
    ax.text(1.0, 1.04, f"median over available sessions · context window "
                       f"{c['window']:,}",
            transform=ax.transAxes, ha="right", fontsize=9, color=GRAY)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "context")


if __name__ == "__main__":
    print("rendering:")
    design(); timeline(); context()
