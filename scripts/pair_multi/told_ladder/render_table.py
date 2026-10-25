#!/usr/bin/env python3
"""Render tables/pair_told_ladder.tex (the header ladder, Appendix D.4).

Only measured rows: DeepSeek V4 Flash (snapshot 0731) with and without the header; the estimated rows were removed.
Leak is the total leak (decision plus refusal-channel leak, echoes excluded) from
evidence/v3.14/total-disclosure/pair2_td.json; FR, AS and U from evidence/v3.13/multi-told/summary.json. Every test is
given twice: exact McNemar on tasks and the exact sign-flip test over session groups with m, the number of groups
that changed, from evidence/v3.14/p17/header_tests.json. Rates are rounded half away from zero from their counts.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fmt_p, pct  # noqa: E402

S = json.loads((ROOT / "evidence/v3.13/multi-told/summary.json").read_text())
P = S["pooled"]
TDC = json.loads((ROOT / "evidence/v3.14/total-disclosure/pair2_td.json").read_text())["header_ladder"]["cells"]
HT = json.loads((ROOT / "evidence/v3.14/p17/header_tests.json").read_text())["header_ladder"]
ROWS = (("AZ-D0", "Azure", "no", "D0"), ("AZ-D1", "Azure", "no", "D1"), ("AZ-D2", "Azure", "no", "D2"),
        ("CTRL-D2", "OpenRouter", "no", "D2"),
        ("TOLD-D0", "OpenRouter", "yes", "D0"), ("TOLD-D1", "OpenRouter", "yes", "D1"),
        ("TOLD-D2", "OpenRouter", "yes", "D2"))
METRICS = ("TL", "FR", "AS", "U")


def cell(row, metric):
    if metric == "TL":
        return f"${pct(TDC[row]['TD'], TDC[row]['n'])}$"
    m = P["rates"][row].get(metric)
    if not m:
        return "--"
    assert abs(100 * m["count"] / m["n"] - m["pct"]) < 0.051, (row, metric)
    return f"${pct(m['count'], m['n'])}$"


def p_(x):
    """Glossary v2 style: two significant figures (two decimals at 0.1 and above), "< 0.001" below that."""
    return "<0.001" if x < 0.001 else "=" + fmt_p(x)


def test(pair, metric):
    """improved:worsened (failures fewer:more at the second row), McNemar p, group sign-flip p (m)."""
    v = HT[f"{pair}/{metric}"]
    b, c = v["improved_worsened"]
    return f"{b}:{c} ($p{p_(v['mcnemar_p'])}$; groups $p{p_(v['signflip_p'])}$, $m={v['nonzero_groups']}$)"


lines = []
for i, (key, route, told, rung) in enumerate(ROWS):
    if i in (3, 4):
        lines.append("\\addlinespace[2pt]")
    lines.append(f"{route} & {told} & {rung} & " + " & ".join(cell(key, m) for m in METRICS) + " \\\\")
n = {m: P["rates"]["TOLD-D2"][m]["n"] for m in ("FR", "AS", "U")}
n["TL"] = TDC["TOLD-D2"]["n"]
assert all(TDC[r]["n"] == n["TL"] for r, *_ in ROWS) and all(P["rates"][r][m]["n"] == n[m] for r, *_ in ROWS for m in ("FR", "AS", "U"))
tex = f"""\\begin{{table}}[!ht]
\\centering\\small
\\caption{{\\textbf{{The header ladder.}} DeepSeek V4 Flash (snapshot 0731) on the ladder grid's 50 groups, R1--R3
pooled, one session per group, requester and cell; category labels, as in
Table~\\ref{{tab:pair-multi-ladder}}. TL is the total leak. Rates on the {P['tasks']} task--requester pairs that every row scored
({n['TL']} protected questions, {n['FR']} entitled questions and authorized actions, {n['AS']} unauthorized
actions, {n['U']} entitled questions).}}
\\label{{tab:pair-told-ladder}}
\\setlength{{\\tabcolsep}}{{4pt}}
\\begin{{tabular*}}{{\\linewidth}}{{@{{\\extracolsep{{\\fill}}}}lllrrrr@{{}}}}
\\toprule
Route & Header & Rung & TL$\\downarrow$ & FR$\\downarrow$ & AS$\\uparrow$ & U$\\uparrow$ \\\\
\\midrule
""" + "\n".join(lines) + f"""
\\bottomrule
\\end{{tabular*}}

\\vspace{{2pt}}
\\begin{{minipage}}{{\\linewidth}}\\footnotesize\\raggedright
Each test gives the tasks that fail only in the first row versus only in the second (a failure is a leak, a refusal,
a state change or a missed answer), the exact McNemar $p$ on tasks, and the exact sign-flip test over the session groups
with $m$ groups that changed. The header alone (D2 without versus with the header, same route): TL
{test("CTRL-D2 vs TOLD-D2", "TL")}, FR {test("CTRL-D2 vs TOLD-D2", "FR")}, AS {test("CTRL-D2 vs TOLD-D2", "AS")}, U
{test("CTRL-D2 vs TOLD-D2", "U")}. The route alone (Azure versus OpenRouter D2, both without the header): TL
{test("AZ-D2 vs CTRL-D2", "TL")}, FR {test("AZ-D2 vs CTRL-D2", "FR")}. With the header, D0 versus D2: TL
{test("TOLD-D0 vs TOLD-D2", "TL")}, FR {test("TOLD-D0 vs TOLD-D2", "FR")}, AS {test("TOLD-D0 vs TOLD-D2", "AS")}. With
the header versus the ladder grid's own rows: at D0, TL {test("AZ-D0 vs TOLD-D0", "TL")}, FR {test("AZ-D0 vs TOLD-D0", "FR")},
AS {test("AZ-D0 vs TOLD-D0", "AS")}; at D1, TL {test("AZ-D1 vs TOLD-D1", "TL")}, FR {test("AZ-D1 vs TOLD-D1", "FR")}, AS
{test("AZ-D1 vs TOLD-D1", "AS")}; at D2, TL {test("AZ-D2 vs TOLD-D2", "TL")}. Those comparisons change the header and the
route together: the rows without the header ran on Azure, whose prompt filter rejected some D0 and D1 requests, and the
route alone was compared at D2 only.
\\end{{minipage}}
\\end{{table}}
"""
(ROOT / "tables/pair_told_ladder.tex").write_text(tex)
print("wrote tables/pair_told_ladder.tex")
