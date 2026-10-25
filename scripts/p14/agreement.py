#!/usr/bin/env python3
"""Relationship labels: agreement of the five annotation passes, reported on the requesters the experiments use.

Input: evidence/v3.14/labels/annotation_passes.csv (five passes A1-A4 and E, one row per annotated row and requester;
2,005 cells = 401 rows x R0-R4), and the label file for each task's category.

Statistics, for a set of cells each rated by the same passes:
  Fleiss' kappa      (Pbar - Pe) / (1 - Pe), Pe = sum_k p_k^2 (undefined when every rating falls in one category);
  Gwet's AC1         (Pbar - pe) / (1 - pe), pe = sum_k p_k (1 - p_k) / (q - 1), q = the categories of the label
                     scale (2 for questions, P/L; 2 for actions, REFUSE/EXECUTE), whether or not both occur;
  raw agreement      Pbar, the mean over cells of the share of agreeing pairs of passes (10 pairs per cell);
  prevalence         the share of ratings that protect (P or REFUSE).
Scopes: primary R0-R3, the four requesters the experiments use; secondary R0-R4, all five personas (R4 enters
no experiment); each requester; each category (R0-R3 and R0-R4); without E. "Combined" pools questions and actions on
the binary scale protect (P, REFUSE) against permit (L, EXECUTE). The pooling as four categories (P, L, REFUSE, EXECUTE)
is also given, labelled, because an earlier figure used it: it counts the question/action split, which every
pass gets right by construction, as agreement, so it sits above both of its parts.

Checks (the script stops on a mismatch): all-persona kappa equals documentation.json (0.587 questions, 0.764 actions);
the independently computed figures of 2026-10-23 (REFERENCE) reproduce at three decimals.
Outputs: evidence/v3.14/labels/agreement.json, evidence/v3.14/labels/agreement_macros.json,
         tables/label_agreement_numbers.tex (\\agreenum{key}), tables/label_agreement.tex.
Printing: every statistic is a ratio of counts, so the table and the macros print it from its exact fraction, rounded
half away from zero; agreement.json keeps the floating-point values, checked against the fractions.
Usage: python3 scripts/p14/agreement.py
"""
import collections
import csv
import json
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed  # noqa: E402

L = ROOT / "evidence/v3.14/labels"
LAB = ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json"
TEX = ROOT / "tables/label_agreement_numbers.tex"
PASSES = ("A1", "A2", "A3", "A4", "E")
SCALE = {"qa": ("P", "L"), "action": ("REFUSE", "EXECUTE")}
PROTECT = {"P", "REFUSE", "protect"}  # "protect" is the binary scale of the pooled figure
USED = ("R0", "R1", "R2", "R3")
ALL = ("R0", "R1", "R2", "R3", "R4")
REFERENCE = {  # computed independently on 2026-10-23, three decimals
    ("R0-R3", "qa"): {"kappa": 0.708, "ac1": 0.735, "raw": 0.861},
    ("R0-R3", "action"): {"kappa": 0.739, "ac1": 0.768, "raw": 0.877},
    ("R0-R3", "combined-4cat"): {"kappa": 0.799, "ac1": 0.826, "raw": 0.865},
    ("R0-R4", "qa"): {"kappa": 0.587}, ("R0-R4", "action"): {"kappa": 0.764},
    ("R4", "qa"): {"kappa": 0.045, "raw": 0.589},
    ("R0", "qa"): {"kappa": 0.118, "ac1": 0.928}, ("R1", "qa"): {"kappa": 0.641, "ac1": 0.693},
    ("R2", "qa"): {"kappa": 0.696, "ac1": 0.782}, ("R3", "qa"): {"kappa": 0.316, "ac1": 0.724},
}


def stats(cells, cats):
    """cells: lists of ratings (same raters); cats: the label scale. The floats go to agreement.json; "_exact" holds
    the same statistics as fractions, for printing (stripped from the JSON)."""
    n, N = len(cells[0]), len(cells)
    p = {k: sum(c.count(k) for c in cells) / (N * n) for k in cats}
    assert abs(sum(p.values()) - 1) < 1e-12, "a rating outside the scale"
    pbar = sum((sum(c.count(k) ** 2 for k in cats) - n) / (n * (n - 1)) for c in cells) / N
    pe_k = sum(v * v for v in p.values())
    pe_g = sum(v * (1 - v) for v in p.values()) / (len(cats) - 1)
    out = {"cells": N, "raters": n, "kappa": None if pe_k >= 1 else (pbar - pe_k) / (1 - pe_k),
           "ac1": (pbar - pe_g) / (1 - pe_g), "raw": pbar,
           "prevalence_protect": sum(v for k, v in p.items() if k in PROTECT),
           "ratings": N * n, "ratings_protect": sum(c.count(k) for c in cells for k in PROTECT if k in cats),
           "unanimous": sum(len(set(c)) == 1 for c in cells)}
    fp = {k: Fraction(sum(c.count(k) for c in cells), N * n) for k in cats}
    fbar = sum(Fraction(sum(c.count(k) ** 2 for k in cats) - n, n * (n - 1)) for c in cells) / N
    fe_k = sum(v * v for v in fp.values())
    fe_g = sum(v * (1 - v) for v in fp.values()) / (len(cats) - 1)
    ex = {"kappa": None if fe_k >= 1 else (fbar - fe_k) / (1 - fe_k), "ac1": (fbar - fe_g) / (1 - fe_g), "raw": fbar,
          "prevalence_protect": Fraction(out["ratings_protect"], N * n)}
    for k, v in ex.items():
        assert (v is None) == (out[k] is None) and (v is None or abs(float(v) - out[k]) < 1e-12), (k, v, out[k])
    out["_exact"] = ex
    return out


def strip(x):
    """The JSON form: every "_exact" block removed."""
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k != "_exact"}
    return [strip(v) for v in x] if isinstance(x, list) else x


def main():
    lab = json.loads(LAB.read_text())
    cat = {**{f"Q{q['id']}": q["category"] for q in lab["questions"]},
           **{f"A{a['id']}": a["category"] for a in lab["actions"]}}
    cells = [(r["row"], r["kind"], r["requester"], [r[p] for p in PASSES])
             for r in csv.DictReader(open(L / "annotation_passes.csv"))]
    assert len(cells) == 2005

    def pick(reqs, kind=None, category=None, drop_e=False, mode=None):
        out = []
        for row, k, r, labs in cells:
            if r not in reqs or (kind and k != kind) or (category and cat[row] != category):
                continue
            labs = labs[:4] if drop_e else labs
            if mode == "binary":
                labs = ["protect" if x in PROTECT else "permit" for x in labs]
            out.append(labs)
        return out

    def block(reqs, drop_e=False):
        b = {k: stats(pick(reqs, k, drop_e=drop_e), SCALE[k]) for k in ("qa", "action")}
        b["combined"] = stats(pick(reqs, drop_e=drop_e, mode="binary"), ("protect", "permit"))
        b["combined-4cat"] = stats(pick(reqs, drop_e=drop_e), ("P", "L", "REFUSE", "EXECUTE"))
        return b

    out = {"input": "evidence/v3.14/labels/annotation_passes.csv", "passes": list(PASSES),
           "primary": {"requesters": list(USED), "why": "the four requesters the experiments use; R4 enters "
                                                         "no experiment", **block(USED)},
           "secondary_all_personas": {"requesters": list(ALL), **block(ALL)},
           "by_requester": {r: {k: stats(pick((r,), k), SCALE[k]) for k in ("qa", "action")} for r in ALL},
           "by_category": {}, "without_E": {"R0-R3": block(USED, True), "R0-R4": block(ALL, True)}}
    for scope, reqs in (("R0-R3", USED), ("R0-R4", ALL)):
        for kind in ("qa", "action"):
            for c in sorted({cat[row] for row, k, _, _ in cells if k == kind}):
                out["by_category"][f"{scope}/{kind}/{c}"] = stats(pick(reqs, kind, c), SCALE[kind])

    doc = json.loads((L / "documentation.json").read_text())["fleiss_kappa"]
    assert abs(out["secondary_all_personas"]["qa"]["kappa"] - doc["questions"]) < 1e-12
    assert abs(out["secondary_all_personas"]["action"]["kappa"] - doc["actions"]) < 1e-12
    look = {"R0-R3": out["primary"], "R0-R4": out["secondary_all_personas"], **out["by_requester"]}
    for (scope, kind), want in REFERENCE.items():
        got = look[scope][kind]
        for stat, v in want.items():
            assert fixed(got[stat], 3) == f"{v:.3f}", (scope, kind, stat, got[stat], v)
    out["reference_figures_reproduced"] = {f"{s} {k}": v for (s, k), v in REFERENCE.items()}
    out["note_combined"] = ("'combined' is the binary scale protect/permit. 'combined-4cat' keeps P, L, REFUSE and "
                            "EXECUTE apart; it is the earlier figure (0.799 / 0.826 / 0.865) and counts the "
                            "question/action split, agreed by construction, as agreement. Use 'combined' if a pooled "
                            "figure is printed.")
    (L / "agreement.json").write_text(json.dumps(strip(out), indent=1) + "\n")
    macros(out)
    table(out)


def table(out):
    """tables/label_agreement.tex (tab:label-agreement): by scope, by requester and by category (R0-R3)."""
    def math(x):
        return "--" if x is None else f"${fixed(x, 3)}$"

    def row(name, s):
        cells, e = f"{s['cells']:,}".replace(",", "{,}"), s["_exact"]
        return (f"{name} & {cells} & {math(e['kappa'])} & {math(e['ac1'])} & {math(e['raw'])} & "
                f"${fixed(100 * e['prevalence_protect'], 1)}$ \\\\")
    kinds = (("qa", "Questions"), ("action", "Actions"))
    req = {"R0": "R0 stranger", "R1": "R1 colleague", "R2": "R2 CEO's asst.", "R3": "R3 close friend",
           "R4": "R4 (in no experiment)"}
    L = [r"\begin{table}[H]", r"\centering\small",
         r"\caption{\textbf{Agreement of the five label passes.} Fleiss' $\kappa$, Gwet's AC1 and raw agreement (the mean "
         r"share of agreeing pairs of passes) behind the relationship labels. R0--R3 are the four requesters the "
         r"experiments use; R4 enters no experiment. Protect: the share of ratings that protect (P or REFUSE). "
         r"$\kappa$ is undefined (--) where every rating falls in one category.}",
         r"\label{tab:label-agreement}", r"\setlength{\tabcolsep}{4pt}", r"\renewcommand{\arraystretch}{1.05}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrr@{}}", r"\toprule",
         r"Cells rated by all five passes & Cells & $\kappa$ & AC1 & Raw & Protect (\%) \\", r"\midrule",
         r"\multicolumn{6}{@{}l}{\textit{R0--R3 (primary)}} \\"]
    for k, name in kinds + (("combined", "Both, protect vs permit"),):
        L.append(row(name, out["primary"][k]))
    L += [r"\addlinespace[2pt]", r"\multicolumn{6}{@{}l}{\textit{R0--R4, all five personas}} \\"]
    for k, name in kinds + (("combined", "Both, protect vs permit"),):
        L.append(row(name, out["secondary_all_personas"][k]))
    for k, name in kinds:
        L += [r"\addlinespace[2pt]", f"\\multicolumn{{6}}{{@{{}}l}}{{\\textit{{{name}, by requester}}}} \\\\"]
        for r, label in req.items():
            L.append(row(label, out["by_requester"][r][k]))
    for k, name in kinds:
        L += [r"\addlinespace[2pt]", f"\\multicolumn{{6}}{{@{{}}l}}{{\\textit{{{name}, by category (R0--R3)}}}} \\\\"]
        for key, s in sorted(out["by_category"].items(), key=lambda kv: -kv[1]["cells"]):
            scope, kind, c = key.split("/")
            if scope == "R0-R3" and kind == k:
                L.append(row(c.replace("_", r"\_"), s))
    L += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    out_path = ROOT / "tables/label_agreement.tex"
    out_path.write_text("% Generated by scripts/p14/agreement.py from evidence/v3.14/labels/annotation_passes.csv. Do not edit.\n"
                        + "\n".join(L) + "\n")
    print("wrote", out_path.relative_to(ROOT))


def k3(x):
    return "--" if x is None else fixed(x, 3).replace("-", "$-$")


def k2(x):
    return "--" if x is None else fixed(x, 2).replace("-", "$-$")


def macros(out):
    m = {}

    def put(prefix, s):
        e = s["_exact"]
        m[f"{prefix}-kappa"], m[f"{prefix}-kappa2"] = k3(e["kappa"]), k2(e["kappa"])
        m[f"{prefix}-ac1"], m[f"{prefix}-ac12"] = k3(e["ac1"]), k2(e["ac1"])
        m[f"{prefix}-raw"], m[f"{prefix}-rawpct"] = k3(e["raw"]), fixed(100 * e["raw"], 1)
        m[f"{prefix}-prev"] = fixed(100 * e["prevalence_protect"], 1)
        m[f"{prefix}-n"] = f"{s['cells']:,}".replace(",", "{,}")
        m[f"{prefix}-votes"] = f"{s['ratings']:,}".replace(",", "{,}")
        m[f"{prefix}-protvotes"] = f"{s['ratings_protect']:,}".replace(",", "{,}")
        m[f"{prefix}-protvotes-of"] = f"{m[prefix + '-protvotes']} of {m[prefix + '-votes']}"

    short = {"qa": "qa", "action": "act", "combined": "comb", "combined-4cat": "comb4"}
    for scope, b in (("r03", out["primary"]), ("all", out["secondary_all_personas"]),
                     ("noE-r03", out["without_E"]["R0-R3"]), ("noE-all", out["without_E"]["R0-R4"])):
        for kind, s in short.items():
            put(f"{scope}-{s}", b[kind])
    for r, b in out["by_requester"].items():
        for kind in ("qa", "action"):
            put(f"{r}-{short[kind]}", b[kind])
    for key, s in out["by_category"].items():
        scope, kind, c = key.split("/")
        put(f"cat{'' if scope == 'R0-R3' else 'all'}-{short[kind]}-{c.replace('_', '')}", s)
    (L / "agreement_macros.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    body = [f"\\expandafter\\def\\csname agree@{k}\\endcsname{{{v}}}" for k, v in sorted(m.items())]
    TEX.write_text("% Generated by scripts/p14/agreement.py from evidence/v3.14/labels/annotation_passes.csv. Do not edit.\n"
                   "% Use \\agreenum{key}; keys and values in evidence/v3.14/labels/agreement_macros.json. "
                   "Primary scope r03 (R0-R3, the requesters the experiments use); all = R0-R4.\n"
                   + "\n".join(body) + "\n"
                   "\\providecommand{\\agreenum}[1]{\\ifcsname agree@#1\\endcsname\\csname agree@#1\\endcsname"
                   "\\else\\textbf{??}\\fi}\n")
    p, s = out["primary"], out["secondary_all_personas"]
    print("R0-R3  questions kappa %.3f AC1 %.3f raw %.3f | actions %.3f %.3f %.3f | combined %.3f %.3f %.3f"
          % tuple(x for k in ("qa", "action", "combined") for x in (p[k]["kappa"], p[k]["ac1"], p[k]["raw"])))
    print("R0-R4  questions kappa %.3f AC1 %.3f raw %.3f | actions %.3f %.3f %.3f"
          % tuple(x for k in ("qa", "action") for x in (s[k]["kappa"], s[k]["ac1"], s[k]["raw"])))
    print("wrote", TEX.relative_to(ROOT), "with", len(m), "keys")


if __name__ == "__main__":
    main()
