"""Figure 5: PAIR I in one float, the trade-off plane over the same ladder in counts.

Leak is the total leak (decision plus refusal-channel leak, echoes excluded) from
evidence/v3.14/total-disclosure/pair1_cells.json; false refusal from evidence/v3.13/single-grid/cells.json.
One encoding with Figure 3: requester by colour, rung by marker (D0 circle, D1 square, D2 triangle); the
stranger, who is entitled to one question, sits on a labeled leak-only strip under each panel, with a legend
entry. Drawn at the text width (5.5 in) so every label prints at 7 pt or more.
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
from matplotlib.patches import Patch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PNG = sys.argv[1] if len(sys.argv) > 1 else None   # optional preview path
cells = {c["cell"]: c for c in json.load(open(f"{REPO}/evidence/v3.13/single-grid/cells.json"))["cells"]}
TDC = json.load(open(f"{REPO}/evidence/v3.14/total-disclosure/pair1_cells.json"))["cells"]

FAMS = [("ds41", "DeepSeek V4.1"), ("glm", "GLM-5.3-Flash"), ("luna", "GPT-5.6")]
REQS = [("r1", "R1 colleague", "#2a78d6"), ("r2", "R2 CEO's assistant", "#eb6834"), ("r3", "R3 close friend", "#1baf7a")]
R0C = "#4a3aa7"
ALLREQ = [("r0", "R0"), ("r1", "R1"), ("r2", "R2"), ("r3", "R3")]
POLS = ["d0", "d1", "d2"]
PLAB = ["D0", "D1", "D2"]
RUNG = [("o", 22), ("s", 19), ("^", 32)]
LEAK, HELD, EDGE = "#C2553F", "#DCE4EA", "#9FB0BD"

plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 8,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7.2})


def style(ax):
    ax.grid(True, lw=0.45, color="#E8ECEF", zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#B9C3CC")
        ax.spines[s].set_linewidth(0.8)


def tl(fam, pol, req):
    a = TDC[f"{fam}-{pol}-{req}"]["relationship"]
    return a["TD"], a["n"]


def pct(k, n):
    return float(Fraction(100 * k, n))


def fr(fam, pol, req):
    m = cells[f"{fam}-{pol}-{req}"]["recovered"]["falseRefusalRate"]
    return pct(m["numerator"], m["denominator"])


fig = plt.figure(figsize=(5.5, 4.55))
outer = fig.add_gridspec(3, 3, height_ratios=[1.12, 0.95, 0.16], hspace=0.45, wspace=0.25,
                         left=0.1, right=0.995, top=0.95, bottom=0.03)

# ---- top row: the trade-off plane, with the stranger's leak-only strip ----
for col, (fam, fname) in enumerate(FAMS):
    inner = outer[0, col].subgridspec(2, 1, height_ratios=[1.0, 0.11], hspace=0.08)
    ax = fig.add_subplot(inner[0])
    for req, rlab, c in REQS:
        xs = [pct(*tl(fam, p, req)) for p in POLS]
        ys = [fr(fam, p, req) for p in POLS]
        for k in range(2):
            ax.annotate("", xy=(xs[k + 1], ys[k + 1]), xytext=(xs[k], ys[k]),
                        arrowprops=dict(arrowstyle="-|>,head_width=0.12,head_length=0.28", color=c,
                                        lw=1.0, shrinkA=2.8, shrinkB=2.8, alpha=0.85), zorder=3)
        for k, (mk, sz) in enumerate(RUNG):
            ax.scatter(xs[k], ys[k], s=sz, marker=mk, facecolor=c, edgecolor="white", lw=0.6, zorder=6 + k)
    ax.set_xlim(-3, 95)
    ax.set_ylim(-3, 72)
    ax.set_title(fname, pad=3)
    ax.tick_params(axis="x", labelbottom=False, length=0)
    style(ax)
    if col == 0:
        ax.set_ylabel("false refusal (%)")
    strip = fig.add_subplot(inner[1], sharex=ax)
    r0 = [pct(*tl(fam, p, "r0")) for p in POLS]
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
        strip.text(-0.02, 0.5, "R0", transform=strip.transAxes, ha="right", va="center", fontsize=7, color=R0C,
                   fontweight="bold")

# ---- bottom row: the same ladder in counts ----
W = 0.26
for col, (fam, fname) in enumerate(FAMS):
    ax = fig.add_subplot(outer[1, col])
    for gi, (req, rlab) in enumerate(ALLREQ):
        for pi, pol in enumerate(POLS):
            k, n = tl(fam, pol, req)
            x = gi + (pi - 1) * W
            ax.bar(x, n, width=W, color=HELD, edgecolor=EDGE, lw=0.5, zorder=2)
            ax.bar(x, k, width=W, color=LEAK, edgecolor="none", zorder=3)
            if pi == 2:
                ax.text(x + W * 0.05, k + 8, str(k), ha="center", va="bottom", fontsize=7, color=LEAK, zorder=5,
                        bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none", alpha=0.85))
    ax.set_xticks(range(4))
    ax.set_xticklabels([r for _, r in ALLREQ], fontsize=7.2, fontweight="bold", color="#3C4A56")
    ax.tick_params(axis="x", length=0, pad=2)
    ax.set_ylim(0, 430)
    if col:
        ax.set_yticklabels([])
    else:
        ax.set_ylabel("protected questions")
    style(ax)

# ---- shared legend ----
lax = fig.add_subplot(outer[2, :])
lax.axis("off")
lax.legend(handles=[Line2D([], [], color=c, lw=1.8, label=lab) for _, lab, c in REQS]
           + [Line2D([], [], color=R0C, lw=1.8, label="R0 stranger (leak only)")]
           + [Line2D([], [], ls="", marker=mk, color="#333333", ms=4.2, label=r) for (mk, _), r in zip(RUNG, PLAB)]
           + [Patch(fc=LEAK, ec="none", label="leaked"), Patch(fc=HELD, ec=EDGE, lw=0.5, label="not leaked")],
           loc="center", ncol=5, frameon=False, handlelength=1.3, handletextpad=0.4, columnspacing=0.8, borderpad=0.0)
fig.savefig(f"{REPO}/figures/single_grid/single_ladder_combined.pdf")
if PNG:
    fig.savefig(PNG, dpi=240)
print("written")
