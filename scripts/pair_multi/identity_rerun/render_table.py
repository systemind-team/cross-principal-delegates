#!/usr/bin/env python3
"""Render tables/pair_identity.tex, the header comparison (Appendix D.4).

DeepSeek V4 Flash (snapshot 0731) on the ladder grid's 50 groups under the relationship policy, with and without the
identity header, relationship labels. Every rate and test comes from evidence/v3.14/p17/header_tests.json
(scripts/p17/header_tests.py, which reproduces the frozen summary's counts): the total leak, the harness's
whole-trajectory exposure (the old "Leak" row), FR, AS, U and AU on the task-requester pairs both arms scored; each test
as exact McNemar on tasks and the exact sign-flip test over the session groups. Rates round half away from zero.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fmt_p, pct  # noqa: E402

H = json.loads((ROOT / "evidence/v3.14/p17/header_tests.json").read_text())["header_comparison"]
S = json.loads((ROOT / "evidence/v3.13/multi-identity/summary.json").read_text())
REQS = (("R0", "stranger"), ("R1", "colleague"), ("R2", "CEO's asst."), ("R3", "friend"))
ROWS = (("U", "Utility (U) $\\uparrow$", True), ("TL", "Total leak (TL) $\\downarrow$", False),
        ("WTE", "Whole-trajectory exposure $\\downarrow$", False), ("FR", "False refusal (FR) $\\downarrow$", False),
        ("AS", "Action safety (AS) $\\uparrow$", True), ("AU", "Action utility (AU) $\\uparrow$", True))


def rate(key, side, success):
    v = H.get(key)
    if not v or not v["n"]:
        return "--"
    k = v[side]
    return f"${pct(v['n'] - k if success else k, v['n'])}$"


def p_(x):
    return "<0.001" if x < 0.001 else "=" + fmt_p(x)


lines = []
for metric, label, success in ROWS:
    cells = []
    for r, _ in REQS:
        if r == "R0" and metric in ("U", "FR"):     # one entitled question: not reported
            cells += ["--", "--"]
            continue
        cells += [rate(f"{r}/{metric}", "a", success), rate(f"{r}/{metric}", "b", success)]
    cells += [rate(f"pooled/{metric}", "a", success), rate(f"pooled/{metric}", "b", success)]
    lines.append(f"{label} & " + " & ".join(cells) + " \\\\")
scored = []
for r, _ in REQS:
    t = S["requesters"][r]
    scored += [f"{t['tasks_scored']['PR']}", f"{t['tasks_scored']['ID']}"]
matched = sum(S["requesters"][r]["matched"] for r, _ in REQS)
notes = []
for metric, name in (("TL", "TL"), ("FR", "FR"), ("AS", "AS")):
    parts = []
    for r, _ in REQS + (("pooled", ""),):
        v = H.get(f"{r}/{metric}")
        if v and sum(v["improved_worsened"]):
            b, c = v["improved_worsened"]
            parts.append(f"{r} {b}:{c} ($p{p_(v['mcnemar_p'])}$; groups $p{p_(v['signflip_p'])}$, $m={v['nonzero_groups']}$)")
    notes.append(f"{name}: " + "; ".join(parts))
head = " & ".join(f"\\multicolumn{{2}}{{c}}{{{r} {name}}}" for r, name in REQS)
rules = "".join(f"\\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(5))
tex = f"""\\begin{{table}}[!ht]
\\centering\\small
\\caption{{\\textbf{{The header comparison.}} DeepSeek V4 Flash (snapshot 0731) on the ladder grid's 50 groups, one
session per group, requester and arm. Both arms read the same relationship policy; in one arm a header names the
requester and its relationship; the run configuration chooses it, so it is an oracle
(Appendix~\\ref{{app:pair-identity}}). Labels are each requester's relationship labels, as in PAIR~I. Rates are on the
{matched} task--requester pairs both arms scored.}}
\\label{{tab:pair-identity}}
\\setlength{{\\tabcolsep}}{{2.4pt}}
\\begin{{tabular*}}{{\\linewidth}}{{@{{\\extracolsep{{\\fill}}}}lrrrrrrrrrr@{{}}}}
\\toprule
& {head} & \\multicolumn{{2}}{{c}}{{pooled}} \\\\
{rules}
Header & without & with & without & with & without & with & without & with & without & with \\\\
\\midrule
""" + "\n".join(lines) + f"""
\\addlinespace[2pt]
Tasks scored (of 150) & {' & '.join(scored)} & & \\\\
\\bottomrule
\\end{{tabular*}}

\\vspace{{2pt}}
\\begin{{minipage}}{{\\linewidth}}\\footnotesize\\raggedright
TL is the total leak (decision plus refusal-channel leak, echoes excluded); whole-trajectory exposure is the harness's
count of protected questions with a gold fact anywhere in the session. Tests: tasks that fail only without the header
versus only with it, exact McNemar $p$, and the exact sign-flip test over the session groups with $m$ groups that
changed. {'. '.join(notes)}. A dash marks a population the requester has no entitlement in.
\\end{{minipage}}
\\end{{table}}
"""
(ROOT / "tables/pair_identity.tex").write_text(tex)
print("wrote tables/pair_identity.tex")
