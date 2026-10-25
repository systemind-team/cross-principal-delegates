#!/usr/bin/env python3
"""One protocol and four configuration dimensions.

House style is inherited from scripts/render_pair_multiturn.py: same palette,
same rounded primitives, same 9pt floor on every label, same refusal to ship a
figure whose text runs off the canvas.

Usage: python3 scripts/render_pair_design.py
"""
from __future__ import annotations

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


def save(fig, name: str) -> None:
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    c = fig.bbox
    boxes = []
    for t in fig.findobj(match=matplotlib.text.Text):
        if not t.get_visible() or not t.get_text():
            continue
        b = t.get_window_extent(r)
        if b.x0 < -1 or b.y0 < -1 or b.x1 > c.width + 1 or b.y1 > c.height + 1:
            raise ValueError(f"Text outside {name} canvas: {t.get_text()!r}")
        boxes.append((b, t.get_text()))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b2 = boxes[i][0], boxes[j][0]
            ox = min(a.x1, b2.x1) - max(a.x0, b2.x0)
            oy = min(a.y1, b2.y1) - max(a.y0, b2.y0)
            if ox > 1.5 and oy > 1.5:
                raise ValueError(
                    f"Text collides in {name}: {boxes[i][1]!r} / {boxes[j][1]!r}")
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"{name}.{fmt}", dpi=300,
                    bbox_inches="tight", pad_inches=0.02)
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


AXES = (
    ("Policy", "what it is told", GOLD,
     ("D0  none", "D1  generic", "D2  explicit"),
     "60 tasks × 3 reps"),
    ("Requester", "persona it plays", BLUE,
     ("R0  stranger", "R1  colleague", "R2  exec aide", "R3  friend"),
     "600 tasks × 3 reps"),
    ("Packing", "grouping + budget", BLUE,
     ("1 task", "3 tasks", "10 tasks"),
     "60 tasks × 3 reps"),
    ("Model", "who answers", BLUE,
     ("DeepSeek Flash", "GLM", "Grok"),
     "200 groups each"),
)


def design_axes() -> None:
    fig, ax = plt.subplots(figsize=(7.1, 3.30))
    ax.set_xlim(0, 10); ax.set_ylim(0.08, 3.60); ax.axis("off")

    # ---- held fixed: the protocol
    ax.text(0.10, 3.46, "Held fixed", ha="left", va="center", fontsize=9,
            fontweight="bold", color=INK)
    ax.text(9.90, 3.46, "one requester, one responder, one continuous session",
            ha="right", va="center", fontsize=9, color=GRAY)
    panel(ax, 0.10, 2.22, 9.80, 1.02, face="white", edge=LIGHT)

    steps = (("Phase 1", "every task asked once", BLUE_LIGHT, 0.28, 3.00),
             ("Phase 2", "five reframings, unresolved only", GOLD_LIGHT, 3.62, 3.55),
             ("Finalize", "pending closed", BLUE_LIGHT, 7.70, 2.02))
    for head, body, face, x, w in steps:
        panel(ax, x, 2.36, w, 0.74, face=face, edge=face)
        ax.text(x + 0.16, 2.92, head, ha="left", va="center", fontsize=9,
                fontweight="bold")
        ax.text(x + 0.16, 2.60, body, ha="left", va="center", fontsize=9,
                color=GRAY)
    arrow(ax, (3.32, 2.73), (3.56, 2.73))
    arrow(ax, (7.35, 2.73), (7.64, 2.73))

    # ---- configuration dimensions
    ax.text(0.10, 2.00, "Configuration dimensions", ha="left", va="center",
            fontsize=9, fontweight="bold", color=INK)

    w, gap = 2.36, 0.12
    for i, (name, sub, accent, settings, foot) in enumerate(AXES):
        x = 0.10 + i * (w + gap)
        panel(ax, x, 0.16, w, 1.66)
        ax.add_patch(FancyBboxPatch((x, 1.50), w, 0.32,
                                    boxstyle="round,pad=0,rounding_size=0.05",
                                    linewidth=0, facecolor=accent, zorder=3))
        ax.text(x + w / 2, 1.66, name, ha="center", va="center", fontsize=9,
                fontweight="bold", color="white", zorder=5)
        ax.text(x + w / 2, 1.36, sub, ha="center", va="center", fontsize=9,
                color=GRAY)
        for j, s in enumerate(settings):
            y = 1.10 - j * 0.215
            ax.plot([x + 0.20], [y], marker="o", markersize=2.6,
                    color=accent, zorder=5)
            ax.text(x + 0.34, y, s, ha="left", va="center", fontsize=9)
        ax.text(x + w / 2, 0.27, foot, ha="center", va="center", fontsize=9,
                color=GRAY)

    save(fig, "design_axes")


if __name__ == "__main__":
    print("Rendering:")
    design_axes()
