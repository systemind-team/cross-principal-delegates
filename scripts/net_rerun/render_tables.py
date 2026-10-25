#!/usr/bin/env python3
"""Render the NET tables (Appendix E.3; glossary v2 terms) from evidence/v3.13/net-rerun/net_summary.json (read only).

  tables/net_results.tex         Table 6:  primary view, with each p's exact-test floor
  tables/net_results_full.tex    Table 38: primary view and two robustness views
  tables/net_strata_results.tex  Table 39: declared strata
  tables/net_delivery.tex        Table 7:  delivery, all 24 paired edges

net_summary.json is written by scripts/net_rerun/analyse.py from contacts.jsonl and replies.jsonl.
That script writes into evidence/v3.13, which no one may modify, so this script never calls it.

Terms follow revision/glossary.md v1: forbidden and permitted arm; the judge's verdicts are "judged
disclosure" (the paper's names for L_w and L_p); the permitted arm carries no utility reading, so no column has
an arrow. Rounding: half away from zero from the unrounded value (scripts/common/halfup.py). Every p is
an exact sign-flip or McNemar p, a multiple of 1/2^m, printed with two decimals at or above 0.1 and two
significant figures below. A floor is the smallest p the sign-flip test can return over m holders
whose summed difference is not zero, 2/2^m; it is printed exactly.
"""
import json
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, fmt_p, mcnemar_p, signed  # noqa: E402

NS = json.loads((ROOT / "evidence/v3.13/net-rerun/net_summary.json").read_text())
RUNGS = ("D0", "D1", "D2")
# GLM-5.3 answers many D0 requests by calling the empty POLICY.md a configuration error
# (scripts/net_rerun/empty_policy.py); its D0 rows are marked and the note gives the counts.
EP = json.loads((ROOT / "evidence/v3.14/net-rerun-audit/empty_policy.json").read_text())["primary_edges_reps_1_2"]


def empty_policy_note():
    w, p = EP["glm/D0/withheld"], EP["glm/D0/permitted"]
    assert all(EP[f"{m}/{g}/{a}"]["configuration_error"] == 0 for m in ("deepseek", "glm") for g in RUNGS
               for a in ("withheld", "permitted") if (m, g) != ("glm", "D0"))
    assert w["configuration_error_disclosed"] == p["configuration_error_disclosed"] == 0
    return (f"$^{{\\dagger}}$GLM-5.3's D0 rows mix the no-policy condition with replies that call the empty "
            f"\\texttt{{POLICY.md}} a configuration error and decline; on its primary edges these are {w['configuration_error']} of its "
            f"{w['judged_replies']} forbidden-arm and {p['configuration_error']} of its {p['judged_replies']} "
            f"permitted-arm replies, none judged a disclosure (Appendix~\\ref{{app:net-results-detail}}).")
RUNG_NAME = {"D0": "D0: no policy", "D1": "D1: generic caution", "D2": "D2: topic policy"}   # NET's D2 is the topic policy
MODELS = (("deepseek", "DeepSeek V4"), ("glm", "GLM-5.3"))


def exact(x):
    """A floor or a sign-flip p is k/2^m; recover it exactly from the stored float."""
    fr = Fraction(x).limit_denominator(1 << 20)
    assert float(fr) == x, x
    return fr


def nonzero_holders(x):
    """m, the number of holders whose summed difference is not zero, from the floor 2/2^m."""
    fl = exact(x)
    m = (2 * fl.denominator // fl.numerator).bit_length() - 1
    assert Fraction(2, 2 ** m) == fl
    return m


def floor_str(x):
    fr = exact(x)
    return format(float(fr), "g")  # 0.25, 0.125, 0.0625: dyadic, so the decimal is exact


def ci(c):
    return f"$[{signed(c[0])}, {signed(c[1])}]$"


def check_floor(cell):
    """The stored floor must equal 2/2^m for some m, and p must not be below it."""
    fl = exact(cell["p_floor"])
    assert fl.numerator in (1, 2) and (fl.denominator & (fl.denominator - 1)) == 0, fl
    assert exact(cell["p"]) >= fl, (cell["p"], fl)


def table6():
    rows = []
    for key, name in MODELS:
        o = NS[key]
        rows.append(f"\\multicolumn{{11}}{{@{{}}l}}{{\\textit{{{name}: {o['edges']} edges, {o['holders']} holders}}}}\\\\")
        for g in RUNGS:
            x = o[g]
            check_floor(x)
            assert x["w_leaked"] == round(x["Lw"] * o["edges"]) and x["p_reached"] == round(x["Lp"] * o["edges"])
            rows.append(" & ".join([
                f"{RUNG_NAME[g] + ('$^{\\dagger}$' if (key, g) == ('glm', 'D0') else ''):<19}",
                f"{x['w_replies']}\\,/\\,{x['p_replies']}",
                fixed(Fraction(x["w_leaked"], o["edges"]), 2), fixed(Fraction(x["p_reached"], o["edges"]), 2),
                fixed(Fraction(x["w_disclosed"], x["w_replies"]), 2), fixed(Fraction(x["p_disclosed"], x["p_replies"]), 2),
                f"${signed(x['Dbar'])}$", ci(x["ci"]),
                fmt_p(exact(x["p"])), floor_str(x["p_floor"]), str(nonzero_holders(x["p_floor"]))]) + "\\\\")
        if key == "deepseek":
            rows.append("\\addlinespace[2pt]")
    body = "\n".join(rows)
    return f"""\\begin{{table}}[!ht]
\\centering\\small
\\caption{{\\textbf{{The NET run: one fact, a forbidden and a permitted requester.}} Each model's primary
edges are the non-borderline paired edges with a judged reply on both arms at every rung; two
repetitions per edge, arm and rung. Every disclosure here is judged disclosure of confidential
content by the LLM judge (DeepSeek-V4-Flash-0731, three votes, majority).}}
\\label{{tab:net-results}}
\\setlength{{\\tabcolsep}}{{3.5pt}}
\\begin{{tabular*}}{{\\linewidth}}{{@{{\\extracolsep{{\\fill}}}}lcccccr@{{\\hspace{{2pt}}}}lccc@{{}}}}
\\toprule
& replies & \\multicolumn{{2}}{{c}}{{edges disclosed}} & \\multicolumn{{2}}{{c}}{{per reply}} &
  \\multicolumn{{2}}{{c}}{{$\\bar\\Delta$ (95\\% CI)}} & $p$ & min.\\ $p$ & $m$\\\\
\\cmidrule(lr){{3-4}}\\cmidrule(lr){{5-6}}
& F\\,/\\,P & $J_{{\\mathrm{{F}}}}$ & $J_{{\\mathrm{{P}}}}$ & F & P & & & & & \\\\
\\midrule
{body}
\\bottomrule
\\end{{tabular*}}

\\vspace{{1pt}}
\\begin{{minipage}}{{\\linewidth}}\\footnotesize\\raggedright
F\\,/\\,P: forbidden arm / permitted arm. $J_{{\\mathrm{{F}}}}$, $J_{{\\mathrm{{P}}}}$: share of edges with at least one
judged disclosure on that arm. Per reply: judged disclosures over judged replies. $\\bar\\Delta$: mean over
edges of the permitted minus the forbidden per-reply rate; interval: holder-clustered bootstrap
(10{{,}}000 resamples). $p$: exact sign-flip test over holders. Min.\\ $p$: the smallest attainable $p$ of that
test here, $2/2^m$, where $m$ is the number of holders whose summed difference is not zero; no cell can
reach $0.05$. {empty_policy_note()}
\\end{{minipage}}
\\end{{table}}
"""


def full_rows(o, label, mark_d0=False):
    out = [f"\\multicolumn{{9}}{{@{{}}l}}{{\\textit{{{label}}}}}\\\\"]
    for g in RUNGS:
        x = o[g]
        check_floor(x)
        out.append(" & ".join([
            g + ("$^{\\dagger}$" if mark_d0 and g == "D0" else ""), str(x["w_leaked"]), str(x["p_reached"]),
            f"{x['w_disclosed']}/{x['w_replies']}", f"{x['p_disclosed']}/{x['p_replies']}", "",
            f"${signed(x['Dbar'], 3)}$", f"$[{signed(x['ci'][0], 3)}, {signed(x['ci'][1], 3)}]$",
            f"{fmt_p(exact(x['p']))} ({floor_str(x['p_floor'])})"]) + "\\\\")
    return out


def mc(model_key, pair):
    t = NS[model_key]["mcnemar_withheld"][pair]
    a, b = pair.split("-")
    x, y = t[f"only_{a}"], t[f"only_{b}"]
    p = mcnemar_p(x, y)
    assert abs(float(p) - t["p"]) < 1e-12
    return x, y, p


def table38():
    ds, glm = NS["deepseek"], NS["glm"]
    ds3, cds, cglm = NS["deepseek_reps123"], NS["common_edges"]["deepseek"], NS["common_edges"]["glm"]
    rows = []
    rows += full_rows(ds, f"DeepSeek V4, repetitions 1--2, {ds['edges']} edges, {ds['holders']} holders (primary)")
    rows += full_rows(ds3, f"DeepSeek V4, repetitions 1--3, same {ds3['edges']} edges")
    rows += full_rows(cds, f"DeepSeek V4, repetitions 1--2, {cds['edges']} common edges, {cds['holders']} holders")
    rows.append("\\addlinespace[2pt]")
    rows += full_rows(glm, f"GLM-5.3, repetitions 1--2, {glm['edges']} edges, {glm['holders']} holders (primary)", True)
    rows += full_rows(cglm, f"GLM-5.3, repetitions 1--2, {cglm['edges']} common edges, {cglm['holders']} holders", True)
    only_ds = sorted(set(ds["edge_ids"]) - set(cds["edge_ids"]))
    only_glm = sorted(set(glm["edge_ids"]) - set(cglm["edge_ids"]))
    a = mc("deepseek", "D0-D2"); b = mc("deepseek", "D1-D2"); c = mc("deepseek", "D0-D1")
    ga = mc("glm", "D0-D2"); gb = mc("glm", "D1-D2"); gc = mc("glm", "D0-D1")
    glm_min = min(ga[2], gb[2], gc[2])
    lo = Fraction(int(glm_min * 100), 100)  # a two-decimal bound strictly below the smallest GLM p
    assert lo < glm_min
    t3a = mc("deepseek_reps123", "D0-D2"); t3b = mc("deepseek_reps123", "D1-D2")
    one = cds["D1"]
    assert one["ci"][1] < 0 and exact(one["p"]) == exact(one["p_floor"])
    return f"""\\begin{{table}}[!ht]
\\centering\\small
\\caption{{\\textbf{{The NET run: the primary analysis and two robustness views.}} Counts behind
Table~\\ref{{tab:net-results}}. $J_{{\\mathrm{{F}}}}$ and $J_{{\\mathrm{{P}}}}$ count edges with at least one judged disclosure on the
forbidden (F) and the permitted (P) arm; the per-reply columns give judged disclosures over judged
replies; $p$ is the sign-flip test over holders with its smallest attainable value in parentheses. The third DeepSeek repetition adds chances to disclose, so it raises edge counts by
construction; per-reply rates normalize by judged replies but can still vary with repetition and reply
composition. The common view keeps the {cds['edges']} edges both models retain (DeepSeek alone keeps
edge {', edge '.join(only_ds)}, GLM alone edge {', edge '.join(only_glm)}).}}
\\label{{tab:net-results-full}}
\\setlength{{\\tabcolsep}}{{3.5pt}}
\\begin{{tabular*}}{{\\linewidth}}{{@{{\\extracolsep{{\\fill}}}}lcccccr@{{\\hspace{{2pt}}}}lc@{{}}}}
\\toprule
& \\multicolumn{{2}}{{c}}{{edges disclosed}} & \\multicolumn{{2}}{{c}}{{per reply}} & & & & \\\\
\\cmidrule(lr){{2-3}}\\cmidrule(lr){{4-5}}
Rung & $J_{{\\mathrm{{F}}}}$ & $J_{{\\mathrm{{P}}}}$ & F & P & & \\multicolumn{{2}}{{c}}{{$\\bar\\Delta$ (95\\% CI)}} & $p$ (min.)\\\\
\\midrule
""" + "\n".join(rows) + f"""
\\bottomrule
\\end{{tabular*}}

\\vspace{{2pt}}
{{\\footnotesize Exact McNemar tests on the forbidden arm's edge-level judged disclosure, primary view:
DeepSeek D0 vs D2 {a[0]}--{a[1]} ($p={fmt_p(a[2])}$), D1 vs D2 {b[0]}--{b[1]} ($p={fmt_p(b[2])}$), D0 vs D1
{c[0]}--{c[1]}; GLM D0 vs D2 {ga[0]}--{ga[1]}, D1 vs D2 {gb[0]}--{gb[1]}, D0 vs D1 {gc[0]}--{gc[1]} (all
$p>{fixed(lo, 2)}$). With the third DeepSeek repetition: D0 vs D2 {t3a[0]}--{t3a[1]}, D1 vs D2
{t3b[0]}--{t3b[1]}. The one interval that excludes zero, DeepSeek D1 on the common edges, excludes it
on the negative side, and its sign-flip $p$ equals the smallest attainable value, {floor_str(one['p_floor'])}.
{empty_policy_note()}}}
\\end{{table}}
"""


def table39():
    rows = []
    for key, name in MODELS:
        o = NS[key]
        for i, (s, lab) in enumerate((("category", "category"), ("exception", "exception"), ("no-cell", "no cell"))):
            x = o["strata"][s]
            cells = [f"{x[g]['w_disclosed']}/{x[g]['w_replies']}" for g in RUNGS] + \
                    [f"{x[g]['p_disclosed']}/{x[g]['p_replies']}" for g in RUNGS]
            rows.append(" & ".join([name if i == 0 else "", lab, str(len(x["edges"]))] + cells) + "\\\\")
        if key == "deepseek":
            rows.append("\\addlinespace[2pt]")
    sizes = [len(NS[k]["strata"][s]["edges"]) for k, _ in MODELS for s in ("category", "exception", "no-cell")]
    assert (min(sizes), max(sizes)) == (4, 7), sizes  # the caption's "Four to seven"
    return f"""\\begin{{table}}[!ht]
\\centering\\small
\\caption{{\\textbf{{The NET run by declared stratum.}} Judged disclosures over judged replies,
repetitions 1--2, on each model's primary edges. \\emph{{Category}}: the access matrix makes the fact's
category protected from the forbidden requester. \\emph{{Exception}}: the matrix permits the category to
that requester and the fact alone is forbidden. \\emph{{No cell}}: the matrix is silent and the
forbidden edge is the only protection. Four to seven edges per row cannot separate these
patterns; the table is reported because the strata were declared before execution. GLM-5.3's D0 columns
include replies that call the empty \\texttt{{POLICY.md}} a configuration error (Table~\\ref{{tab:net-results}}).}}
\\label{{tab:net-strata-results}}
\\setlength{{\\tabcolsep}}{{3.5pt}}
\\begin{{tabular*}}{{\\linewidth}}{{@{{\\extracolsep{{\\fill}}}}llccccccc@{{}}}}
\\toprule
& & & \\multicolumn{{3}}{{c}}{{forbidden arm}} & \\multicolumn{{3}}{{c}}{{permitted arm}}\\\\
\\cmidrule(lr){{4-6}}\\cmidrule(lr){{7-9}}
Model & Stratum & Edges & D0 & D1 & D2 & D0 & D1 & D2\\\\
\\midrule
""" + "\n".join(rows) + """
\\bottomrule
\\end{tabular*}
\\end{table}
"""


def table7():
    rows = []
    for key, name in MODELS:
        d = NS[key]["delivery_all_edges"]
        for i, g in enumerate(RUNGS):
            f, p = d[g]["withheld"], d[g]["permitted"]
            assert f["contacts"] == p["contacts"] == 48
            rows.append(" & ".join([name if i == 0 else "", g,
                                    str(f["delivered"]), str(f["decided"]), str(f["replies"]),
                                    str(p["delivered"]), str(p["decided"]), str(p["replies"])]) + "\\\\")
        if key == "deepseek":
            rows.append("\\addlinespace[2pt]")
    return """\\begin{table}[!ht]
\\centering\\small
\\caption{\\textbf{NET delivery, all 24 paired edges.} For the 48 exchanges per model, rung and arm
(two repetitions), the exchanges that returned a reply, the exchanges that closed with an answer or a
refusal, and the judged replies.}
\\label{tab:net-delivery}
\\setlength{\\tabcolsep}{4pt}
\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}llcccccc@{}}
\\toprule
& & \\multicolumn{3}{c}{forbidden arm} & \\multicolumn{3}{c}{permitted arm}\\\\
\\cmidrule(lr){3-5}\\cmidrule(lr){6-8}
Model & Rung & replied & decided & replies & replied & decided & replies\\\\
\\midrule
""" + "\n".join(rows) + """
\\bottomrule
\\end{tabular*}

\\vspace{1pt}
\\begin{minipage}{\\linewidth}\\footnotesize\\raggedright
GLM often replies without closing the exchange, so its replies outnumber its exchanges; a silent
exchange ends at the 22-tick limit.
\\end{minipage}
\\end{table}
"""


if __name__ == "__main__":
    for name, fn in (("net_results.tex", table6), ("net_results_full.tex", table38),
                     ("net_strata_results.tex", table39), ("net_delivery.tex", table7)):
        (ROOT / "tables" / name).write_text(fn())
        print("wrote tables/" + name)
