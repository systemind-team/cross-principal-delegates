#!/usr/bin/env python3
"""Figures for the single-request grid. Reads out/cells.json; writes out/figures/{pdf,png,svg}.
Palette: validated 3-slot categorical (dataviz reference) for the three responder models; blue sequential ramp for delivery."""
import json, os, math, sys
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats import wilson
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})  # TrueType (Type 42) fonts in PDF and PS, no Type 3 (arXiv)
from matplotlib.lines import Line2D
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # paper repo root
OUT = os.path.join(ROOT, "evidence", "v3.13", "single-grid"); FIG = os.path.join(ROOT, "figures", "single_grid")
cells = {c["cell"]: c for c in json.load(open(os.path.join(OUT, "cells.json")))["cells"]}
# the leak these figures plot is the total leak (decision plus refusal-channel leak, echoes excluded)
TDC = json.load(open(os.path.join(ROOT, "evidence", "v3.14", "total-disclosure", "pair1_cells.json")))["cells"]
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
from halfup import fixed  # noqa: E402

INK, INK2, MUTED, GRID = "#1f2328", "#57606a", "#8b949e", "#e6e8eb"
MODEL_COLOR = {"ds41": "#2a78d6", "glm": "#eb6834", "luna": "#1baf7a"}
MODEL_NAME = {"ds41": "DeepSeek V4.1", "glm": "GLM-5.3-Flash", "luna": "GPT-5.6"}   # glossary v2
REQ_NAME = {"R0": "R0 stranger", "R1": "R1 colleague", "R2": "R2 CEO's assistant", "R3": "R3 close friend"}
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 9, "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "xtick.major.size": 0, "ytick.major.size": 0,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "white", "savefig.facecolor": "white", "pdf.fonttype": 42, "svg.fonttype": "none",
})

def r(cell, m):
    v = cells[cell]["recovered"][m]; return v["numerator"], v["denominator"], (None if v["value"] is None else v["value"] * 100)
def ci(cell, m):
    k, n, v = r(cell, m)
    if v is None: return None, None, None
    lo, hi = wilson(k, n); return v, max(0.0, v - lo * 100), max(0.0, hi * 100 - v)
def tl_ci(cell):
    """Total leak (%) of a cell under the relationship labels, with its 95% Wilson interval as (v, lo-gap, hi-gap)."""
    a = TDC[cell]["relationship"]; k, n = a["TD"], a["n"]
    v = 100 * k / n; lo, hi = wilson(k, n); return v, max(0.0, v - lo * 100), max(0.0, hi * 100 - v)
def save(fig, name):
    for ext in ("pdf", "png", "svg"): fig.savefig(os.path.join(FIG, f"{name}.{ext}"), dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig); print("wrote", name)

# ---------------- Figure 1: policy ladder, three models, per requester ----------------
def fig_ladder():
    """Small multiples: one column per requester, one row per metric; three responder models as thin lines.
    Whiskers are 95% Wilson intervals; the D2 end of every line is labelled directly (values in ink, never in the series colour)."""
    import matplotlib.patheffects as pe
    pols = ["D0", "D1", "D2"]; reqs = ["R0", "R1", "R2", "R3"]; fams = ["ds41", "glm", "luna"]
    metrics = [("leakRate", "Leak on protected QA (%)", 100, [0, 25, 50, 75, 100], 6.5), ("falseRefusalRate", "False refusal on entitled items (%)", 75, [0, 20, 40, 60], 5.0)]
    fig, axes = plt.subplots(2, 4, figsize=(7.1, 4.3), sharex=True, sharey="row")
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    for i, (m, ylabel, top, ticks, gap) in enumerate(metrics):
        for j, req in enumerate(reqs):
            ax = axes[i, j]
            if req == "R0" and m == "falseRefusalRate":
                ax.axis("off")
                ax.text(0.5, 0.55, "one entitled item;\nfalse refusal\nnot reported", ha="center", va="center", fontsize=7.5, color=MUTED, transform=ax.transAxes)
                continue
            ax.axvspan(1.62, 2.55, color="#f3f4f6", zorder=0, lw=0)  # the relationship-aware rung
            ends = []
            for k, fam in enumerate(fams):
                xs = np.arange(3) + (k - 1) * 0.06
                vals, lo, hi = zip(*[ci(f"{fam}-{p.lower()}-{req.lower()}", m) for p in pols])
                ax.errorbar(xs, vals, yerr=[lo, hi], color=MODEL_COLOR[fam], lw=0, elinewidth=0.7, capsize=0, alpha=0.45, zorder=2)
                ax.plot(xs, vals, color=MODEL_COLOR[fam], lw=1.5, solid_capstyle="round", solid_joinstyle="round", zorder=3 + k)
                ax.plot(xs, vals, ls="none", marker="o", ms=5.2, mfc=MODEL_COLOR[fam], mec="white", mew=1.1, zorder=6 + k)
                ends.append([vals[2], fam])
            # direct labels at the D2 end, pushed apart only as far as needed
            ends.sort(key=lambda e: e[0]); ys = [e[0] for e in ends]
            for t in range(1, len(ys)): ys[t] = max(ys[t], ys[t - 1] + gap)
            over = ys[-1] - (top - 1)
            if over > 0: ys = [y - over for y in ys]
            for (v, fam), y in zip(ends, ys):
                ax.text(2.2, y, f"{v:.1f}", ha="left", va="center", fontsize=6.8, color=INK2, path_effects=halo, zorder=9)
            bottom = (i == 1) or (req == "R0")
            ax.set_xticks(range(3)); ax.set_xticklabels(["D0\nnone", "D1\ngeneric", "D2\nrelation-\nship"] if bottom else ["", "", ""])
            if bottom: ax.tick_params(axis="x", labelbottom=True)
            ax.set_ylim(-2, top); ax.set_yticks(ticks); ax.set_xlim(-0.3, 2.55)
            ax.grid(axis="x", visible=False); ax.grid(axis="y", color="#ececec", lw=0.6)
            for sp in ax.spines.values(): sp.set_visible(False)
            if i == 0:
                ax.set_title(REQ_NAME[req], loc="left", fontsize=9, color=INK, pad=14)
                npro = r(f"ds41-d2-{req.lower()}", "leakRate")[1]; nent = r(f"ds41-d2-{req.lower()}", "falseRefusalRate")[1]
                sub = f"{npro} protected items" if req == "R0" else f"{npro} protected · {nent} entitled"
                ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=6.8, color=MUTED, ha="left", va="bottom")
            if (i == 0 and j == 0) or (i == 1 and j == 1):
                ax.set_ylabel(ylabel, labelpad=5, fontsize=8); ax.tick_params(axis="y", labelleft=True)
            ax.tick_params(axis="y", pad=2, labelsize=7.5); ax.tick_params(axis="x", labelsize=7.5)
    handles = [Line2D([0], [0], color=MODEL_COLOR[f], lw=1.5, marker="o", ms=5.2, mec="white", mew=1.1, label=MODEL_NAME[f]) for f in fams]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.02), handlelength=2.0, columnspacing=1.8, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.955), h_pad=1.2, w_pad=0.9)
    save(fig, "single_ladder")

# ---------------- Figure 2: operating points of all seven policies ----------------
def fig_operating_points():
    """Every policy as an operating point: total leak (x) against false refusal (y), the axes of Figure 3; D0, D1 and D2
    keep Figure 3's markers (circle, square, triangle)."""
    pols = ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]; reqs = ["R1", "R2", "R3"]
    style = {"D0": dict(color="#57606a", marker="o", fill=True), "D1": dict(color="#eb6834", marker="s", fill=False), "D6": dict(color="#eb6834", marker="D", fill=False),
             "D2": dict(color="#2a78d6", marker="^", fill=True), "D3": dict(color="#2a78d6", marker="v", fill=False), "D4": dict(color="#2a78d6", marker="P", fill=False), "D5": dict(color="#2a78d6", marker="X", fill=False)}
    fig, axes = plt.subplots(3, 3, figsize=(5.5, 5.6), sharex=True, sharey="row")   # text width: labels print at >= 7 pt
    for i, fam in enumerate(["ds41", "glm", "luna"]):
        for j, req in enumerate(reqs):
            ax = axes[i, j]; pt = {}
            for p in pols:
                cell = f"{fam}-{p.lower()}-{req.lower()}"
                x, xlo, xhi = tl_ci(cell); y, ylo, yhi = ci(cell, "falseRefusalRate")
                st = style[p]; pt[p] = (x, y)
                ax.errorbar(x, y, xerr=[[xlo], [xhi]], yerr=[[ylo], [yhi]], fmt="none", ecolor=st["color"], elinewidth=0.6, alpha=0.45, capsize=0, zorder=2)
                ax.plot(x, y, marker=st["marker"], ms=6, color=st["color"], mfc=st["color"] if st["fill"] else "white", mec=st["color"], mew=1.3, ls="none", zorder=3)
            # no direct labels: in the tight D2 cluster they collide at the text width; the legend maps the markers
            ax.set_xlim(-4, 100); ax.set_ylim(-4, 88)
            if i == 0: ax.set_title(REQ_NAME[req], loc="left", fontsize=8, pad=5)
            if j == 0: ax.set_ylabel(f"{MODEL_NAME[fam]}\nfalse refusal (%)", fontsize=7.5)
            if i == 2: ax.set_xlabel("total leak (%)", fontsize=7.5)
            ax.tick_params(labelsize=7)
    handles = [Line2D([0], [0], ls="none", marker="o", ms=6, color="#57606a", label="D0 no policy"),
               Line2D([0], [0], ls="none", marker="s", ms=6, color="#eb6834", mfc="white", mew=1.3, label="D1 generic caution"),
               Line2D([0], [0], ls="none", marker="D", ms=6, color="#eb6834", mfc="white", mew=1.3, label="D6 length control"),
               Line2D([0], [0], ls="none", marker="^", ms=6, color="#2a78d6", label="D2 relationship policy"),
               Line2D([0], [0], ls="none", marker="v", ms=6, color="#2a78d6", mfc="white", mew=1.3, label="D3 D2 + spotlighting"),
               Line2D([0], [0], ls="none", marker="P", ms=6, color="#2a78d6", mfc="white", mew=1.3, label="D4 D2 + instruction hierarchy"),
               Line2D([0], [0], ls="none", marker="X", ms=6, color="#2a78d6", mfc="white", mew=1.3, label="D5 D2 + sandwich")]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.07), handlelength=1.4, columnspacing=1.0, fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.95), h_pad=0.6, w_pad=0.6)
    save(fig, "single_operating_points")

# ---------------- Figure 3: disclosure follows the responder ----------------
def fig_responder_side():
    pols = ["D0", "D1", "D2"]; reqs = ["R1", "R2", "R3"]
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.9), sharey=True)
    panels = [("ds41", "xC", "codex", "Responder: DeepSeek V4.1"), ("glm", "xD", None, "Responder: GLM-5.3-Flash")]
    for ax, (same, cross, codex, title) in zip(axes, panels):
        groups = [(p, q) for q in reqs for p in pols]
        xs = np.arange(len(groups)) + np.repeat([0, 0.6, 1.2], 3)  # gap between requester blocks
        for x, (p, q) in zip(xs, groups):
            a = f"{same}-{p.lower()}-{q.lower()}"; b = f"{cross}-{p.lower()}-{q.lower()}"
            ya, ylo_a, yhi_a = tl_ci(a); yb, ylo_b, yhi_b = tl_ci(b)
            xa, xb = x - 0.13, x + 0.13
            ax.plot([xa, xb], [ya, yb], color="#c9ced4", lw=1.4, zorder=1)
            req_same = "ds41" if same == "ds41" else "glm"; req_cross = "glm" if same == "ds41" else "ds41"
            ax.errorbar(xa, ya, yerr=[[ylo_a], [yhi_a]], fmt="o", ms=5.5, color=MODEL_COLOR[req_same], mec="white", mew=1.0, elinewidth=0.8, capsize=0, zorder=3)
            ax.errorbar(xb, yb, yerr=[[ylo_b], [yhi_b]], fmt="o", ms=5.5, color=MODEL_COLOR[req_cross], mec="white", mew=1.0, elinewidth=0.8, capsize=0, zorder=3)
            if codex and p == "D2":
                c = f"{codex}-{p.lower()}-{q.lower()}"
                if c in cells:
                    yc = tl_ci(c)[0]
                    ax.plot(x + 0.42, yc, marker="D", ms=5.5, color=MODEL_COLOR["ds41"], mfc="white", mew=1.3, ls="none", zorder=4)
        ax.set_xticks(xs); ax.set_xticklabels([p for p, _ in groups])
        for k, q in enumerate(reqs):
            ax.text(xs[3 * k + 1], -13, REQ_NAME[q], ha="center", va="top", fontsize=8, color=INK2, clip_on=False)
        ax.set_title(title, loc="left", fontsize=9, pad=6); ax.set_ylim(-2, 95); ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Total leak on protected questions (%)")
    handles = [Line2D([0], [0], ls="none", marker="o", ms=6, color=MODEL_COLOR["ds41"], mec="white", label="requester driven by DeepSeek"),
               Line2D([0], [0], ls="none", marker="o", ms=6, color=MODEL_COLOR["glm"], mec="white", label="requester driven by GLM"),
               Line2D([0], [0], ls="none", marker="D", ms=5.5, color=MODEL_COLOR["ds41"], mfc="white", mew=1.3, label="responder in Codex CLI harness (D2)")]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.06), fontsize=7.8, columnspacing=1.4)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94), w_pad=1.0)
    save(fig, "single_responder_side")

# ---------------- Figure 4: delivery heatmap ----------------
def fig_delivery():
    """Figure 4: scored tasks per cell. Two rows of panels at the text width so every label prints at 7 pt; label
    colour from the cell's luminance; Codex's unrun cells say so."""
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    cmap = LinearSegmentedColormap.from_list("blue_seq", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"])
    norm = Normalize(vmin=88, vmax=100)
    seven = ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]
    rows = [[("ds41", "DeepSeek V4.1", seven), ("glm", "GLM-5.3-Flash", seven)],
            [("luna", "GPT-5.6 (Azure)", seven), ("xC", "DeepSeek" + r"$\to$" + "GLM", ["D0", "D1", "D2"]),
             ("xD", "GLM" + r"$\to$" + "DeepSeek", ["D0", "D1", "D2"]), ("codex", "Codex CLI", ["D2"])]]
    fig = plt.figure(figsize=(5.5, 3.9))
    outer = fig.add_gridspec(2, 2, width_ratios=[1, 0.025], hspace=0.42, wspace=0.03, left=0.06, right=0.93, top=0.93, bottom=0.07)
    reqs = ["R0", "R1", "R2", "R3"]
    for r, row in enumerate(rows):
        inner = outer[r, 0].subgridspec(1, len(row), width_ratios=[max(len(f[2]), 1.6) for f in row], wspace=0.12)
        for c, (fam, name, pols) in enumerate(row):
            ax = fig.add_subplot(inner[c])
            M = np.full((4, len(pols)), np.nan); Rc = np.zeros((4, len(pols)), dtype=int)
            for jj, pp in enumerate(pols):
                for ii, q in enumerate(reqs):
                    k = f"{fam}-{pp.lower()}-{q.lower()}"
                    if k in cells:
                        M[ii, jj] = cells[k]["scoredWithRecovery"] / 6.0; Rc[ii, jj] = cells[k]["recoveredQa"]
            ax.imshow(np.ma.masked_invalid(M), cmap=cmap, norm=norm, aspect="auto")
            for ii in range(4):
                for jj in range(len(pols)):
                    if np.isnan(M[ii, jj]):
                        ax.text(jj, ii, "not\nrun", ha="center", va="center", fontsize=7, color=MUTED, linespacing=0.9)
                        continue
                    k = f"{fam}-{pols[jj].lower()}-{reqs[ii].lower()}"
                    txt = fixed(Fraction(cells[k]["scoredWithRecovery"], 6), 0) + (f"\n+{Rc[ii, jj]}" if Rc[ii, jj] >= 5 else "")
                    rr, gg, bb, _ = cmap(norm(M[ii, jj]))
                    lum = 0.2126 * rr + 0.7152 * gg + 0.0722 * bb   # dark text on light cells, white on dark
                    ax.text(jj, ii, txt, ha="center", va="center", fontsize=7, color=INK if lum > 0.55 else "white", linespacing=0.85)
            ax.set_xticks(range(len(pols))); ax.set_xticklabels(pols, fontsize=7)
            ax.set_yticks(range(4)); ax.set_yticklabels(reqs if c == 0 else [], fontsize=7)
            ax.set_title(name, loc="left", fontsize=7.5, pad=3); ax.grid(False)
            for sp in ax.spines.values(): sp.set_visible(False)
    cax = fig.add_subplot(outer[:, 1])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
    cb = fig.colorbar(sm, cax=cax); cb.set_label("scored tasks (%) of 600", fontsize=7); cb.ax.tick_params(labelsize=7); cb.outline.set_visible(False)
    save(fig, "single_delivery")

if __name__ == "__main__":
    # fig_ladder() draws single_ladder.*, which no section includes; it is left as it was (decision leak).
    fig_operating_points(); fig_responder_side(); fig_delivery()
