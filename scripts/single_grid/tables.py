#!/usr/bin/env python3
"""LaTeX tables for the single-request grid (booktabs, tabular*, matching the manuscript's table style).
Reads out/cells.json and out/tasks.jsonl; writes out/tables/*.tex.  Rates are the with-recovery
relationshipActive rates (recovery changes 4 tasks in the OpenRouter grid and 413 in the Azure grid)."""
import json, os, collections, sys
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats import load_tasks, paired, mcnemar_exact
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # paper repo root
sys.path.insert(0, os.path.join(ROOT, "scripts", "common"))
from halfup import fixed, signed  # every printed rate is rounded half away from zero from its exact fraction
OUT = os.path.join(ROOT, "evidence", "v3.13", "single-grid"); TAB = os.path.join(ROOT, "tables")
cells = {c["cell"]: c for c in json.load(open(os.path.join(OUT, "cells.json")))["cells"]}
pools = json.load(open(os.path.join(OUT, "pools.json")))["cells"]  # Files/States split, pools.py
MODEL = {"ds41": "DeepSeek V4.1", "glm": "GLM-5.3-Flash", "luna": "GPT-5.6"}            # glossary v2, section 9
REQ = {"R0": "R0 stranger", "R1": "R1 colleague", "R2": "R2 CEO's asst.", "R3": "R3 close friend"}
POL = {"D0": "D0 none", "D1": "D1 generic", "D2": "D2 relationship", "D3": "D3 +spotlight", "D4": "D4 +hierarchy", "D5": "D5 +sandwich", "D6": "D6 length control"}
CROSS = {"xC": r"DeepSeek$\to$GLM", "xD": r"GLM$\to$DeepSeek", "codex": "Codex CLI"}  # responder -> requester (glossary v2, section 8)

def rate(c, m, which="recovered"):
    """Exact percentage 100 * numerator / denominator, or None for an empty denominator."""
    r = c[which][m]; return None if not r["denominator"] else Fraction(100 * r["numerator"], r["denominator"])
def ppct(blk):
    """Exact percentage of a pools.json block {k, n}, or None for an empty denominator."""
    return None if not blk["n"] else Fraction(100 * blk["k"], blk["n"])
def fmt(v, bold=False):
    if v is None: return "\\textemdash"
    s = fixed(v, 1); return f"$\\mathbf{{{s}}}$" if bold else f"${s}$"
def n_of(c, m, which="recovered"): return c[which][m]["denominator"]
def at_most(x, digits=1):
    """A value printed as an upper bound ("at most", "within"), rounded towards +infinity, so the bound holds."""
    import math
    return fixed(Fraction(math.ceil(Fraction(x) * 10 ** digits), 10 ** digits), digits)
def at_least(x, digits=1):
    """A value printed as a lower bound ("at least"), rounded towards -infinity."""
    import math
    return fixed(Fraction(math.floor(Fraction(x) * 10 ** digits), 10 ** digits), digits)

def words(n):
    """Style sheet: counts from zero to nine as words."""
    return ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")[n] if 0 <= n < 10 else str(n)

def write(name, body):
    path = os.path.join(TAB, name); open(path, "w").write(body); print("wrote", path)

# ---------- T1: main compact ladder table (three models x D0/D1/D2 x R1-R3) ----------
# Leak is the total leak: decision leak plus refusal-channel leak, echoes excluded, from
# evidence/v3.14/total-disclosure/pair1_cells.json (scripts/p11/pair1_td.py); FR and AS are the cells' own.
TDC = json.load(open(os.path.join(ROOT, "evidence", "v3.14", "total-disclosure", "pair1_cells.json")))["cells"]
MODEL2 = {"ds41": "DeepSeek V4.1", "glm": "GLM-5.3-Flash", "luna": "GPT-5.6"}   # glossary v2, section 9
REQ2 = {"R0": "R0 stranger", "R1": "R1 colleague", "R2": "R2 CEO's asst.", "R3": "R3 close friend"}
def tl(cell):
    a = TDC[cell]["relationship"]
    return Fraction(100 * a["TD"], a["n"]) if a.get("n") else None
def t1():
    fams = ["ds41", "glm", "luna"]
    L = [r"\begin{table}[H]", r"\centering\small",
         r"\caption{\textbf{Single-request policy outcomes (\%).} Each cell attempts 600 tasks; rates use scored,",
         r"eligible tasks. Tables~\ref{tab:single-grid-deepseek}--\ref{tab:single-grid-gpt56} give the scored counts and",
         r"the stranger's rows, Tables~\ref{tab:single-pools-deepseek}--\ref{tab:single-pools-gpt56} the denominators on",
         r"each question surface, and Table~\ref{tab:metrics} the measures (Appendix~\ref{app:single-measurement}).}",
         r"\label{tab:single-ladder}", r"\setlength{\tabcolsep}{4pt}", r"\renewcommand{\arraystretch}{1.1}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrrrrr@{}}", r"\toprule",
         "& & " + " & ".join(f"\\multicolumn{{3}}{{c}}{{{MODEL2[f]}}}" for f in fams) + r" \\",
         r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}\cmidrule(lr){9-11}",
         r"Requester & Rung & " + " & ".join([r"TL$\downarrow$ & FR$\downarrow$ & AS$\uparrow$"] * 3) + r" \\", r"\midrule"]
    for req in ["R1", "R2", "R3"]:
        for i, pol in enumerate(["D0", "D1", "D2"]):
            row = [REQ2[req] if i == 0 else "", r"\textbf{D2}" if pol == "D2" else pol]
            for fam in fams:
                cell = f"{fam}-{pol.lower()}-{req.lower()}"; c = cells[cell]
                row += [fmt(tl(cell)), fmt(rate(c, "falseRefusalRate")), fmt(rate(c, "actionSafety"))]
            L.append(" & ".join(row) + r" \\")
        if req != "R3": L.append(r"\addlinespace[3pt]")
    L += [r"\bottomrule", r"\end{tabular*}", r"\vspace{2pt}", r"\begin{minipage}{\linewidth}\footnotesize\raggedright",
          r"D0: no policy; D1: generic caution; D2: relationship policy.",
          r"\end{minipage}", r"\end{table}"]
    write("single_ladder.tex", "\n".join(L) + "\n")

# ---------- T2: variants add nothing (pooled paired tests; Table 19 [23]) ----------
def pooled(tasks, fam, pol_a, pol_b, metric, reqs=("R1", "R2", "R3")):
    b = c = fa = n = 0
    for req in reqs:
        a = f"{fam}-{pol_a.lower()}-{req.lower()}"; bb = f"{fam}-{pol_b.lower()}-{req.lower()}"
        if a not in tasks or bb not in tasks: continue
        r = paired(tasks[a], tasks[bb], metric)
        b += r["discordant_a_only"]; c += r["discordant_b_only"]; n += r["n"]; fa += r["a_fail"]
    fb = fa - b + c
    return dict(n=n, delta_pp=Fraction(100 * (fb - fa), n) if n else None, p=mcnemar_exact(b, c), rate_a=Fraction(100 * fa, n) if n else None, rate_b=Fraction(100 * fb, n) if n else None)
def star(p): return r"$^{***}$" if p < 0.001 else r"$^{**}$" if p < 0.01 else r"$^{*}$" if p < 0.05 else ""
def bh(ps):
    """Benjamini-Hochberg q for a dict of p values (BH within each table)."""
    items = sorted(ps.items(), key=lambda kv: kv[1]); m = len(items); q, run = {}, 1.0
    for i in range(m - 1, -1, -1):
        k, p = items[i]; run = min(run, p * m / (i + 1)); q[k] = run
    return q
VARIANTS = [("D2", "D3", "D3 (spotlighting) $-$ D2"), ("D2", "D4", "D4 (instruction hierarchy) $-$ D2"), ("D2", "D5", "D5 (sandwich) $-$ D2"), ("D1", "D6", "D6 (length control) $-$ D1")]
def variant_tests(tasks):
    res = {(a, b, fam, m): pooled(tasks, fam, a, b, m) for a, b, _ in VARIANTS for fam in ("ds41", "glm", "luna") for m in ("leak", "frr")}
    q = bh({k: v["p"] for k, v in res.items()})
    return res, q
def t2(tasks):
    fams = ["ds41", "glm", "luna"]
    res, q = variant_tests(tasks)
    L = [r"\begin{table}[!ht]", r"\centering\small",
         r"\caption{\textbf{Neither defenses nor length change the ladder.} Paired differences on the same tasks (R1--R3 pooled, exact McNemar on discordant pairs). D3--D5 add one defense each to D2 (spotlighting, instruction hierarchy and sandwich framing, each shown in Appendix~\ref{app:single-policies}); D6 restates the generic caution at D2's length. DL is the decision leak. Differences in percentage points, variant minus anchor; a negative DL or FR favors the variant.}",
         r"\label{tab:single-variants}", r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrr@{}}", r"\toprule",
         "& " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{MODEL[f]}}}" for f in fams) + r" \\",
         r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
         r"Contrast & $\Delta$DL & $\Delta$FR & $\Delta$DL & $\Delta$FR & $\Delta$DL & $\Delta$FR \\", r"\midrule"]
    for a, b, name in VARIANTS:
        row = [name]
        for fam in fams:
            for m in ("leak", "frr"):
                r = res[(a, b, fam, m)]
                row.append(f"${signed(r['delta_pp'], 1)}${star(q[(a, b, fam, m)])}")
        L.append(" & ".join(row) + r" \\")
    nl = [v["n"] for (a, b, f, m), v in res.items() if m == "leak"]; nf = [v["n"] for (a, b, f, m), v in res.items() if m == "frr"]
    L += [r"\bottomrule", r"\end{tabular*}", r"\vspace{2pt}", r"\begin{minipage}{\linewidth}\footnotesize\setlength{\parindent}{0pt}",
          f"Stars: Benjamini--Hochberg $q$ within the table's {len(res)} tests ($^{{*}}q<0.05$, $^{{**}}q<0.01$, $^{{***}}q<0.001$). Each contrast pairs {min(nl)}--{max(nl)} protected questions and {min(nf)}--{max(nf)} entitled questions and authorized actions per model. Anchors (D2, D1) are in Table~\\ref{{tab:single-policy-pooled}}. The one large effect is the length control on the close friend for GPT-5.6: the longer generic text refuses far more entitled personal questions while leaking as much as D1 (Tables~\\ref{{tab:single-grid-deepseek}}--\\ref{{tab:single-grid-gpt56}} and Figure~\\ref{{fig:single-operating-points}}).",
          r"\end{minipage}", r"\end{table}"]
    write("single_variants.tex", "\n".join(L) + "\n")

# ---------- T3: requester model and harness (Table 24) ----------
# Leak is the total leak; the note's tests come from scripts/p17/inference.py (exact McNemar per cell,
# Benjamini-Hochberg within this table's 40 leak and FR tests).
P17 = os.path.join(ROOT, "evidence", "v3.14", "p17")
def t3():
    t17 = json.load(open(os.path.join(P17, "pair1_tests.json")))
    q = json.load(open(os.path.join(P17, "families.json")))["pair1_bh"]["swap_harness_leak_FR"]["q"]
    def gap(k):
        """|b - a| in points, exactly, from the test's discordant counts."""
        v = t17[k]; return abs(Fraction(100 * (v["improved_worsened"][1] - v["improved_worsened"][0]), v["n"]))
    tl_max = max(gap(k) for k in q if k.endswith("/leak_TD"))
    L = [r"\begin{table}[H]", r"\centering\small",
         r"\caption{\textbf{Leak follows the responder.} Holding the responder model, policy and requester fixed and changing only the model that drives the requester (or the responder's harness) moves the total leak by at most "
         + at_most(tl_max) + r" points. Column pairs name the model that drives the requester; Codex CLI is the DeepSeek V4.1 responder run inside the Codex CLI harness with a DeepSeek requester. TL and FR in percent over scored tasks.}",
         r"\label{tab:single-crossmodel}", r"\setlength{\tabcolsep}{4.5pt}\footnotesize",
         r"\begin{tabular}{@{}ll*{10}{>{\raggedleft\arraybackslash}p{0.72cm}}@{}}", r"\toprule",   # fixed widths keep each TL/FR pair under its header
         r"& & \multicolumn{6}{c}{Responder: DeepSeek V4.1} & \multicolumn{4}{c}{Responder: GLM-5.3-Flash} \\",
         r"\cmidrule(lr){3-8}\cmidrule(lr){9-12}",
         r"\multicolumn{2}{@{}l}{Requester model} & \multicolumn{2}{c}{DeepSeek} & \multicolumn{2}{c}{GLM} & \multicolumn{2}{c}{Codex CLI} & \multicolumn{2}{c}{GLM} & \multicolumn{2}{c}{DeepSeek} \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}\cmidrule(lr){11-12}",
         r"Requester & Rung & TL & FR & TL & FR & TL & FR & TL & FR & TL & FR \\", r"\midrule"]
    for req in ["R1", "R2", "R3"]:
        for i, pol in enumerate(["D0", "D1", "D2"]):
            row = [REQ2[req] if i == 0 else "", pol]
            for fam in ["ds41", "xC", "codex", "glm", "xD"]:
                k = f"{fam}-{pol.lower()}-{req.lower()}"
                if k in cells: row += [fmt(tl(k)), fmt(rate(cells[k], "falseRefusalRate"))]
                else: row += ["\\textemdash", "\\textemdash"]
            L.append(" & ".join(row) + r" \\")
        if req != "R3": L.append(r"\addlinespace[3pt]")
    n_swap = sum("requester swap" in k for k in q); n_h = sum("harness" in k for k in q)
    big = {m: max((k for k in q if k.endswith("/" + m)), key=lambda k: abs(t17[k]["diff"])) for m in ("leak_TD", "FR")}
    def where(k):
        v = t17[k]; fam, req, pol = v["block"].split("/")
        resp = {"ds41": "DeepSeek V4.1", "glm": "GLM-5.3-Flash"}[fam]
        prose = {"R1": "colleague", "R2": "CEO's assistant", "R3": "close friend"}[req]
        return f"{resp} responder, {prose}, {pol}, $n={v['n']}$"
    unc = sum(t17[k]["p"] < 0.05 for k in q)
    sig = sum(v < 0.05 for v in q.values())
    note = (f"The Codex CLI harness (DeepSeek V4.1 on both sides) was run for D2 only. Across the {n_swap + n_h} paired "
            f"total-leak and false-refusal tests on R1--R3 that swap the requester model ({n_swap}) or the harness ({n_h}), "
            f"the largest paired difference is {fixed(gap(big['leak_TD']), 2)} points of total leak ({where(big['leak_TD'])}) "
            f"and {fixed(gap(big['FR']), 2)} of false refusal ({where(big['FR'])}). ")
    if sig == 0:
        note += (f"None is significant after Benjamini--Hochberg within the table (smallest $q = {fixed(min(q.values()), 2)}$); "
                 f"{words(unc)} have an uncorrected $p < 0.05$ (exact McNemar, paired by task).")
    else:
        note += f"{sig} are significant after Benjamini--Hochberg within the table."
    # what the 95% intervals exclude (scripts/p17/inference.py's null_reading)
    lk = [k for k in q if k.endswith("/leak_TD")]; fk = [k for k in q if k.endswith("/FR")]
    n10 = sum(t17[k]["null_reading"] == "no difference larger than 10 points" for k in lk)
    n5 = sum(t17[k]["null_reading"] == "no difference larger than 5 points" for k in fk)
    note += (f" The 95\\% intervals (Newcombe, paired) exclude differences above 10 points of total leak in {n10} of the "
             f"{len(lk)} total-leak comparisons and above 5 points of false refusal in {n5} of the {len(fk)} false-refusal "
             f"comparisons (\\texttt{{evidence/v3.14/p17/pair1\\_tests.json}}).")
    L += [r"\bottomrule", r"\end{tabular}", r"\par\vspace{2pt}", r"\begin{minipage}{\linewidth}\footnotesize\setlength{\parindent}{0pt}",
          note, r"\end{minipage}", r"\end{table}"]
    write("single_crossmodel.tex", "\n".join(L) + "\n")

# ---------- T4: full appendix grids (Tables 13-15 [14-16] and the cross-model table) ----------
GRID_CAPTION = ("One run of 600 tasks per cell. U: entitled questions answered with their gold facts; FR: entitled questions "
                "and authorized actions refused; Leak: PAIR~I's decision leak, protected questions whose reply, recorded as an "
                r"answer, carries a gold fact (Table~\ref{tab:single-ladder} gives the total leak); AU: authorized actions with "
                "the correct end state; AS: unauthorized actions that left the workspace unchanged. Scored counts include "
                "quarantined question tasks recovered from the \\SharedOS{} ledger (rec.). A dash marks an undefined denominator or, for the stranger's U "
                "and FR, a denominator of one entitled question, which we do not report.")
GRID_METRICS = ("informationUtility", "falseRefusalRate", "leakRate", "actionUtility", "actionSafety")   # S = 100 - Leak is dropped
def t4():
    for fam, label in [("ds41", "deepseek"), ("glm", "glm"), ("luna", "gpt56")]:
        title = MODEL[fam] + (" (Azure)" if fam == "luna" else "")
        L = [r"\begin{table}[!ht]", r"\centering\scriptsize",
             (f"\\caption{{\\textbf{{{title}: full single-request grid.}} {GRID_CAPTION}}}" if fam == "ds41" else  # the other models' captions point to the first
              f"\\caption{{\\textbf{{{title}: full single-request grid.}} As in Table~\\ref{{tab:single-grid-deepseek}}.}}"),
             f"\\label{{tab:single-grid-{label}}}", r"\setlength{\tabcolsep}{2.5pt}",
             r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrrr@{}}", r"\toprule",
             r"Rung & Req. & U & FR & Leak & AU & AS & scored & rec. \\", r"\midrule"]
        for pol in ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]:
            for i, req in enumerate(["R0", "R1", "R2", "R3"]):
                c = cells[f"{fam}-{pol.lower()}-{req.lower()}"]
                row = [POL[pol] if i == 0 else "", req]
                row += [("\\textemdash" if (req == "R0" and m in ("informationUtility", "falseRefusalRate")) else fmt(rate(c, m)))
                        for m in GRID_METRICS]
                row += [str(c["scoredWithRecovery"]), str(c["recoveredQa"])]
                L.append(" & ".join(row) + r" \\")
            if pol != "D6": L.append(r"\addlinespace[1.5pt]")
        L += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
        write(f"single_grid_{label}.tex", "\n".join(L) + "\n")
    # cross-model + codex compact appendix table
    L = [r"\begin{table}[!ht]", r"\centering\scriptsize",
         r"\caption{\textbf{Cross-model and harness cells.} DeepSeek$\to$GLM: the DeepSeek V4.1 responder with a GLM-5.3-Flash requester; GLM$\to$DeepSeek: the reverse; Codex CLI: DeepSeek V4.1 on both sides, with the responder run inside the Codex CLI harness. Same metrics as Tables~\ref{tab:single-grid-deepseek}--\ref{tab:single-grid-gpt56}.}",
         r"\label{tab:single-grid-cross}", r"\setlength{\tabcolsep}{2.5pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lllrrrrrr@{}}", r"\toprule",
         r"Cells & Rung & Req. & U & FR & Leak & AU & AS & scored \\", r"\midrule"]
    for fam in ["xC", "xD", "codex"]:
        first = True
        for pol in ["D0", "D1", "D2"]:
            for req in ["R0", "R1", "R2", "R3"]:
                k = f"{fam}-{pol.lower()}-{req.lower()}"
                if k not in cells: continue
                c = cells[k]
                row = [CROSS[fam] if first else "", POL[pol], req]; first = False
                row += [("\\textemdash" if (req == "R0" and m in ("informationUtility", "falseRefusalRate")) else fmt(rate(c, m)))
                        for m in GRID_METRICS]
                row += [str(c["scoredWithRecovery"])]
                L.append(" & ".join(row) + r" \\")
        L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    write("single_grid_cross.tex", "\n".join(L) + "\n")

# ---------- T5: delivery and error accounting (Table 12 [13]) ----------
def t5():
    fams = [("ds41", "DeepSeek V4.1 (OpenRouter)"), ("glm", "GLM-5.3-Flash (OpenRouter)"), ("xC", CROSS["xC"]), ("xD", CROSS["xD"]), ("codex", "Codex CLI"), ("luna", "GPT-5.6 (Azure)")]
    side = collections.Counter()
    for fam_tasks in load_tasks().values():
        for r in fam_tasks.values():
            if r["status"] == "side_effect_before_failure": side[r["family"]] += 1
    L = [r"\begin{table}[!ht]", r"\centering\small",
         r"\caption{\textbf{Delivery of the single-request grid.} Every cell attempts 600 tasks. A task is excluded when it ends without a scorable decision; the column names the stage that failed. Quarantined tasks (indeterminate requester turn) whose responder reply and requester classification are both committed in the \SharedOS{} ledger are recovered and scored; the rates without recovery are in the supplementary JSON.}",
         r"\label{tab:single-grid-delivery}", r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrr@{}}", r"\toprule",
         r"Cells (600 tasks each) & resp.\ failed & session failed & quarantined & recovered & scored & delivery \\", r"\midrule"]
    for fam, name in fams:
        cs = [c for c in cells.values() if c["family"] == fam]
        att = 600 * len(cs)
        codes = collections.Counter()
        for c in cs: codes.update(c["errorCodes"])
        rec = sum(c["recoveredQa"] for c in cs); sc = sum(c["scoredWithRecovery"] for c in cs)
        resp = codes.get("CONTACT_RESPONDER_FAILED", 0) + codes.get("CONTACT_RESPONDER_FILE_READ_REQUIRED", 0)
        L.append(f"{name} ({len(cs)}) & {resp} & {codes.get('FILE_SESSION_FAILED',0)} & {codes.get('INDETERMINATE_EXTERNAL_OPERATION',0)} & {rec} & {sc:,} & ${fixed(Fraction(100 * sc, att), 1)}\\%$ \\\\")
    az = [c for c in cells.values() if c["family"] == "luna"]
    qa_all = sum(c["errorCodes"].get("INDETERMINATE_EXTERNAL_OPERATION", 0) for c in az)
    qa_r3 = sum(c["errorCodes"].get("INDETERMINATE_EXTERNAL_OPERATION", 0) for c in az if c["requester"] == "R3")
    sname = {"ds41": "DeepSeek~V4.1", "glm": "GLM-5.3-Flash", "xC": CROSS["xC"], "xD": CROSS["xD"], "codex": "Codex CLI", "luna": "GPT-5.6"}
    side_txt = ", ".join(f"{words(side[f])} {sname[f]}" for f, _ in fams if side[f])
    L += [r"\bottomrule", r"\end{tabular*}", r"\vspace{2pt}", r"\begin{minipage}{\linewidth}\footnotesize\setlength{\parindent}{0pt}\raggedright",
          r"Resp.\ failed merges two codes: \texttt{CONTACT\_RESPONDER\_FAILED} and \texttt{CONTACT\_RESPONDER\_FILE\_READ\_REQUIRED}; session failed is \texttt{FILE\_SESSION\_FAILED}; quarantined is \texttt{INDETERMINATE\_EXTERNAL\_OPERATION}. "
          + f"In the Azure grid {qa_r3} of the {qa_all} quarantined tasks are the close friend's, whose replies are mostly refusals; excluding them would understate the close friend's false-refusal rate. Recovered decisions use the same rule as the run-time pipeline (the requester's committed MEMORY classification plus the responder's committed reply); action tasks are never recovered. "
          + f"An action that changed the workspace before its turn failed stays scored for action safety (tasks: {side_txt}).",
          r"\end{minipage}", r"\end{table}"]
    write("single_grid_delivery.tex", "\n".join(L) + "\n")


# ---------- T6: what action safety counts (Table 21 [25]) ----------
def t6(tasks):
    def scored(r): return r["status"] in ("answered", "refused", "side_effect_before_failure") or r.get("recovery") is not None
    rows, d2 = [], []
    for fam, name in [("ds41", "DeepSeek V4.1"), ("glm", "GLM-5.3-Flash"), ("luna", "GPT-5.6")]:
        for i, req in enumerate(["R0", "R1", "R2", "R3"]):
            row = [name if i == 0 else "", REQ[req]]
            for pol in ["D0", "D1", "D2"]:
                sub = [r for r in tasks[f"{fam}-{pol.lower()}-{req.lower()}"].values() if r["kind"] == "action" and r["relationshipExpectedBehavior"] == "refuse" and scored(r)]
                auth = [r for r in sub if r["taskCategory"].startswith("authorized_")]; un = [r for r in sub if not r["taskCategory"].startswith("authorized_")]
                fa = sum(1 for r in auth if r.get("stateChanged")); fu = sum(1 for r in un if r.get("stateChanged"))
                row += [f"{fa}/{len(auth)}", f"{fu}/{len(un)}"]
                if pol == "D2" and un: d2.append((Fraction(100 * fu, len(un)), fu, len(un)))
            rows.append(" & ".join(row) + r" \\")
        if fam != "luna": rows.append(r"\addlinespace[3pt]")
    lo, hi = min(d2), max(d2)
    L = [r"\begin{table}[!ht]", r"\centering\small",
         r"\caption{\textbf{The two populations of action safety.} Unauthorized actions split into those withheld from this requester (work actions, i.e., creates, edits and completions the category labels authorize, that the relationship labels withhold from a given requester) and those canonically refused (sensitive creates and edits, strategic changes, wipes, information-leaking and probing actions that every label refuses). Each entry is executed/unauthorized. "
         + f"D2 cuts the canonical set to {fixed(lo[0], 0)}--{fixed(hi[0], 0)}\\% for every requester; what it still performs for the CEO's assistant are work actions the policy itself grants to a business counterpart's delegate.}}",
         r"\label{tab:single-action-split}", r"\setlength{\tabcolsep}{2pt}\footnotesize",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrr@{}}", r"\toprule",
         r"& & \multicolumn{2}{c}{D0 none} & \multicolumn{2}{c}{D1 generic} & \multicolumn{2}{c}{D2 relationship} \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}",
         r"Model & Requester & withheld & canonical & withheld & canonical & withheld & canonical \\", r"\midrule",
         *rows, r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    write("single_action_split.tex", "\n".join(L) + "\n")

# ---------- T7: Files QA / States QA per surface, full grid per model (appendix; C.4 now points to pools.json) ----------
def _label_dens():
    """Protected and entitled QA counts per requester and surface from the label file (before exclusions):
    {R: (protected Files, protected States, entitled Files, entitled States)}."""
    lab = json.load(open(os.path.join(ROOT, "evidence", "v3.1", "sharedeval", "dataset", "pact-pair", "relationship_labels",
                                      "relationship_label_matrix_v2.json")))
    d = {}
    for req in ("R0", "R1", "R2", "R3"):
        c = collections.Counter((q[req], "F" if q["id"] <= 200 else "S") for q in lab["questions"])
        d[req] = (c[("P", "F")], c[("P", "S")], c[("L", "F")], c[("L", "S")])
    return d
def _leak_star(o):
    p, g = o["fisher_p"]["leak"], o["todo_minus_notes"]["leak"]
    return star(p) if (p is not None and g is not None and g > 0) else ""
POOLS_DEF = ("The 400 questions of every cell split into 200 that read the owner's notes (Files QA, Q1--Q200) and 200 that "
             "read the owner's to-do list (States QA, Q201--Q400); every other table pools them. Leak (PAIR~I's decision leak) "
             "over protected questions, FR and U over entitled questions, with recovery.")
FISHER = ("Stars on a States QA leak give the significance of a two-sided Fisher exact test of the gap between the two surfaces in that cell "
          "($^{*}$ $p<0.05$, $^{**}$ $p<0.01$, $^{***}$ $p<0.001$, uncorrected); no cell differs significantly the other way.")
def t7():
    for fam, label in [("ds41", "deepseek"), ("glm", "glm"), ("luna", "gpt56")]:
        title = MODEL[fam] + (" (Azure)" if fam == "luna" else "")
        L = [r"\begin{table}[!ht]", r"\centering\scriptsize",
             (f"\\caption{{\\textbf{{{title}: Files QA and States QA separately.}} {POOLS_DEF} $n_p$ and $n_e$: protected and entitled denominators, Files/States. {FISHER} The stranger has one entitled question, so its FR and U are not reported.}}"
              if fam == "ds41" else  # the other models' captions point to the first
              f"\\caption{{\\textbf{{{title}: Files QA and States QA separately.}} As in Table~\\ref{{tab:single-pools-deepseek}}.}}"),
             f"\\label{{tab:single-pools-{label}}}", r"\setlength{\tabcolsep}{2.2pt}",
             r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{3}{c}{Files QA} & \multicolumn{3}{c}{States QA} & & \\", r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
             r"Rung & Req. & Leak & FR & U & Leak & FR & U & $n_p$ F/S & $n_e$ F/S \\", r"\midrule"]
        for pol in ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]:
            for i, req in enumerate(["R0", "R1", "R2", "R3"]):
                o = pools[f"{fam}-{pol.lower()}-{req.lower()}"]; a, b = o["pools"]["notes"], o["pools"]["todo"]
                dash = req == "R0"
                row = [POL[pol] if i == 0 else "", req,
                       fmt(ppct(a["leak"])), "\\textemdash" if dash else fmt(ppct(a["fr"])), "\\textemdash" if dash else fmt(ppct(a["iu"])),
                       fmt(ppct(b["leak"])) + _leak_star(o), "\\textemdash" if dash else fmt(ppct(b["fr"])), "\\textemdash" if dash else fmt(ppct(b["iu"])),
                       f"{a['leak']['n']}/{b['leak']['n']}", "\\textemdash" if dash else f"{a['fr']['n']}/{b['fr']['n']}"]
                L.append(" & ".join(row) + r" \\")
            if pol != "D6": L.append(r"\addlinespace[2pt]")
        L += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
        write(f"single_pools_{label}.tex", "\n".join(L) + "\n")

# ---------- T8: the ladder on each surface (Table 17 [18]) ----------
def t8():
    fams = ["ds41", "glm", "luna"]; d = _label_dens()
    L = [r"\begin{table}[!ht]", r"\centering\small",
         f"\\caption{{\\textbf{{The policy ladder on each question surface.}} The cells of Table~\\ref{{tab:single-ladder}} plus the stranger. {POOLS_DEF} The stranger's single entitled question is not reported. {FISHER} Before exclusions, the protected denominators (Files/States) are {d['R0'][0]}/{d['R0'][1]} for the stranger, {d['R1'][0]}/{d['R1'][1]} for the colleague, {d['R2'][0]}/{d['R2'][1]} for the CEO's assistant and {d['R3'][0]}/{d['R3'][1]} for the close friend; the entitled ones are {d['R1'][2]}/{d['R1'][3]}, {d['R2'][2]}/{d['R2'][3]} and {d['R3'][2]}/{d['R3'][3]}. Bold marks the D2 rows.}}",
         r"\label{tab:single-pools-ladder}", r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lllrrrrrr@{}}", r"\toprule",
         "& & & " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{MODEL[f]}}}" for f in fams) + r" \\",
         r"\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}",
         r"Requester & Rung & Surface & Leak$\downarrow$ & FR$\downarrow$ & Leak$\downarrow$ & FR$\downarrow$ & Leak$\downarrow$ & FR$\downarrow$ \\", r"\midrule"]
    for req in ["R0", "R1", "R2", "R3"]:
        first = True
        for pol in ["D0", "D1", "D2"]:
            for surf, name in (("notes", "Files"), ("todo", "States")):
                lab = (f"\\textbf{{{POL[pol]}}}" if pol == "D2" else POL[pol]) if surf == "notes" else ""
                row = [REQ[req] if first else "", lab, name]; first = False
                for fam in fams:
                    o = pools[f"{fam}-{pol.lower()}-{req.lower()}"]; x = o["pools"][surf]
                    row += [fmt(ppct(x["leak"])) + (_leak_star(o) if surf == "todo" else ""), "\\textemdash" if req == "R0" else fmt(ppct(x["fr"]))]
                L.append(" & ".join(row) + r" \\")
        if req != "R3": L.append(r"\addlinespace[3pt]")
    L += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    write("single_pools_ladder.tex", "\n".join(L) + "\n")

# ---------- T9: all seven policies pooled over R1-R3 (Table 18 [22]) ----------
POOL_METRICS = ("leakRate", "falseRefusalRate", "actionSafety", "informationUtility")
def t9(tasks):
    fams = ["ds41", "glm", "luna"]
    def pooled_counts(fam, pol, m):
        k = n = 0
        for req in ("r1", "r2", "r3"):
            c = cells[f"{fam}-{pol.lower()}-{req}"]["recovered"][m]; k += c["numerator"]; n += c["denominator"]
        return k, n
    def pooled_rate(fam, pol, m):
        k, n = pooled_counts(fam, pol, m); return Fraction(100 * k, n)
    # the largest D2-D5 spread per column, and the largest paired difference against D2 (Table 19 [23])
    spread = max(((max(pooled_rate(f, p, m) for p in ("D2", "D3", "D4", "D5")) - min(pooled_rate(f, p, m) for p in ("D2", "D3", "D4", "D5")), f, m)
                  for f in fams for m in POOL_METRICS))
    pmax = {(f, m): max(("D2", "D3", "D4", "D5"), key=lambda p: pooled_rate(f, m=m, pol=p)) for f in fams for m in POOL_METRICS}
    pmin = {(f, m): min(("D2", "D3", "D4", "D5"), key=lambda p: pooled_rate(f, m=m, pol=p)) for f in fams for m in POOL_METRICS}
    res, _ = variant_tests(tasks)
    paired_max = max(abs(v["delta_pp"]) for (a, b, f, m), v in res.items() if a == "D2")
    mname = {"leakRate": "leak", "falseRefusalRate": "FR", "actionSafety": "AS", "informationUtility": "U"}
    short = {"ds41": "DeepSeek", "glm": "GLM", "luna": "GPT-5.6"}
    sp, sf, sm = spread
    pair = sorted((pmax[(sf, sm)], pmin[(sf, sm)]))
    means = [Fraction(sum(pooled_counts(f, p, m)[1] for f in fams for p in POL), len(fams) * len(POL)) for m in ("leakRate", "falseRefusalRate", "actionSafety")]
    # how near D6 stays to D1, and how far from D2, pooled; and Table 23's one significant D6 - D1 difference
    d6 = {m: max(abs(pooled_rate(f, "D6", m) - pooled_rate(f, "D1", m)) for f in fams) for m in ("leakRate", "actionSafety")}
    far = {m: min(abs(pooled_rate(f, "D6", m) - pooled_rate(f, "D2", m)) for f in fams) for m in ("leakRate", "actionSafety")}
    assert all(far[m] > 3 * d6[m] for m in far), "D6 is not far from D2 relative to its distance from D1"
    _, q = variant_tests(tasks)
    sig6 = [(f, res[("D1", "D6", f, "leak")]["delta_pp"]) for f in fams if q[("D1", "D6", f, "leak")] < 0.05]
    assert len(sig6) == 1 and sig6[0][1] < 0 and all(q[("D1", "D6", f, "frr")] >= 0.05 for f in fams)
    L = [r"\begin{table}[!ht]", r"\centering\scriptsize",
         r"\caption{\textbf{All seven policies, pooled over the colleague, the CEO's assistant and the close friend.} Numerators and denominators summed over the three requesters "
         + f"(on average {fixed(means[0], 0)} protected questions, {fixed(means[1], 0)} entitled questions and authorized actions and {fixed(means[2], 0)} unauthorized actions per policy and model), with recovery. "
         + "Leak (PAIR~I's decision leak) and FR lower is better; AS and U higher. "
         + f"D2--D5 differ by at most {at_most(sp)} points on every column ({short[sf]} {mname[sm]}, {pair[0]} versus {pair[1]}), and by at most {at_most(paired_max)} points from D2 on paired tasks (Table~\\ref{{tab:single-variants}}). "
         + f"D6, the generic caution padded to D2's length, stays near D1 (within {at_most(d6['leakRate'])} points of leak and {at_most(d6['actionSafety'])} of action safety) and far from D2 (at least {at_least(far['leakRate'])} points more leak); "
         + f"on {MODEL[sig6[0][0]]} it leaks {fixed(-sig6[0][1], 1)} points less than D1 on paired tasks (Table~\\ref{{tab:single-variants}}). Bold marks the D2 row.}}",
         r"\label{tab:single-policy-pooled}", r"\setlength{\tabcolsep}{2.5pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrrrrrrrr@{}}", r"\toprule",
         "& " + " & ".join(f"\\multicolumn{{4}}{{c}}{{{MODEL[f]}}}" for f in fams) + r" \\",
         r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}\cmidrule(lr){10-13}",
         r"Rung & Leak & FR & AS & U & Leak & FR & AS & U & Leak & FR & AS & U \\", r"\midrule"]
    for pol in ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]:
        row = [f"\\textbf{{{POL[pol]}}}" if pol == "D2" else POL[pol]]
        for fam in fams:
            row += [fmt(pooled_rate(fam, pol, m)) for m in POOL_METRICS]
        L.append(" & ".join(row) + r" \\")
        if pol in ("D1", "D5"): L.append(r"\addlinespace[3pt]")
    L += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    write("single_policy_pooled.tex", "\n".join(L) + "\n")

if __name__ == "__main__":
    tasks = load_tasks()
    t1(); t2(tasks); t3(); t4(); t5(); t6(tasks); t7(); t8(); t9(tasks)
