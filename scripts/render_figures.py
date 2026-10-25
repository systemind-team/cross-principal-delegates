#!/usr/bin/env python3
"""Rebuild the manuscript's vector figures from the frozen evidence summary.

The schematic distinguishes communication, authorization and the evaluated outcomes (utility, leak, mutation).
The paired bars report pooled observed rates, with error-excluded denominators.
They are a historical structural-scope comparison, not current-kernel validation.

Usage: python3 scripts/render_figures.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence" / "notes_scope_source.json"
OUT = ROOT / "figures"
MANIFEST = ROOT / "evidence" / "figure_manifest.json"
BLUE = "#386C9C"
BLUE_LIGHT = "#EDF3F8"
GOLD = "#B78328"
GOLD_LIGHT = "#FCF5E9"
OS_NAME, EVAL_NAME = "AnonOS", "AnonEval"  # review copy; camera-ready: "SharedOS", "SharedEval"
INK = "#26323C"
GRAY = "#697784"
LIGHT = "#DCE2E6"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.7,
    "axes.edgecolor": GRAY,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, name: str) -> dict:
    """Preserve exact final dimensions and vector text; also emit a PNG preview."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    for label in fig.findobj(match=matplotlib.text.Text):
        if not label.get_visible() or not label.get_text():
            continue
        box = label.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > canvas.width + 1 or box.y1 > canvas.height + 1:
            raise ValueError(f"Text outside {name} canvas: {label.get_text()!r}")
    exports = {}
    for fmt in ("pdf", "svg", "png"):
        path = OUT / f"{name}.{fmt}"
        fig.savefig(path, dpi=300, metadata={"Creator": "scripts/render_figures.py"} if fmt != "png" else None)
        exports[str(path.relative_to(ROOT))] = {"sha256": sha256(path)}
    size = list(fig.get_size_inches())
    plt.close(fig)
    return {"dimensions_inches": size, "minimum_label_size_pt": 9, "exports": exports}


def box(ax, x, y, w, h, label, *, face="white", edge=LIGHT, weight="normal", size=9):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05",
        linewidth=0.8, edgecolor=edge, facecolor=face, zorder=3,
    ))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=size, fontweight=weight, linespacing=1.35, zorder=4)


def arrow(ax, start, end, color=GRAY, *, path=None, style="-|>", width=1.2):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle=style, mutation_scale=9, linewidth=width,
        color=color, shrinkA=0, shrinkB=0,
        connectionstyle=path or "arc3", zorder=2,
    ))


def delegation_overview() -> dict:
    """Show the study workflow without implying an integrated empirical result.

    SharedEval defines scenarios and outcome rules; the central SharedOS panel
    makes separate owners, interchangeable drivers and checked execution visible.
    """
    # The canvas starts just below the panels (y = 0.30); a caption line under them was dropped
    # in review (10-04) as saying nothing the paper's caption does not.
    fig = plt.figure(figsize=(6, 2.38))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 6), ylim=(0.22, 2.6))
    ax.axis("off")

    # Three stages, with most space assigned to the actual delegate interaction.
    panels = ((0.04, 1.32), (1.54, 2.96), (4.70, 1.26))
    for x, w in panels:
        ax.add_patch(FancyBboxPatch(
            (x, 0.30), w, 1.89, boxstyle="round,pad=0,rounding_size=0.06",
            facecolor="white", edgecolor=LIGHT, linewidth=0.8, zorder=0,
        ))
    for x, title in ((0.70, "1  Configure"), (3.02, "2  Interact"), (5.33, "3  Evaluate")):
        ax.text(x, 2.39, title, fontsize=10, fontweight="bold", ha="center", va="center")
    arrow(ax, (1.16, 2.39), (2.44, 2.39), GRAY, width=0.9)
    arrow(ax, (3.60, 2.39), (4.88, 2.39), GRAY, width=0.9)

    # Scenario registration is broader than benchmark prompts: it fixes the
    # world, participants, drivers and permissions for either pair or network.
    ax.text(0.70, 2.00, EVAL_NAME, fontsize=10, fontweight="bold", ha="center", color=BLUE)
    ax.text(0.70, 1.57, "Register scenarios\nTasks · state\nDrivers · tools\nOwner grants",
            ha="center", va="center", fontsize=9, linespacing=1.4)
    ax.plot([0.16, 1.24], [1.12, 1.12], color=LIGHT, linewidth=0.7)
    # PAIR and NET are concrete interaction topologies, not performance claims.
    for (x1, y1), (x2, y2) in [((0.26, .78), (.52, .78)),
                              ((.87, .68), (1.12, .70)),
                              ((.87, .68), (.93, .92)),
                              ((.93, .92), (1.17, .94)),
                              ((1.17, .94), (1.12, .70)),
                              ((.93, .92), (1.12, .70))]:
        ax.plot([x1, x2], [y1, y2], color=BLUE, linewidth=0.9, zorder=2)
    for x, y in ((.26, .78), (.52, .78), (.87, .68), (1.12, .70), (.93, .92), (1.17, .94)):
        ax.plot(x, y, "o", markersize=4.7, markerfacecolor=BLUE_LIGHT,
                markeredgecolor=BLUE, markeredgewidth=0.9, zorder=3)
    ax.text(.39, .44, "PAIR", ha="center", fontsize=9, fontweight="bold")
    ax.text(1.02, .44, "NET", ha="center", fontsize=9, fontweight="bold")

    ax.text(3.02, 2.00, OS_NAME, fontsize=10, fontweight="bold", ha="center", color=BLUE)
    for x, owner, delegate, driver in ((1.65, "Owner A", "Delegate A", "Driver A"),
                                       (3.21, "Owner B", "Delegate B", "Driver B")):
        ax.add_patch(FancyBboxPatch(
            (x, .96), 1.18, .89, boxstyle="round,pad=0,rounding_size=0.04",
            facecolor="#F7F9FA", edgecolor=LIGHT, linewidth=0.7, zorder=1,
        ))
        ax.text(x + .59, 1.70, owner, ha="center", va="center", fontsize=9, fontweight="bold")
        box(ax, x + .07, 1.19, 1.04, .35, f"{delegate}\n{driver}",
            face=BLUE_LIGHT, edge=BLUE)
        ax.text(x + .59, 1.05, "Knowledge · tools", ha="center", va="center", fontsize=9)
    arrow(ax, (2.84, 1.41), (3.20, 1.41), BLUE, width=1.2)
    arrow(ax, (3.20, 1.25), (2.84, 1.25), BLUE, width=1.2)
    ax.text(3.02, .78, "Message ≠ authority", ha="center", va="center", fontsize=9,
            fontweight="bold", color=GOLD)
    box(ax, 1.65, .39, 2.74, .27, "Owner grants → checked execution", face=GOLD_LIGHT,
        edge=GOLD, size=9)

    ax.text(5.33, 2.00, EVAL_NAME, fontsize=10, fontweight="bold", ha="center", color=BLUE)
    ax.text(5.33, 1.64, "Score traces +\nstate changes", ha="center", va="center",
            fontsize=9, linespacing=1.4)
    for y, label in ((1.17, "Utility"), (.84, "Leak"), (.51, "Mutation")):   # m = (U, L, M), glossary v2
        box(ax, 4.81, y, 1.04, .25, label, face=BLUE_LIGHT, edge=LIGHT, size=9)
    # The record path is distinct from agent-to-agent message exchange.
    arrow(ax, (4.40, 1.06), (4.69, 1.06), GRAY, width=1.1)

    result = save(fig, "delegation_overview")
    result.update({
        "kind": "conceptual schematic",
        "claim": "Researchers register PAIR or NET scenarios, run separately owned delegates under independently checked authority in SharedOS, and evaluate interaction traces and state changes through SharedEval.",
        "data_source": None,
        "implementation_boundary": "Conceptual framework relationship, not evidence that the historical PAIR/NET results have been rerun on the current SharedOS runtime. No integrated experiment, typed views or information-flow guarantee is claimed.",
        "reading_order": ["Configure: SharedEval scenario registration and PAIR/NET instances", "Interact: distinct owners, delegates, drivers and state/tools in SharedOS; messages do not grant authority", "Evaluate: SharedEval utility, leak and mutation outcomes"],
        "final_manuscript_width_inches": 5.5,
        "minimum_label_size_at_manuscript_width_pt": 8.25,
    })
    return result


def aggregate(summary: dict) -> dict:
    result = {}
    for condition in ("D3", "MCC_H_D3"):
        rows = [v for k, v in summary["conditions"][condition].items() if k.startswith("R")]
        counts = {
            "utility_numerator": sum(r["utility_correct"] for r in rows),
            "utility_denominator": sum(r["utility_total"] for r in rows),
            "disclosure_numerator": sum(r["security_leaked"] for r in rows),
            "disclosure_denominator": sum(r["security_total"] for r in rows),
            "errors": sum(r["errors"] for r in rows),
            "requester_conditions": len(rows),
        }
        for metric in ("utility", "disclosure"):
            n, d = counts[f"{metric}_numerator"], counts[f"{metric}_denominator"]
            if not 0 <= n <= d or d == 0:
                raise ValueError(f"Invalid {condition}/{metric} counts")
            counts[f"{metric}_percent"] = 100 * n / d
        result[condition] = counts
    return result


def scope_tradeoff(counts: dict) -> dict:
    fig, axes = plt.subplots(1, 2, figsize=(6, 2.4))
    fig.subplots_adjust(left=0.085, right=0.98, bottom=0.255, top=0.82, wspace=0.42)
    colors = (BLUE, GOLD)
    conditions = ("D3", "MCC_H_D3")
    labels = ("Policy", "Policy +\nscoped access")
    for ax, metric, title, upper, ticks, panel in zip(
        axes,
        ("utility", "disclosure"),
        ("Task utility (higher is better)", "P+B disclosure (lower is better)"),
        (100, 20),
        ([0, 25, 50, 75, 100], [0, 5, 10, 15, 20]),
        ("a", "b"),
    ):
        rates = [counts[c][f"{metric}_percent"] for c in conditions]
        ax.bar([0, 1], rates, width=0.50, color=colors, edgecolor="white", linewidth=0.5, zorder=3)
        ax.set_xticks([0, 1], labels)
        ax.tick_params(axis="x", length=0, pad=5)
        ax.tick_params(axis="y", length=3)
        ax.set(xlim=(-0.65, 1.65), ylim=(0, upper), yticks=ticks, ylabel="Observed rate (%)")
        ax.grid(axis="y", color=LIGHT, linewidth=0.55, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left", fontsize=9, pad=12)
        ax.text(-0.18, 1.15, panel, transform=ax.transAxes, fontsize=10, fontweight="bold")
        for index, condition in enumerate(conditions):
            row = counts[condition]
            n, d = row[f"{metric}_numerator"], row[f"{metric}_denominator"]
            ax.text(index, row[f"{metric}_percent"] + upper * 0.033,
                    f"{row[f'{metric}_percent']:.1f}%\n{n}/{d}",
                    ha="center", va="bottom", fontsize=9, linespacing=1.25)

    fig.text(0.5, 0.025, "Historical Notes QA · pooled counts · error-excluded denominators",
             ha="center", va="bottom", fontsize=9, color=GRAY)
    result = save(fig, "scope_tradeoff")
    result.update({
        "kind": "quantitative paired bars",
        "claim": "The documented scoped Notes condition (folder mounting plus an access notice, with the same base relationship policy) has lower disclosure and lower task utility. Exact loaded run prompts are not archived.",
        "data_source": str(SOURCE.relative_to(ROOT)),
        "aggregation": "Sum count numerators and error-excluded denominators over R0–R4, then divide; do not average requester percentages.",
        "metric_definitions": {
            "utility": "Correct answers to legitimate utility questions / evaluated utility questions, excluding errors.",
            "disclosure": "Disclosures on private or boundary questions (P+B) / evaluated private or boundary questions, excluding errors.",
        },
        "uncertainty": "Observed rates only; one run per requester-condition. No confidence intervals or significance claims.",
        "caveats": ["Historical implementation; not validation of the current SharedOS kernel.",
                    "Post-hoc folder scopes.", "Scoped runner adds an access notice; its separate effect is not isolated, and exact loaded run prompts are not archived.", "Different error-excluded denominators across conditions.",
                    "Reduced disclosure is accompanied by reduced utility; Pareto improvement is not established."],
        "derived_counts": counts,
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-origin", help="Original source path for the local provenance ledger")
    parser.add_argument("--only", choices=("overview", "tradeoff"), help="Rebuild one figure while preserving the other export hashes")
    args = parser.parse_args()
    summary = json.loads(SOURCE.read_text())
    counts = aggregate(summary)
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    origin = args.source_origin or previous.get("source", {}).get("original_path")
    figures = dict(previous.get("figures", {}))
    if args.only != "tradeoff":
        figures["delegation_overview"] = delegation_overview()
    if args.only != "overview":
        figures["scope_tradeoff"] = scope_tradeoff(counts)
    manifest = {
        "schema_version": 1,
        "generator": "scripts/render_figures.py",
        "generator_sha256": sha256(Path(__file__)),
        "backend": {"name": "Python/matplotlib", "matplotlib_version": matplotlib.__version__},
        "source": {
            "frozen_path": str(SOURCE.relative_to(ROOT)), "original_path": origin,
            "sha256": sha256(SOURCE), "benchmark": summary["benchmark"],
            "source_date": summary["date"], "source_model_field": summary["model"],
            "judge_model": summary["judge_model"],
        },
        "figures": figures,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    if args.only != "overview":
        print(json.dumps(counts, indent=2))
    print("Saved PDF, SVG, PNG figures and their provenance manifest.")


if __name__ == "__main__":
    main()
