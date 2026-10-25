"""Figure 3: every D0 -> D1 -> D2 ladder of PAIR I and PAIR II, each responder model in its own panel.

Rows are studies, columns are responder models. Each panel draws one block's ladder as operating points, D0 (circle)
-> D1 (square) -> D2 (triangle); lower-left is what a policy tries to reach. Both rows plot the total leak (
decision leak plus refusal-channel leak, echoes excluded) against false refusal.
  PAIR I : total leak from evidence/v3.14/total-disclosure/pair1_cells.json (relationship labels, with recovery);
           false refusal from evidence/v3.13/single-grid/cells.json.
  PAIR II: total leak from evidence/v3.14/pair2-total-disclosure/td.json (the counts behind Table 4);
           false refusal from evidence/v3.13/multi-table3/table3s.json.
The stranger (R0) has one entitled question, so it has no false refusal: it is drawn as a separate, labeled
leak-only strip under each PAIR I panel. NET is not drawn. Changes against v3.13:
no NET row or colors, a shared legend under the panels, R0 on its own labeled strip, a PAIR II row with a 0-12%
false-refusal axis so its arrows separate, glossary v2 names, text at 7 pt or more. Page cuts: the
PAIR II panels are drawn at the height of PAIR I's panels, at the same width; every other dimension is unchanged.
"""
import json
import os
import sys
from fractions import Fraction

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})  # TrueType (Type 42) fonts in PDF and PS, no Type 3 (arXiv)
from matplotlib.lines import Line2D

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "figures", "overview", "three_ladders.pdf")
PNG = sys.argv[1] if len(sys.argv) > 1 else None

single = {c["cell"]: c for c in json.load(open(f"{ROOT}/evidence/v3.13/single-grid/cells.json"))["cells"]}
tl1 = json.load(open(f"{ROOT}/evidence/v3.14/total-disclosure/pair1_cells.json"))["cells"]
tl2 = json.load(open(f"{ROOT}/evidence/v3.14/pair2-total-disclosure/td.json"))["blocks"]
fr2 = json.load(open(f"{ROOT}/evidence/v3.13/multi-table3/table3s.json"))["blocks"]

R1C, R2C, R3C, R0C = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"   # colour-blind-safe, all-pairs separable
REQS = [("1", "R1 colleague", R1C), ("2", "R2 CEO's assistant", R2C), ("3", "R3 close friend", R3C)]
INK = "#333333"
plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 8.0,
                     "xtick.labelsize": 7.0, "ytick.labelsize": 7.0, "legend.fontsize": 7.2})
RUNGS = ("D0", "D1", "D2")
RUNG = [("o", 22), ("s", 19), ("^", 32)]


def pct(k, n):
    return float(Fraction(100 * k, n))


def style(ax):
    ax.grid(True, lw=0.45, color="#E8ECEF", zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#B9C3CC")
        ax.spines[s].set_linewidth(0.8)


def path(ax, xs, ys, col, scale=1.0):
    for k in range(2):
        ax.annotate("", xy=(xs[k + 1], ys[k + 1]), xytext=(xs[k], ys[k]),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.12,head_length=0.28", color=col,
                                    lw=1.0, shrinkA=2.8, shrinkB=2.8, alpha=0.85), zorder=3)
    for k, (mk, sz) in enumerate(RUNG):
        ax.scatter(xs[k], ys[k], s=sz * scale, marker=mk, facecolor=col, edgecolor="white", lw=0.6, zorder=6 + k)


# Geometry in inches. PAIR I's row (panel, gap, R0 strip), the legend, the gaps and the margins keep the sizes of the
# 5.5 x 4.75 in layout before the page cuts; the PAIR II panels take PAIR I's panel height.
ROW1, P1_PANEL, LEG, GAP, TOP_M, BOT_M = 1.6576, 1.4359, 0.2388, 0.4858, 0.2138, 0.0950
ROW2 = P1_PANEL
SUM = ROW1 + ROW2 + LEG
FIG_H = SUM + 2 * GAP + TOP_M + BOT_M
fig = plt.figure(figsize=(5.5, FIG_H))
outer = fig.add_gridspec(3, 3, height_ratios=[ROW1, ROW2, LEG], hspace=GAP / (SUM / 3), wspace=0.28,
                         left=0.115, right=0.99, top=1 - TOP_M / FIG_H, bottom=BOT_M / FIG_H)

# ---- PAIR I: one panel per responder model, with the stranger's leak-only strip beneath ----
for col, (fam, name) in enumerate([("ds41", "DeepSeek V4.1"), ("glm", "GLM-5.3-Flash"), ("luna", "GPT-5.6")]):
    inner = outer[0, col].subgridspec(2, 1, height_ratios=[1.0, 0.11], hspace=0.08)
    ax = fig.add_subplot(inner[0])
    for q, lab, c in REQS:
        xs = [pct(tl1[f"{fam}-{p.lower()}-r{q}"]["relationship"]["TD"], tl1[f"{fam}-{p.lower()}-r{q}"]["relationship"]["n"]) for p in RUNGS]
        ys = []
        for p in RUNGS:
            fr = single[f"{fam}-{p.lower()}-r{q}"]["recovered"]["falseRefusalRate"]
            ys.append(pct(fr["numerator"], fr["denominator"]))
        path(ax, xs, ys, c)
        if col == 0 and q == "3":
            for (x, y), lab_, off in zip(zip(xs, ys), RUNGS, ((-4, 5), (4, 4), (-15, 4))):
                ax.annotate(lab_, (x, y), textcoords="offset points", xytext=off, fontsize=7.0, color=INK,
                            fontweight="bold")
    ax.set_xlim(-3, 95)
    ax.set_ylim(-3, 72)
    ax.set_title(name, pad=3)
    ax.tick_params(axis="x", labelbottom=False)
    style(ax)
    if col == 0:
        ax.set_ylabel("false refusal (%)")
    ax.tick_params(axis="x", length=0)
    strip = fig.add_subplot(inner[1], sharex=ax)
    r0 = [pct(tl1[f"{fam}-{p.lower()}-r0"]["relationship"]["TD"], tl1[f"{fam}-{p.lower()}-r0"]["relationship"]["n"]) for p in RUNGS]
    strip.plot(r0, [0] * 3, color=R0C, lw=0.8, alpha=0.6, zorder=4)
    for (mk, sz), v in zip(RUNG, r0):
        strip.scatter(v, 0, s=sz * 0.7, marker=mk, facecolor=R0C, edgecolor="white", lw=0.4, zorder=5)
    strip.set_ylim(-1, 1)
    strip.set_yticks([])
    for s in ("top", "right", "left"):
        strip.spines[s].set_visible(False)
    strip.spines["bottom"].set_color("#B9C3CC")
    strip.set_xlabel("total leak (%)", labelpad=1)
    if col == 0:
        strip.text(-0.02, 0.5, "R0", transform=strip.transAxes, ha="right", va="center", fontsize=7.0, color=R0C,
                   fontweight="bold")

# ---- PAIR II: one panel per model; false refusal stays under 12%, so the axis stops at 12 ----
for col, (b, name) in enumerate([("DS", "DeepSeek V4"), ("GLM", "GLM-5.3"), ("GROK", "Grok 4.6")]):
    ax = fig.add_subplot(outer[1, col])
    for q, lab, c in REQS:
        t = tl2[f"{b}-R{q}"]
        xs = [pct(t[p]["total"], t["n"]) for p in RUNGS]
        ys = [fr2[f"{b}-R{q}"]["rates"][p]["FR"]["value"] for p in RUNGS]
        path(ax, xs, ys, c)
    ax.set_xlim(-3, 100)
    ax.set_ylim(-0.8, 12)
    ax.set_yticks([0, 4, 8, 12])
    ax.set_title(name, pad=3)
    ax.set_xlabel("total leak (%)", labelpad=1)
    style(ax)
    if col == 0:
        ax.set_ylabel("false refusal (%)")

# ---- shared legend under the panels ----
lax = fig.add_subplot(outer[2, :])
lax.axis("off")
lax.legend(handles=[Line2D([], [], color=c, lw=1.8, label=lab) for _, lab, c in REQS]
           + [Line2D([], [], color=R0C, lw=1.8, label="R0 stranger (leak only)")]
           + [Line2D([], [], ls="", marker=mk, color=INK, ms=4.2, label=r) for (mk, _), r in zip(RUNG, RUNGS)],
           loc="center", ncol=4, frameon=False, handlelength=1.3, handletextpad=0.4, columnspacing=1.2,
           borderpad=0.0)
ROW2_BOTTOM = BOT_M + LEG + GAP
for y, lab in (((ROW2_BOTTOM + ROW2 + GAP + 0.7314) / FIG_H, "PAIR I"), ((ROW2_BOTTOM + 0.566 * ROW2) / FIG_H, "PAIR II")):
    fig.text(0.005, y, lab, rotation=90, va="center", ha="left", fontsize=8.0, fontweight="bold", color="#1F3A5F")
fig.savefig(OUT)
if PNG:
    fig.savefig(PNG, dpi=200)
print("written", OUT)
