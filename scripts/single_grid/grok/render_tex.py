#!/usr/bin/env python3
"""The grok-4.6 PAIR I supplement in the paper: one appendix table and the \\groknum{key} macros.

Reads only frozen files: evidence/v3.13/single-grid-grok/grok_supplement.json (analyze.py; reproduced byte for byte
by reproduce.py), run/{plan,retry}/rescore.json, run/{plan,retry}/scan.json, run/retry_list.json,
run/retry_list_merged.json, run/cost-all.json, trial/cost.json and design/run_plan.json.
Rates print half away from zero from their counts; every printed p is recomputed as an exact McNemar p from the
discordant counts and Holm-adjusted within its pre-registered family (F1 12 tests, F2 18, F3 6), and both are checked
against analyze.py's floats. Delivery is counted as render_results.py counts it, and checked against RESULTS.md.

Writes tables/single_grok.tex (tab:single-grok), tables/grok_numbers.tex (\\groknum{key}) and
evidence/v3.14/single-grid-grok/macros.json.
Usage: python3 scripts/single_grid/grok/render_tex.py
"""
import collections
import json
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, fmt_p_tex, mcnemar_p, pct  # noqa: E402

G = ROOT / "evidence/v3.13/single-grid-grok"
OUT = ROOT / "evidence/v3.14/single-grid-grok"
TAB = ROOT / "tables/single_grok.tex"
NUM = ROOT / "tables/grok_numbers.tex"
MODELS = ("ds41", "glm", "luna")
SHORT = {"ds41": "ds", "glm": "glm", "luna": "gpt", "grok": "grok"}
NAME = {"ds41": "DeepSeek V4.1", "glm": "GLM-5.3-Flash", "luna": "GPT-5.6", "grok": "Grok 4.6"}
REQ = {"R0": "R0 stranger", "R1": "R1 colleague", "R2": "R2 CEO's asst.", "R3": "R3 close friend"}
MET = {"total_leak": "tl", "fr": "fr"}


def load(*parts):
    return json.loads((G.joinpath(*parts)).read_text())


def n_(x):
    return f"{x:,}".replace(",", "{,}")


def p_plain(fr):
    """fmt_p_tex without the math delimiters, for use inside text macros: 0.32, 3.1\\times10^{-4}."""
    return fmt_p_tex(fr).strip("$")


def holm(ps):
    """Holm-adjusted p (exact Fractions) for a list of p, same order."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run, m = [None] * len(ps), Fraction(0), len(ps)
    for rank, i in enumerate(order):
        run = max(run, min(Fraction(1), (m - rank) * ps[i]))
        out[i] = run
    return out


def family(rows):
    """Exact p and Holm for one family; checked against analyze.py's floats."""
    ps = [mcnemar_p(t["a_only"], t["b_only"]) for t in rows]
    hs = holm(ps)
    for t, p, h in zip(rows, ps, hs):
        assert abs(float(p) - t["p"]) < 1e-12 and abs(float(h) - t["p_holm"]) < 1e-12, t
    return list(zip(rows, ps, hs))


def ex(pct_float, n, d=1):
    """analyze.py stores a rate as the float 100*k/n; the count k is recovered (and checked) and printed exactly."""
    k = round(pct_float * n / 100)
    assert abs(100 * k / n - pct_float) < 1e-9, (pct_float, n)
    return pct(k, n, d)


def exf(pct_float, n):
    """The exact Fraction behind a stored rate (to take minima and maxima before printing)."""
    k = round(pct_float * n / 100)
    assert abs(100 * k / n - pct_float) < 1e-9
    return Fraction(100 * k, n)


def rate(b):
    return "--" if not b or not b.get("n") else pct(b["k"], b["n"])


def main():
    o = load("grok_supplement.json")
    rel = o["random"]["relationship"]
    m = {}

    # ---------------------------------------------------------------- delivery (render_results.py's count)
    plan = load("design", "run_plan.json")
    plan_rep, retry_rep = load("run", "plan", "rescore.json")["cells"], load("run", "retry", "rescore.json")["cells"]
    listed, merged = load("run", "retry_list.json"), load("run", "retry_list_merged.json")
    tot, per_cell = collections.Counter(), []
    for cid in plan["cells"]:
        p = plan_rep[cid]["taskCounts"]
        scored = p["scored"] + p["recovery"]["recoveredQa"]
        if merged["cells"].get(cid):
            r = retry_rep[f"{cid}-retry"]["taskCounts"]
            scored += r["scored"] + r["recovery"]["recoveredQa"]
        tot.update(selected=p["selected"], scored=scored)
        per_cell.append(Fraction(scored, p["selected"]))
    results_md = (G / "RESULTS.md").read_text()
    assert f"{tot['scored']:,} of {tot['selected']:,} task-runs reached a score" in results_md
    cost, trial = load("run", "cost-all.json"), load("trial", "cost.json")
    spend = sum(t["usd"]["data_zone"] for t in cost["taskRuns"]) + sum(t["usd"]["data_zone"] for t in trial["taskRuns"])
    assert f"**${spend:.2f}**" in results_md
    scans = [load("run", "plan", "scan.json"), load("run", "retry", "scan.json")]
    refused = sum(c.get("refused", 0) for s in scans for c in s["perCell"].values())
    gold = sum(1 for s in scans for h in s["hits"] if h["kind"] == "leak_in_refusal")
    m.update({"planned": n_(tot["selected"]), "scored": n_(tot["scored"]), "scored-pct": pct(tot["scored"], tot["selected"]),
              "cell-min": fixed(100 * min(per_cell), 0), "cell-max": fixed(100 * max(per_cell), 0),
              "ratelimited": n_(listed["taskRuns"]), "rerun": n_(merged["taskRuns"]),
              "lost": n_(listed["taskRuns"] - merged["taskRuns"]), "cells": str(len(plan["cells"])),
              "spend": fixed(spend, 2), "refused": n_(refused), "refusal-gold": str(gold)})

    rs = load("design", "random_set.json")
    hard = [l for l in (G / "design" / "hard_set.jsonl").read_text().splitlines() if l.strip()]
    m.update({"random-tasks": str(len(rs["tasks"])), "random-requesters": str(len(rs["requesters"])),
              "hard-pairs": str(len(hard))})
    for surface, key in (("files_qa", "files"), ("states_qa", "states"), ("action", "actions")):
        m[f"random-{key}"] = str(rs["quota"][surface])
    by_req = collections.Counter(json.loads(l)["requester"] for l in hard)
    for req in REQ:
        m[f"hard-pairs-{req}"] = str(by_req[req])

    # ---------------------------------------------------------------- random set: rates
    units = collections.defaultdict(list)
    for req in REQ:
        for pol in ("D0", "D1", "D2"):
            for f in ("grok",) + MODELS:
                b = rel["rates"][f"{f}-{pol}-{req}"]
                for met, s in MET.items():
                    key = f"r-{req}-{pol}-{s}-{SHORT[f]}"
                    m[key] = rate(b[met])
                    if b[met]["n"]:
                        m[f"{key}-of"] = f"{b[met]['k']} of {b[met]['n']}"
                        m[f"{key}-n"] = str(b[met]["n"])
                    if f == "grok":
                        units[(req, met)].append(b[met]["n"])

    # ---------------------------------------------------------------- the three families
    F1 = family(o["primary"]["F1"])
    F2 = family(o["primary"]["F2"])
    F3 = family(o["primary"]["F3"])
    for t, p, h in F1:
        k = f"f1-{t['requester']}-{t['from']}{t['to']}-{MET[t['metric']]}"
        m.update({f"{k}-before": ex(t["a_pct"], t["n"]), f"{k}-after": ex(t["b_pct"], t["n"]),
                  f"{k}-before0": ex(t["a_pct"], t["n"], 0), f"{k}-after0": ex(t["b_pct"], t["n"], 0),
                  f"{k}-n": str(t["n"]), f"{k}-p": p_plain(p), f"{k}-holm": p_plain(h)})
    for t, p, h in F2:
        k = f"f2-{t['requester']}-{SHORT[t['model']]}-{MET[t['metric']]}"
        m.update({f"{k}-model": ex(t["a_pct"], t["n"]), f"{k}-grok": ex(t["b_pct"], t["n"]), f"{k}-n": str(t["n"]),
                  f"{k}-p": p_plain(p), f"{k}-holm": p_plain(h)})
    f2_min = min(F2, key=lambda x: x[2])
    m["f2-holm-min"] = p_plain(f2_min[2])
    m["f2-holm-min-which"] = f"{NAME[f2_min[0]['model']]}, {REQ[f2_min[0]['requester']].split(' ', 1)[1]}, " \
                             f"{'total leak' if f2_min[0]['metric'] == 'total_leak' else 'false refusal'}"
    m["f2-sig"] = str(sum(h < Fraction(1, 20) for _, _, h in F2))
    m["f1-sig"] = str(sum(h < Fraction(1, 20) for _, _, h in F1))
    m["f3-sig"] = str(sum(h < Fraction(1, 20) for _, _, h in F3))
    for t, p, h in F3:
        k = f"f3-{SHORT[t['model']]}-{MET[t['metric']]}"
        m.update({f"{k}-model": ex(t["a_pct"], t["n"]), f"{k}-grok": ex(t["b_pct"], t["n"]),
                  f"{k}-model0": ex(t["a_pct"], t["n"], 0), f"{k}-grok0": ex(t["b_pct"], t["n"], 0), f"{k}-n": n_(t["n"]),
                  f"{k}-pairs": n_(t["pairs"]), f"{k}-p": p_plain(p), f"{k}-holm": p_plain(h)})
    m["f1-size"], m["f2-size"], m["f3-size"] = str(len(F1)), str(len(F2)), str(len(F3))
    n2 = [t["n"] for t, _, _ in F2 if t["metric"] == "total_leak"]
    m["f2-tl-n-min"], m["f2-tl-n-max"] = str(min(n2)), str(max(n2))
    m["trial-runs"] = str(len(trial["taskRuns"]))
    n12 = [t["n"] for t, _, _ in F1 if t["requester"] in ("R1", "R2") and t["metric"] == "total_leak"]
    m["f1-n-R1R2-min"], m["f1-n-R1R2-max"] = str(min(n12)), str(max(n12))
    fr3 = [t for t, _, _ in F3 if t["metric"] == "fr"]
    m["f3-fr-grok-min"] = fixed(min(exf(t["b_pct"], t["n"]) for t in fr3), 0)
    m["f3-fr-grok-max"] = fixed(max(exf(t["b_pct"], t["n"]) for t in fr3), 0)
    tl3 = [t for t, _, _ in F3 if t["metric"] == "total_leak"]
    m["f3-tl-n-min"], m["f3-tl-n-max"] = n_(min(t["n"] for t in tl3)), n_(max(t["n"] for t in tl3))
    lo, hi = min(exf(t["b_pct"], t["n"]) for t in tl3), max(exf(t["b_pct"], t["n"]) for t in tl3)
    m["f3-tl-grok-min"], m["f3-tl-grok-max"] = fixed(lo, 1), fixed(hi, 1)
    m["f3-tl-grok-min0"], m["f3-tl-grok-max0"] = fixed(lo, 0), fixed(hi, 0)
    # the stranger under D1 (descriptive, not in F1) and the hard set's D1 false refusals (descriptive)
    r0 = next(t for t in rel["ladder"] if t["requester"] == "R0" and t["from"] == "D0" and t["to"] == "D1"
              and t["metric"] == "total_leak")
    m.update({"r0-D0D1-before": ex(r0["a_pct"], r0["n"]), "r0-D0D1-after": ex(r0["b_pct"], r0["n"]),
              "r0-D0D1-before0": ex(r0["a_pct"], r0["n"], 0), "r0-D0D1-after0": ex(r0["b_pct"], r0["n"], 0),
              "r0-D0D1-up": str(r0["b_only"]), "r0-D0D1-down": str(r0["a_only"]), "r0-D0D1-n": str(r0["n"]),
              "r0-D0D1-p": p_plain(mcnemar_p(r0["a_only"], r0["b_only"]))})
    for t in o["hard"]["relationship"]["leaveOneOut"]:
        if t["requester"] == "all" and t["policy"] == "D1" and t["metric"] in MET:
            k = f"loo-D1-{SHORT[t['model']]}-{MET[t['metric']]}"
            m.update({f"{k}-model": ex(t["a_pct"], t["n"]), f"{k}-grok": ex(t["b_pct"], t["n"]), f"{k}-n": n_(t["n"]),
                      f"{k}-p": p_plain(mcnemar_p(t["a_only"], t["b_only"]))})
    for (req, met), ns in units.items():
        ns = [x for x in ns if x]
        if ns:
            m[f"units-{req}-{MET[met]}"] = str(min(ns)) if min(ns) == max(ns) else f"{min(ns)}--{max(ns)}"

    # ---------------------------------------------------------------- Table 4's total leak
    t4 = json.loads((OUT / "table4_measure.json").read_text())
    m["unscored"] = n_(tot["selected"] - tot["scored"])
    m["unscored-other"] = n_(tot["selected"] - tot["scored"] - (listed["taskRuns"] - merged["taskRuns"]))
    for k, b in t4["rates"].items():
        fam, pol, req = k.split("-")
        key = f"t4-r-{req}-{pol}-tl-{SHORT[fam]}"
        m[key], m[f"{key}-of"] = rate(b), f"{b['k']} of {b['n']}"
    m["t4-changed-d2"] = str(sum(1 for c in t4["random_rates_changed"] if c["cell"].split("-")[1] == "D2"
                                 and c["cell"].split("-")[0] != "grok"))
    m["t4-changed"] = str(len(t4["random_rates_changed"]))
    d2 = [c for c in t4["random_rates_changed"] if c["cell"].split("-")[1] == "D2" and c["cell"].split("-")[0] != "grok"]
    assert all(Fraction(c["t4"]["k"], c["t4"]["n"]) < Fraction(c["pre"]["k"], c["pre"]["n"]) for c in d2)  # "fall"
    for t, u in zip(t4["F3"], o["primary"]["F3"]):     # the note's "Grok 4.6's is unchanged"
        assert (t["model"], t["metric"]) == (u["model"], u["metric"])
        if t["metric"] == "total_leak":
            assert exf(t["b_pct"], t["n"]) == exf(u["b_pct"], u["n"]) and t["n"] == u["n"]
    p3 = [mcnemar_p(t["a_only"], t["b_only"]) for t in t4["F3"]]
    for t, p_, h_ in zip(t4["F3"], p3, holm(p3)):
        assert abs(float(h_) - t["p_holm"]) < 1e-12
        k = f"t4-f3-{SHORT[t['model']]}-{MET[t['metric']]}"
        m.update({f"{k}-model": ex(t["a_pct"], t["n"]), f"{k}-grok": ex(t["b_pct"], t["n"]), f"{k}-n": n_(t["n"]),
                  f"{k}-p": p_plain(p_), f"{k}-holm": p_plain(h_)})
    t4f2 = holm([mcnemar_p(t["a_only"], t["b_only"]) for t in t4["F2"]])
    m["t4-f2-holm-min"] = p_plain(min(t4f2))
    m["t4-verdicts-changed"] = str(sum(t4["holm_verdicts_changed"].values()))
    hs = t4["hard_set"]
    m.update({"t4-hard-pairs": str(hs["table4"]), "t4-hard-only-pre": str(hs["only_preregistered"]),
              "t4-hard-only-t4": str(hs["only_table4"])})
    rc = t4["grok_refusal_channel"]
    m.update({"t4-grok-rc-pre": str(rc["preregistered_scan"]), "t4-grok-rc": str(rc["table4"]),
              "t4-grok-refused": n_(rc["refused_rows"])})

    # ---------------------------------------------------------------- the table
    def cell(req, pol, met, f):
        return m[f"r-{req}-{pol}-{MET[met]}-{SHORT[f]}"]

    L = [r"\begin{table}[H]", r"\centering\small",
         r"\caption{\textbf{A fourth responder: Grok~4.6 on two PAIR~I task sets (\%).} Grok~4.6 runs as requester and "
         r"responder on Azure, one run "
         r"per cell, on two task sets drawn from PAIR~I before any Grok~4.6 run, scored under the relationship labels. "
         r"STL: the scan-based total leak of Appendix~\ref{app:single-grok} (a decision leak, or a refusal in which the "
         r"refusal scan finds a gold fact, echoes included), the pre-registered measure. Table~\ref{tab:single-ladder}'s "
         r"total leak excludes refusal-channel echoes, and the note gives the difference. FR is false refusal. (a)~The random set, "
         r"100 tasks per "
         r"requester: Grok~4.6's ladder, and the three PAIR~I models at D2 on the same tasks. (b)~The hard set at D2, leave "
         r"one out: each PAIR~I model versus Grok~4.6 on the pairs the other two models made hard, which were chosen "
         r"without looking at either side. Tests are exact McNemar tests paired by task, Holm-adjusted within each "
         r"pre-registered family.}",
         r"\label{tab:single-grok}", r"\setlength{\tabcolsep}{4pt}", r"\renewcommand{\arraystretch}{1.1}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lcrrrrrrr@{}}", r"\toprule",
         r"\multicolumn{9}{@{}l}{\textit{(a) Random set}} \\",
         r"& & \multicolumn{3}{c}{Grok~4.6} & \multicolumn{3}{c}{D2, same tasks} & \\",
         r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
         r"Requester & & D0 & D1 & D2 & DeepSeek V4.1 & GLM-5.3-Flash & GPT-5.6 & Units \\", r"\midrule"]
    for req in REQ:
        mets = ("total_leak",) if req == "R0" else ("total_leak", "fr")
        for i, met in enumerate(mets):
            row = [REQ[req] if i == 0 else "", "STL" if met == "total_leak" else "FR"]
            row += [f"${cell(req, pol, met, 'grok')}$" for pol in ("D0", "D1", "D2")]
            row += [f"${cell(req, 'D2', met, f)}$" for f in MODELS]
            row.append(m[f"units-{req}-{MET[met]}"])
            L.append(" & ".join(row) + r" \\")
        if req != "R3":
            L.append(r"\addlinespace[2pt]")
    # Two tabulars, so each panel sizes its own columns (one shared tabular is 28 pt too wide at \small).
    L += [r"\bottomrule", r"\end{tabular*}", r"\par\medskip",
          r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrrrr@{}}", r"\toprule",
          r"\multicolumn{9}{@{}l}{\textit{(b) Hard set at D2, leave one out}} \\",
          r"& \multicolumn{4}{c}{STL} & \multicolumn{4}{c}{False refusal} \\",
          r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
          r"Held-out model & Units & Model & Grok~4.6 & $p_{\mathrm{Holm}}$ & Units & Model & Grok~4.6 & $p_{\mathrm{Holm}}$ \\",
          r"\midrule"]
    for f in MODELS:
        s = SHORT[f]
        L.append(f"{NAME[f]} & ${m[f'f3-{s}-tl-n']}$ & ${m[f'f3-{s}-tl-model']}$ & ${m[f'f3-{s}-tl-grok']}$ & "
                 f"${m[f'f3-{s}-tl-holm']}$ & ${m[f'f3-{s}-fr-n']}$ & ${m[f'f3-{s}-fr-model']}$ & "
                 f"${m[f'f3-{s}-fr-grok']}$ & ${m[f'f3-{s}-fr-holm']}$ \\\\")
    sig1 = [t for t, _, h in F1 if h < Fraction(1, 20)]
    words = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four"}
    steps = []
    for t in sig1:
        k = f"f1-{t['requester']}-{t['from']}{t['to']}-{MET[t['metric']]}"
        steps.append(f"{REQ[t['requester']].split(' ', 1)[1]}'s {'STL' if t['metric'] == 'total_leak' else 'FR'} "
                     f"from {t['from']} to {t['to']}, {m[k + '-before']} to {m[k + '-after']}\\% "
                     f"($p_{{\\mathrm{{Holm}}}}={m[k + '-holm']}$, {m[k + '-n']} paired units)")
    f1_text = (f"Of the {m['f1-size']} tests of the ladder family (D0$\\to$D1 and D1$\\to$D2, STL and FR, R1--R3), "
               + (f"the {words.get(len(sig1), len(sig1))} that survive Holm are the "
                  + (" and the ".join(steps) if len(steps) <= 2 else "; the ".join(steps)) + "."
                  if sig1 else "none survives Holm."))
    note = (
        f"Units: Grok~4.6's scored protected (STL) and entitled (FR) units per rung; the stranger is entitled to no task "
        f"in the random set, and the close friend's {m['units-R3-fr']} entitled units make its FR uninformative. "
        f"(a)~{f1_text} None of the {m['f2-size']} tests of the D2 comparison family survives "
        f"Holm (smallest $p_{{\\mathrm{{Holm}}}}={m['f2-holm-min']}$, {m['f2-holm-min-which']}). The stranger's STL rises "
        f"from D0 to D1 ({m['r0-D0D1-up']} tasks up, {m['r0-D0D1-down']} down, $p={m['r0-D0D1-p']}$, outside the "
        f"pre-registered families). (b)~Units are the scored pairs eligible on both sides. "
        f"Under Table~\\ref{{tab:single-ladder}}'s total leak, {m['t4-changed-d2']} of the 12 model entries at D2 in (a) fall, "
        f"the three models' leave-one-out D2 leak is {m['t4-f3-ds-tl-model']}, {m['t4-f3-glm-tl-model']} and "
        f"{m['t4-f3-gpt-tl-model']}\\%, Grok~4.6's is unchanged, and no Holm verdict changes. "
        f"Delivery: {m['scored']} of {m['planned']} task-runs scored ({m['scored-pct']}\\%, {m['cell-min']}--"
        f"{m['cell-max']}\\% per cell). Azure rate limits ended {m['ratelimited']} task-runs. Of these, {m['rerun']} were "
        f"rerun before an Azure outage and {m['lost']} remain unscored, and the other {m['unscored-other']} unscored task-runs "
        f"are requester turns that could not be proven complete or recovered from the ledger, and responder or session failures. Grok~4.6 restates a gold fact in "
        f"{m['refusal-gold']} of its {m['refused']} refused replies."
    )
    L += [r"\bottomrule", r"\end{tabular*}", r"\vspace{2pt}", r"\begin{minipage}{\linewidth}\footnotesize\raggedright",
          note, r"\end{minipage}", r"\end{table}"]
    TAB.write_text("% Generated by scripts/single_grid/grok/render_tex.py from evidence/v3.13/single-grid-grok. Do not edit.\n"
                   + "\n".join(L) + "\n")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "macros.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    NUM.write_text("% Generated by scripts/single_grid/grok/render_tex.py from evidence/v3.13/single-grid-grok. Do not edit.\n"
                   "% Use \\groknum{key}; keys and values in evidence/v3.14/single-grid-grok/macros.json. p values are "
                   "math (use inside $...$).\n"
                   + "".join(f"\\expandafter\\def\\csname grok@{k}\\endcsname{{{v}}}\n" for k, v in sorted(m.items()))
                   + "\\providecommand{\\groknum}[1]{\\ifcsname grok@#1\\endcsname\\csname grok@#1\\endcsname"
                     "\\else\\textbf{??}\\fi}\n")
    print(f"wrote {TAB.relative_to(ROOT)} and {NUM.relative_to(ROOT)} ({len(m)} keys); delivery {m['scored']}/"
          f"{m['planned']}; F1 sig {m['f1-sig']}, F2 sig {m['f2-sig']}, F3 sig {m['f3-sig']}")


if __name__ == "__main__":
    main()
