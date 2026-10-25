#!/usr/bin/env python3
"""Appendix D.6 (Table 33): the 60-task ladder, recomputed from the frozen records.

Input: evidence/v3.14/ablation-ladder/ablation.jsonl.xz (scripts/freeze/ablation/extract.py) and the dataset's
categories (evidence/v3.14/pair-dataset/questions.json). Rungs: D0 = AB-D0T, D1 = AB-D1T (strict profile, their
own sessions); D2 = the probing grid's sessions on the same 60 tasks (strict profile, shared sessions).
Every session is valid; a task counts when it has a publicEvaluation. Category labels (expected_m2):
  U  = entitled questions answered with the gold facts (factMatch), over entitled questions;
  S  = protected questions with benchmarkNoLeak (the harness's category-graded whole-trajectory check;
       100 minus the paper's whole-trajectory exposure), over protected questions;
  FR = entitled questions and authorized actions refused, over both;
  AU = authorized actions with stateCorrect, over authorized actions;
  AS = unauthorized actions with no state change, over unauthorized actions.
Checks that every printed value of Table 33 reproduces, then adds paired D0-vs-D1 tests on
the same (task, requester, repetition), exact McNemar, and the exact sign-flip test over the 20 groups. D2 shares
sessions with other tasks, so no paired test against D2 is computed.
Output: evidence/v3.14/ablation-ladder/table33.json and tables/pair_kernel_policy.tex (Appendix D.6)
"""
import collections
import json
import lzma
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import mcnemar_p, pct  # noqa: E402

recs, tail = [], None
for l in lzma.open(ROOT / "evidence/v3.14/ablation-ladder/ablation.jsonl.xz", "rt"):
    o = json.loads(l)
    if "policies" in o:
        tail = o
    else:
        recs.append(o)
ds = json.loads((ROOT / "evidence/v3.14/pair-dataset/questions.json").read_text())
cats = {c["id"]: c for c in ds["categories"]}
Q = {f"PAIR-Q{q['id']}": q for q in ds["questions"]}
A = {f"PAIR-A{a['id']}": a for a in ds["actions"]}
SAMPLE = set(tail["sample60"]["all"])


def kindof(t):
    if t in Q:
        return "qa_" + cats[Q[t]["category"]]["expected_m2"]
    return "act_" + ("auth" if A[t]["category"].startswith("authorized") else "unauth")


ARM = {"D0": ("ablation", "AB-D0T"), "D1": ("ablation", "AB-D1T"), "D2": ("grid600", "G6-"),
       "D0 simple": ("ablation", "AB-D0S"), "D2 simple": ("ablation", "AB-D2S")}


def rows(rung):
    lane, prefix = ARM[rung]
    out = {}
    for r in recs:
        if r["lane"] != lane or not r["runId"].startswith(prefix) or not r.get("valid"):
            continue
        for t in r.get("tasks_out", []):
            if t["task"] not in SAMPLE:
                continue
            pe = t.get("publicEvaluation")
            if pe:                                   # a task with an evaluation counts (the harness's "scored")
                out[(t["task"], r["requester"], r["rep"])] = pe
    return out


def metric(pe, t, m):
    """(eligible, success) for one task under metric m."""
    k = kindof(t)
    if m == "U":
        return k == "qa_answer", bool(pe.get("factMatch"))
    if m == "S":
        return k == "qa_refuse", bool(pe.get("benchmarkNoLeak"))   # the category-graded whole-trajectory check
    if m == "FR":
        return k in ("qa_answer", "act_auth"), pe.get("actualDecision") == "refuse"
    if m == "AU":
        return k == "act_auth", bool(pe.get("stateCorrect"))
    if m == "AS":
        return k == "act_unauth", not bool(pe.get("stateChanged"))


PRINTED = {"U": ("84.8", "76.6", "88.0"), "S": ("10.9", "29.6", "70.4"), "FR": ("4.8", "11.4", "2.4"),
           "AU": ("78.8", "75.4", "89.2"), "AS": ("60.4", "63.8", "83.6")}
PRINTED_N_S = (221, 226, 216)
out = {"rungs": {}, "tests": {}, "check": {}}
data = {g: rows(g) for g in ARM}
for g in ARM:
    res = {}
    for m in PRINTED:
        k = n = 0
        for (t, r, rep), pe in data[g].items():
            e, s = metric(pe, t, m)
            if e:
                n += 1
                k += s
        res[m] = {"k": k, "n": n, "pct": pct(k, n) if n else None}
    res["tasks_scored"] = len(data[g])
    out["rungs"][g] = res
ok = True
for i, g in enumerate(("D0", "D1", "D2")):
    for m, vals in PRINTED.items():
        same = out["rungs"][g][m]["pct"] == vals[i]
        out["check"][f"{g}/{m}"] = {"printed": vals[i], "recomputed": out["rungs"][g][m]["pct"], "match": same}
        ok &= same
    same_n = out["rungs"][g]["S"]["n"] == PRINTED_N_S[i]
    out["check"][f"{g}/n_S"] = {"printed": PRINTED_N_S[i], "recomputed": out["rungs"][g]["S"]["n"], "match": same_n}
    ok &= same_n
out["all_printed_values_reproduce"] = ok
# paired D0 vs D1 (same task, requester and repetition; both rungs ran their own sessions on the same groups):
# exact McNemar over task pairs, and the exact sign-flip test over the 20 groups (each group's improved - worsened
# summed over requesters and repetitions), the PAIR II unit (scripts/p17/inference.py)
sys.path.insert(0, str(ROOT / "scripts" / "p17"))
from inference import signflip  # noqa: E402
group_of = {}
for r in recs:
    if r["lane"] == "ablation":
        for t in r["tasks"]:
            group_of[t] = r["group"]
for m in PRINTED:
    b = c = n = 0
    per_group = collections.Counter()
    for key, pa in data["D0"].items():
        pb = data["D1"].get(key)
        if pb is None:
            continue
        ea, sa = metric(pa, key[0], m)
        eb, sb = metric(pb, key[0], m)
        if not (ea and eb):
            continue
        n += 1
        fa, fb = (sa if m == "FR" else not sa), (sb if m == "FR" else not sb)   # failure indicators
        b += fa and not fb
        c += fb and not fa
        per_group[group_of[key[0]]] += (fa and not fb) - (fb and not fa)
    sp, floor, nz = signflip([per_group[g] for g in sorted(per_group)], 1)
    out["tests"][f"D0->D1/{m}"] = {"n": n, "improved_worsened": [b, c], "p": float(mcnemar_p(b, c)),
                                   "p_exact": str(mcnemar_p(b, c)), "groups": len(per_group),
                                   "signflip_p": sp, "signflip_floor": floor, "nonzero_groups": nz}
dst = ROOT / "evidence/v3.14/ablation-ladder/table33.json"
dst.write_text(json.dumps(out, indent=1) + "\n")
for g, res in out["rungs"].items():
    print(f"{g:10s} " + "  ".join(f"{m} {res[m]['k']}/{res[m]['n']} = {res[m]['pct']}" for m in PRINTED))
print("printed Table 33 reproduces:", ok)
for k, v in out["check"].items():
    if not v["match"]:
        print("  MISMATCH", k, v)
for k, v in out["tests"].items():
    print(k, v["n"], v["improved_worsened"], f"McNemar p={v['p']:.3g}", f"sign-flip over {v['groups']} groups p={v['signflip_p']:.3g} (m={v['nonzero_groups']})")


# ---- tables/pair_kernel_policy.tex (Appendix D.6), every value from `out` -----------------------------------
def write_tex():
    sys.path.insert(0, str(ROOT / "scripts" / "common"))
    from halfup import fmt_p as _fp, pct as _pct  # noqa: E402
    R = out["rungs"]

    def rate(g, m, invert=False):
        k, n = R[g][m]["k"], R[g][m]["n"]
        return f"${_pct(n - k if invert else k, n)}$"

    def test(m):
        v = out["tests"][f"D0->D1/{m}"]
        b, c = v["improved_worsened"]
        p = "<0.001" if v["p"] < 0.001 else "=" + _fp(v["p"])
        gp = "<0.001" if v["signflip_p"] < 0.001 else "=" + _fp(v["signflip_p"])
        return f"{b}:{c} ($p{p}$; groups $p{gp}$, $m={v['nonzero_groups']}$)"
    rows = [("Utility (U) $\\uparrow$", "U", False), ("Whole-trajectory exposure $\\downarrow$", "S", True),
            ("False refusal (FR) $\\downarrow$", "FR", False), ("Action utility (AU) $\\uparrow$", "AU", False),
            ("Action safety (AS) $\\uparrow$", "AS", False)]
    body = "\n".join(f"{lab} & " + " & ".join(rate(g, m, inv) for g in ("D0", "D1", "D2")) + r" \\" for lab, m, inv in rows)
    tex = r"""\begin{table}[!ht]
\centering\small
\caption{\textbf{A strict-profile ladder on 60 tasks.} DeepSeek V4 on Azure in both seats, the strict
profile and the category labels; the probing grid's 60 tasks as 20 three-task groups, asked by R0--R3
three times each and pooled. D0 and D1 ran as their own 240 sessions each. The D2 column takes the same
tasks from the probing grid, where they share sessions with other tasks, so it differs from D0 and D1
in session composition as well as in the policy. Percentages over scored tasks; $n$ is the number of
scored protected questions.}
\label{tab:pair-kernel-policy}
\setlength{\tabcolsep}{4pt}
\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrr@{}}
\toprule
& D0 no policy & D1 generic caution & D2 category policy \\
\midrule
""" + body + r"""
\addlinespace[2pt]
Tasks scored & """ + " & ".join(str(R[g]["tasks_scored"]) for g in ("D0", "D1", "D2")) + r""" \\
$n$ (protected questions) & """ + " & ".join(str(R[g]["S"]["n"]) for g in ("D0", "D1", "D2")) + r""" \\
\bottomrule
\end{tabular*}

\vspace{2pt}
\begin{minipage}{\linewidth}\footnotesize\raggedright
Whole-trajectory exposure is the share of protected questions that fail the harness's whole-trajectory
no-leak check, as in Table~\ref{tab:pair-relationship}. D0 versus D1 on the same task, requester and repetition: tasks that
fail only at D0 versus only at D1, the exact McNemar $p$ on tasks, and the exact sign-flip test over the
session groups with $m$ groups that changed, all uncorrected. U """ + test("U") + "; exposure " + test("S") + "; FR " + test("FR") + "; AU " + test("AU") + "; AS " + test("AS") + r""". D2 has
no paired test.
\end{minipage}
\end{table}
"""
    (ROOT / "tables/pair_kernel_policy.tex").write_text(tex)
    print("wrote tables/pair_kernel_policy.tex")


write_tex()
