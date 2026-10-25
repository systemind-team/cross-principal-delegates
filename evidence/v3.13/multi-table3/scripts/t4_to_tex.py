#!/usr/bin/env python3
"""Simple-profile Table 3: rows for the body table, rows for the appendix table, and the numbers the text needs.
Usage: t4_to_tex.py table3s.json s4_rescore_table.json filter_loss.json OUTDIR
Leak = decision leak (reply recorded as an answer that carries a gold fact); FR and AS from table3s.json.
"""
import json, sys, os
rep = json.load(open(sys.argv[1])); rs = json.load(open(sys.argv[2])); fl = json.load(open(sys.argv[3])); out = sys.argv[4]
BUILDS = ("DS", "GLM", "GROK"); POLS = ("D0", "D1", "D2"); REQS = ("R1", "R2", "R3")
RLAB = {"R1": "R1 colleague", "R2": "R2 exec.\\ delegate", "R3": "R3 close friend"}
PLAB = {"D0": "D0 none", "D1": "D1 generic", "D2": "D2 categories"}
BLAB = {"DS": "DeepSeek", "GLM": "GLM", "GROK": "Grok"}
MIN_N = 5
def rate(b, r, p, m):
    if m == "Leak":
        x = rs[f"{b}-{r}"]; return None if x["n"] < MIN_N else x["decision_leak"][p]
    x = rep["blocks"][f"{b}-{r}"]["rates"][p].get(m)
    if not x or x.get("value") is None or x.get("n", 0) < MIN_N: return None
    return x["value"]
def fmt(x, bold=False):
    if x is None: return "\\textemdash"
    s = f"{x:.1f}"
    return f"$\\mathbf{{{s}}}$" if bold else f"${s}$"
rows = []
for r in REQS:
    for i, p in enumerate(POLS):
        cells = []
        for b in BUILDS:
            cells += [fmt(rate(b, r, p, "Leak"), p == "D2"), fmt(rate(b, r, p, "FR")), fmt(rate(b, r, p, "AS"), p == "D2")]
        rows.append(f"{RLAB[r] if i == 0 else ''} & {PLAB[p]} & " + " & ".join(cells) + " \\\\")
    rows.append("\\addlinespace[3pt]")
open(os.path.join(out, "t4_rows.tex"), "w").write("\n".join(rows[:-1]) + "\n")
def pfmt(p):
    if p is None: return "\\textemdash"
    if p < 1e-3:
        e = 0; q = p
        while q < 1: q *= 10; e -= 1
        return f"${q:.1f}\\times10^{{{e}}}$"
    return f"${p:.2g}$" if p < 0.1 else f"${p:.2f}$"
app = []
for b in BUILDS:
    for j, r in enumerate(REQS):
        blk = rep["blocks"][f"{b}-{r}"]; x = rs[f"{b}-{r}"]
        sc = " & ".join(str(rep["cells"][f"{b}-{p}-{r}"]["scored"]) for p in POLS)
        rc = "/".join(str(x["counts"][p][1]) for p in POLS)
        p02, p12 = x["p_D0D2"], x["p_D1D2"]
        app.append(f"{BLAB[b] if j == 0 else ''} & {r} & {sc} & {blk['n_tasks']} & {x['n']} & {rc} & "
                   f"{pfmt(p02['p'])} ({p02['b']}:{p02['c']}) & {pfmt(p12['p'])} ({p12['b']}:{p12['c']}) \\\\")
    app.append("\\addlinespace[2pt]")
open(os.path.join(out, "t4_appendix_rows.tex"), "w").write("\n".join(app[:-1]) + "\n")
summ = {"coverage": {}, "nine_cell": {b: rep["nine_cell"][b]["n_tasks"] for b in BUILDS}, "provenance": rep["provenance"], "blocks": {}, "filter": {}}
for b in BUILDS:
    att = sum(rep["cells"][f"{b}-{p}-{r}"]["attempted"] for p in POLS for r in REQS)
    scd = sum(rep["cells"][f"{b}-{p}-{r}"]["scored"] for p in POLS for r in REQS)
    summ["coverage"][b] = round(100 * scd / att, 1)
    f = [fl[f"{b}-{p}-{r}"] for p in POLS for r in REQS]
    summ["filter"][b] = {k: sum(x.get(k, 0) for x in f) for k in ("runs", "runs_with_block", "tasks", "lost", "lost_protected", "scored_after_block", "lost_other")}
    for r in REQS:
        x = rs[f"{b}-{r}"]; blk = rep["blocks"][f"{b}-{r}"]
        summ["blocks"][f"{b}-{r}"] = {"n_tasks": blk["n_tasks"], "prot": x["n"], "decision_leak": x["decision_leak"], "refusal_channel": x["refusal_channel"],
                                      "p_D0D2": x["p_D0D2"], "p_D1D2": x["p_D1D2"],
                                      "FR": {p: rate(b, r, p, "FR") for p in POLS}, "AS": {p: rate(b, r, p, "AS") for p in POLS},
                                      "n_FR": blk["rates"]["D2"].get("FR", {}).get("n", 0), "n_AS": blk["rates"]["D2"].get("AS", {}).get("n", 0),
                                      "mcnemar_FR_D0D2": blk["mcnemar_D0_D2"]["FR"], "mcnemar_AS_D0D2": blk["mcnemar_D0_D2"]["AS"]}
json.dump(summ, open(os.path.join(out, "t4_summary.json"), "w"), indent=1)
print(json.dumps(summ, indent=1)[:6000])
