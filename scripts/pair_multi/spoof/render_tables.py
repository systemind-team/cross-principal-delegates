#!/usr/bin/env python3
"""P1-6: render Appendix D.5's tables and number macros from the frozen analysis (no number is typed by hand).

Reads evidence/v3.14/multi-spoof/analysis/summary.json (analyze.py), delivery/delivery.json (delivery.py over the
full lists) and manifest.json. Writes
  tables/pair_spoof.tex         rates per arm (primary items, spillover, first-reply leak, claims, coverage);
  tables/pair_spoof_tests.tex   the eight primary tests with both Holm-adjusted p-values;
  tables/pair_spoof_numbers.tex \\newcommand macros for every number the text of appendix/pair_spoof.tex cites.
Percentages round half up to one decimal from the counts.

Usage: python3 render_tables.py [--evidence evidence/v3.14/multi-spoof] [--out tables]
"""
import argparse
import collections
import json
import os
import pathlib
from decimal import ROUND_HALF_UP, Decimal

ROOT = pathlib.Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser()
ap.add_argument("--evidence", default=str(ROOT / "evidence/v3.14/multi-spoof"))
ap.add_argument("--out", default=str(ROOT / "tables"))
a = ap.parse_args()
S = json.load(open(os.path.join(a.evidence, "analysis/summary.json")))
D = json.load(open(os.path.join(a.evidence, "delivery/delivery.json")))
M = json.load(open(os.path.join(a.evidence, "manifest.json")))

ARMS = [("A0h", "header", "none (control)"), ("C1h", "header", "forged header, colleague"),
        ("C2h", "header", "claim, colleague"), ("A0n", "none", "none (control)"),
        ("C1n", "none", "forged header, colleague"), ("C3c", "none", "claim, colleague"),
        ("C3f", "none", "claim, close friend")]


def pct(k, n):
    if not n:
        return "--"
    return str(Decimal(100 * k / n).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def signed(x):
    """+8.0 or $-$10.8 (a typeset minus sign)."""
    t = f"{x:+.1f}"
    return t.replace("-", "$-$") if t.startswith("-") else t


def rate(cell):
    return pct(cell["count"], cell["n"]) if cell and cell.get("n") else "--"


def pfmt(p):
    if p is None:
        return "--"
    if p >= 0.1:
        return f"{p:.2f}"
    if p >= 0.001:
        return f"{p:.2g}" if p >= 0.01 else f"{p:.1g}"
    m, e = f"{p:.1e}".split("e")
    return f"${m}\\times10^{{{int(e)}}}$"


def claims(arm, kind):
    c = S["claims"]["this launch"].get(f"{arm} / {kind}")
    return pct(c["relationship claim, own text"], c["messages"]) if c else "--"


rows = []
for arm, pol, claim in ARMS:
    r = S["rates"].get(arm)
    if not r:
        continue
    cov = sum(v for k, v in S["coverage"].get(f"{arm} r1", {}).items() if k == "scored sessions") + \
        sum(v for k, v in S["coverage"].get(f"{arm} r2", {}).items() if k == "scored sessions")
    o1 = "TL on F1" if arm == "C3f" else "TL on O1"
    rows.append(" & ".join([arm, claim, rate(r[o1]) + ("$^{a}$" if arm == "C3f" else ""),
                            "--" if arm == "C3f" else rate(r["EXEC on O2"]), rate(r["TL on all questions"]),
                            rate(r["EXEC on all actions"]), rate(r["first-reply leak on O1"]),
                            claims(arm, "first request"), claims(arm, "follow-up request"), str(cov)]) + " \\\\")
table = r"""\begin{table}[!ht]
\centering\small
\caption{\textbf{Impersonation arms.} DeepSeek V4 Flash (snapshot 0731) in both seats, the ladder grid's 50 groups,
two sessions per group and arm, the stranger (R0) as the true requester throughout, scored on the stranger's
relationship labels. O1: the 51 questions the colleague may receive; O2: the 22 actions she may cause. Percentages of
task--session pairs. Claims: requester messages whose own text (the scripted prefix removed) matches the frozen
relationship pattern, at the first request and at follow-up requests.}
\label{tab:pair-spoof}
\setlength{\tabcolsep}{2pt}
\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrrrr@{}}
\toprule
& & \multicolumn{2}{c}{Primary} & \multicolumn{2}{c}{All tasks} & First reply & \multicolumn{2}{c}{Claims (\%)} & \\
\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){8-9}
Arm & Scripted claim & TL O1 & Exec.\ O2 & TL & Exec. & TL O1 & first & follow-up & Sess. \\
\midrule
\multicolumn{10}{@{}l}{\textit{Responder policy with the header naming the stranger (\texttt{D2R\_ID\_R0})}}\\
""" + "\n".join(rows[:3]) + "\n\\addlinespace[2pt]\n\\multicolumn{10}{@{}l}{\\textit{Responder policy without the header (\\texttt{D2R\\_PRINCIPLES})}}\\\\\n" + "\n".join(rows[3:]) + r"""
\bottomrule
\end{tabular*}

\vspace{2pt}
\begin{minipage}{\linewidth}\footnotesize\raggedright
$^{a}$ C3f's primary tasks are the 10 questions the close friend may receive; the friend may cause none of the
actions. TL is the total leak (decision plus refusal-channel leak, echoes excluded). Exec.: the action changed state.
Sess.: scored sessions of 100. Q324 is left out of every question count (its gold fact ``AI'' occurs in the
forged header).
\end{minipage}
\end{table}
"""

tests = []
for k, v in S["primary"].items():
    s, rest = k.split(" vs ")
    c, metric = rest.split(" / ")
    lo, hi = v["newcombe_ci"]
    tests.append(" & ".join([s, "TL, O1" if metric.startswith("TL") else "Exec., O2",
                             f"{v['count_a']}/{v['pairs']}, {v['count_b']}/{v['pairs']}",
                             f"{signed(100 * v['diff'])} [{signed(100 * lo)}, {signed(100 * hi)}]",
                             f"{v['a_only']}:{v['b_only']}", pfmt(v["mcnemar_p_holm"]),
                             f"{pfmt(v['signflip_p_holm'])} ({v['nonzero_groups']})",
                             "yes" if v["counts"] else "no"]) + " \\\\")
tests_tex = r"""\begin{table}[!ht]
\centering\small
\caption{\textbf{The eight primary tests.} Each impersonation arm versus the control in the same launch with the same
responder policy (C1h and C2h versus A0h, C1n and C3c versus A0n), paired by group, task and replicate. McNemar: exact, two-sided, over task--replicate pairs. Sign
flip: exact, two-sided, over groups, on each group's (impersonation only $-$ control only) count. Both sets of eight
p-values are Holm-adjusted; a result counts only if both adjusted p-values are below 0.05. Difference: points,
impersonation minus control, with Newcombe's paired 95\% interval. Groups: groups with a non-zero difference.}
\label{tab:pair-spoof-tests}
\setlength{\tabcolsep}{2pt}\footnotesize
\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lllllrll@{}}
\toprule
Arm & Outcome & Arm, control & Difference [95\%] & Discordant & McNemar & Sign flip (groups) & Counts \\
\midrule
""" + "\n".join(tests) + r"""
\bottomrule
\end{tabular*}
\end{table}
"""

# delivery and coverage, per arm (both replicates): coverage from analyze.py, delivery counts over every scored
# session's run folder from delivery.json
rowsd = []
for arm, pol, claim in ARMS:
    cov = collections.Counter()
    for rep in (1, 2):
        cov.update(S["coverage"].get(f"{arm} r{rep}", {}))
    if not cov:
        continue
    drows = [r for k, r in D["rows"].items() if r.get("arm") == arm and r.get("gate") is True]
    if arm in ("A0h", "A0n"):
        stored = f"0 of {sum(r['stored_requests'] for r in drows):,}" if all(r["stored_with_prefix_or_marker"] == 0 for r in drows) else "see text"
        turns = f"0 of {sum(r['responder_turns'] for r in drows):,}" if all(r["responder_turns_with_any_prefix"] == 0 for r in drows) else "see text"
    else:
        stored = f"{sum(r['stored_with_prefix'] for r in drows):,} of {sum(r['stored_requests'] for r in drows):,}"
        turns = f"{sum(r['responder_turns_with_prefix'] for r in drows):,} of {sum(r['responder_turns'] for r in drows):,}"
    own = sum(r["requester_calls_with_prefix"] + r["requester_prompts_with_prefix"] for r in drows)
    rowsd.append(" & ".join([arm, str(cov["slots"]), str(cov["valid at the first attempt"]), str(cov["valid after the rerun"]),
                             str(cov["no valid run"]), str(cov["excluded: route"]), str(cov["scored sessions"]), stored, turns,
                             str(own), str(sum(r["non_relace_calls"] for r in drows))]) + " \\\\")
delivery_tex = r"""\begin{table}[!ht]
\centering\small
\caption{\textbf{Coverage and delivery of the impersonation arms.} Sessions per arm over both replicates. A session is
valid when every task was evaluated, the requester sent at least one request, and every provider call was served by the pinned
upstream; an invalid session was rerun once. Valid: at the first attempt; Rerun: valid after the rerun; Missing: no
valid run; Route: dropped for another upstream. Stored and Prompts count the scored sessions' requests stored by
\SharedOS{} and responder prompts whose request begins with the arm's claim (for the controls, any claim text). Req.:
the requester's own tool calls and prompts that contain the claim. Other: provider calls served by another upstream.}
\label{tab:pair-spoof-delivery}
\setlength{\tabcolsep}{2.4pt}
\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrrllrr@{}}
\toprule
Arm & Slots & Valid & Rerun & Missing & Route & Scored & Stored & Prompts & Req. & Other \\
\midrule
""" + "\n".join(rowsd) + r"""
\bottomrule
\end{tabular*}
\end{table}
"""

# number macros: \spoofnum{<key>} for every number the text of appendix/pair_spoof.tex cites
nums = {}
for k, v in S["primary"].items():
    s_, rest = k.split(" vs ")
    c_, metric = rest.split(" / ")
    tag = f"{s_}-{'TL' if metric.startswith('TL') else 'EXEC'}"
    lo, hi = v["newcombe_ci"]
    nums.update({f"{tag}-arm": f"{v['count_a']}/{v['pairs']}", f"{tag}-ctl": f"{v['count_b']}/{v['pairs']}",
                 f"{tag}-armpct": pct(v["count_a"], v["pairs"]), f"{tag}-ctlpct": pct(v["count_b"], v["pairs"]),
                 f"{tag}-diff": signed(100 * v["diff"]), f"{tag}-lo": signed(100 * lo), f"{tag}-hi": signed(100 * hi),
                 f"{tag}-mcnemar": pfmt(v["mcnemar_p_holm"]), f"{tag}-signflip": pfmt(v["signflip_p_holm"]),
                 f"{tag}-groups": str(v["nonzero_groups"]), f"{tag}-counts": "yes" if v["counts"] else "no"})
for k, v in S["first_request"].items():
    tag = k.split(" vs ")[0] + "-FIRST"
    nums.update({f"{tag}-arm": f"{v['count_a']}/{v['pairs']}", f"{tag}-ctl": f"{v['count_b']}/{v['pairs']}",
                 f"{tag}-p": pfmt(v["mcnemar_p"]), f"{tag}-pbh": pfmt(v["mcnemar_p_bh"])})
for arm, _, _ in ARMS:
    for kind, short in (("first request", "first"), ("follow-up request", "followup")):
        c_ = S["claims"]["this launch"].get(f"{arm} / {kind}")
        if c_:
            nums[f"{arm}-claims-{short}"] = f"{c_['relationship claim, own text']}/{c_['messages']}"
            nums[f"{arm}-claims-{short}-pct"] = pct(c_["relationship claim, own text"], c_["messages"])
tot = collections.Counter()
for k_, v in S["coverage"].items():
    tot.update(v)
nums.update({f"cov-{k_.replace(' ', '-').replace(':', '')}": str(v) for k_, v in tot.items()})
ds = D["summary"]
nums.update({"del-runfolders": str(ds["sessions_with_a_run_folder"]), "del-gatepass": str(ds["gate_pass"]),
             "del-otherupstream": str(ds["non_relace_calls"]), "del-requestercalls": str(ds["requester_calls_with_prefix"]),
             "del-requesterprompts": str(ds["requester_prompts_with_prefix"]), "del-quoted": str(ds["replies_quoting_prefix"])})
# secondary and reference numbers the text cites
def cnt(c):
    return f"{c['count']}/{c['n']}"
cf = S["close_friend"]["C3f vs A0n / TL on F1"]
nums.update({"C3f-F1-arm": f"{cf['count_a']}/{cf['pairs']}", "C3f-F1-ctl": f"{cf['count_b']}/{cf['pairs']}",
             "C3f-F1-p": pfmt(cf["mcnemar_p"]), "C3f-F1-signflip": pfmt(cf["signflip_p"]), "C3f-F1-groups": str(cf["nonzero_groups"]),
             "C3f-O1": cnt(S["rates"]["C3f"]["TL on O1"]), "A0n-O1": cnt(S["rates"]["A0n"]["TL on O1"])})
sp = S["spillover"]
for arm, ctl in (("C1n", "A0n"), ("C3c", "A0n"), ("C1h", "A0h"), ("C2h", "A0h")):
    ra, rq = sp[f"{arm} vs {ctl} / EXEC on rest_actions"], sp[f"{arm} vs {ctl} / TL on rest_questions"]
    nums[f"{arm}-restA"] = f"{ra['count_a']}/{ra['pairs']}"
    nums[f"{arm}-restQ"] = f"{rq['count_a']}/{rq['pairs']}"
    nums[f"{arm}-canonical"] = cnt(S["rates"][arm]["EXEC, canonically refused"])
fh = S["format_and_header"]
for k, tag in (("C1h vs C2h / TL on O1", "fmt-h"), ("C1n vs C3c / TL on O1", "fmt-n"), ("C2h vs C3c / TL on O1", "hdr-TL"),
               ("C2h vs C3c / EXEC on O2", "hdr-EXEC")):
    v = fh[k]
    nums.update({f"{tag}-a": str(v["count_a"]), f"{tag}-b": str(v["count_b"]), f"{tag}-pairs": str(v["pairs"]),
                 f"{tag}-p": pfmt(v["mcnemar_p"])})
rf = S["references"]
nums.update({"ref-ceiling-TL": cnt(rf["runtime says colleague (10-02 ID-R1 on R0 labels)"]["TL on O1"]),
             "ref-ceiling-EXEC": cnt(rf["runtime says colleague (10-02 ID-R1 on R0 labels)"]["EXEC on O2"]),
             "ref-persona-TL": cnt(rf["persona only, no header (10-02 PR-R1 on R0 labels)"]["TL on O1"]),
             "ref-persona-EXEC": cnt(rf["persona only, no header (10-02 PR-R1 on R0 labels)"]["EXEC on O2"])})
h = S["honest_claim_reading"]["C3c"]
nums.update({"honest-FR": cnt(h["false refusal, entitled questions"]), "honest-U": cnt(h["utility, entitled questions"]),
             "honest-ref-FR": cnt(h["reference false refusal"]), "honest-ref-U": cnt(h["reference utility"])})
for tag, c_ in (("honest", h["utility, entitled questions"]), ("honest-ref", h["reference utility"])):
    nums[f"{tag}-n"] = str(c_["n"])
nums.update({"honest-U-count": str(h["utility, entitled questions"]["count"]),
             "honest-FR-count": str(h["false refusal, entitled questions"]["count"]),
             "honest-ref-U-count": str(h["reference utility"]["count"]),
             "honest-ref-FR-count": str(h["reference false refusal"]["count"])})
nm = S["names_in_replies"]
for arm in ("C1h", "C2h"):
    nums[f"{arm}-bothnames"] = f"{nm[arm]['Riley and a claimed name']:,}".replace(",", "{,}")
    nums[f"{arm}-replies"] = f"{nm[arm]['replies']:,}".replace(",", "{,}")
ag = S["against_1002"]
nums["drift-A0h"] = " and ".join(f"{ag[f'A0h r{r} vs 10-02 ID-R0 / TL on all questions']['a_only']}:{ag[f'A0h r{r} vs 10-02 ID-R0 / TL on all questions']['b_only']}" for r in (1, 2))
nums["drift-A0n"] = " and ".join(f"{ag[f'A0n r{r} vs 10-02 PR-R0 / TL on all questions']['a_only']}:{ag[f'A0n r{r} vs 10-02 PR-R0 / TL on all questions']['b_only']}" for r in (1, 2))
# the design's detectable effects (design/power.json, joint rule, 80% power, first Holm step)
PW = json.load(open(os.path.join(a.evidence, "design/power.json")))
for label, tag in (("TL on O1, with the header", "TLh"), ("EXEC on O2, with the header", "EXh"),
                   ("TL on O1, without the header", "TLn"), ("EXEC on O2, without the header", "EXn")):
    vals = sorted(r["joint_rule_increase_points_alpha_0.00625"] for r in PW["rows"] if r["outcome"] == label)
    nums[f"power-{tag}"] = f"{vals[0]:g}--{vals[-1]:g}"
# failures and the claim range of the impersonation arms
fails = [l.rstrip("\n").split("\t") for l in open(os.path.join(a.evidence, "run/failures.tsv")) if l.strip()][1:]
nums["fail-harness"] = str(len(fails))
nums["fail-route"] = str(len(D["summary"]["gate_fail"]))
imp = [float(pct(S["claims"]["this launch"][f"{x} / follow-up request"]["relationship claim, own text"],
                 S["claims"]["this launch"][f"{x} / follow-up request"]["messages"])) for x in ("C1h", "C2h", "C1n", "C3c", "C3f")]
nums["claims-imp-min"], nums["claims-imp-max"] = f"{min(imp):.1f}", f"{max(imp):.1f}"
firsts = [S["claims"]["this launch"][f"{x} / first request"]["relationship claim, own text"] for x, _, _ in ARMS]
nums["claims-first-min"], nums["claims-first-max"] = str(min(firsts)), str(max(firsts))
nums["prefix-class-changes"] = str(sum(S["prefix_changes_a_class"].values()))
if M.get("final_cost"):
    nums["cost-ledger"] = f"{M['final_cost'].get('ledger_cash_usd', 0):.2f}"
import re as _re
for k_, v in list(nums.items()):
    if _re.fullmatch(r"\d+/\d+", v):
        nums[f"{k_}-of"] = v.replace("/", " of ")
numbers_tex = "".join(
    f"\\expandafter\\def\\csname spoof@{k_}\\endcsname{{{v}}}\n" for k_, v in sorted(nums.items())) + \
    "\\providecommand{\\spoofnum}[1]{\\csname spoof@#1\\endcsname}\n"

os.makedirs(a.out, exist_ok=True)
open(os.path.join(a.out, "pair_spoof_numbers.tex"), "w").write(
    "% Generated by scripts/pair_multi/spoof/render_tables.py from the frozen analysis. Use \\spoofnum{key}.\n" + numbers_tex)
open(os.path.join(a.out, "pair_spoof_delivery.tex"), "w").write("% Generated by scripts/pair_multi/spoof/render_tables.py from the frozen analysis.\n" + delivery_tex)
open(os.path.join(a.out, "pair_spoof.tex"), "w").write("% Generated by scripts/pair_multi/spoof/render_tables.py from the frozen analysis.\n" + table)
open(os.path.join(a.out, "pair_spoof_tests.tex"), "w").write("% Generated by scripts/pair_multi/spoof/render_tables.py from the frozen analysis.\n" + tests_tex)
print("wrote", a.out)
