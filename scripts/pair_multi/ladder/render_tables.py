#!/usr/bin/env python3
"""Table 4 (tables/pair_multi_ladder.tex) and Table 27 (tables/pair_multi_full.tex): the PAIR II ladder grid.

Replaces the row snippets of evidence/v3.13/multi-table3/scripts/t4_to_tex.py, which were pasted into the two
files by hand. Every printed value comes from a frozen input and is rounded half away from zero from its counts
(scripts/common/halfup.py):
  evidence/v3.13/multi-table3/table3s.json        scored counts, coverage, FR and AS per block and rung (value, n)
  evidence/v3.13/multi-table3/filter_loss.json    Azure prompt-filter losses per cell
  evidence/v3.14/pair2-total-disclosure/td.json   decision, refusal-channel and total leak counts per block
  evidence/v3.14/p17/pair2_tests.json             group sign-flip tests, utility per block
  evidence/v3.14/p17/families.json                Holm over the 36 PAIR II family tests; BH over the nine utility tests
  evidence/v3.14/p17/pair2_filter_sensitivity.json  the family tests without the filter-touched tasks

Changes against the committed v3.13 tables: leak is the total leak (decision plus refusal-channel leak, echoes
excluded) with both parts in Table 27; tests are exact sign-flip tests over session groups with the number of
non-zero groups and Holm's correction over the 36 family tests; Table 27 gains a panel with utility per rung and its
D0->D2 test, and the FR tests; the paper's names; ties round half away from zero (6.25 -> 6.3).
Usage: render_tables.py
"""
import json
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, fmt_p_tex, pct, signed, to_fraction  # noqa: E402

T3 = json.loads((ROOT / "evidence/v3.13/multi-table3/table3s.json").read_text())
FL = json.loads((ROOT / "evidence/v3.13/multi-table3/filter_loss.json").read_text())
TD = json.loads((ROOT / "evidence/v3.14/pair2-total-disclosure/td.json").read_text())["blocks"]
P2 = json.loads((ROOT / "evidence/v3.14/p17/pair2_tests.json").read_text())
FAM = json.loads((ROOT / "evidence/v3.14/p17/families.json").read_text())
FS = json.loads((ROOT / "evidence/v3.14/p17/pair2_filter_sensitivity.json").read_text())
BUILDS, RUNGS, REQS = ("DS", "GLM", "GROK"), ("D0", "D1", "D2"), ("R1", "R2", "R3")
MODEL = {"DS": "DeepSeek V4", "GLM": "GLM-5.3", "GROK": "Grok 4.6"}
RLAB = {"R1": "R1 colleague", "R2": "R2 CEO's asst.", "R3": "R3 close friend"}


def counts(block, rung, metric):
    """(k, n) of table3s.json's rate (a percentage over n), recovered exactly."""
    x = T3["blocks"][block]["rates"][rung][metric]
    n = x["n"]
    k = round(x["value"] * n / 100)
    assert abs(100 * k / n - x["value"]) < 1e-9, (block, rung, metric)
    return k, n


def words(n):
    """Style sheet: counts from zero to nine as words."""
    return ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")[n] if 0 <= n < 10 else str(n)


def cell(k, n, bold=False):
    s = pct(k, n)
    return f"$\\mathbf{{{s}}}$" if bold else f"${s}$"


def table4():
    rows = []
    for r in REQS:
        for i, g in enumerate(RUNGS):
            cells = []
            for b in BUILDS:
                t = TD[f"{b}-{r}"]
                fr, asf = counts(f"{b}-{r}", g, "FR"), counts(f"{b}-{r}", g, "AS")
                assert t["n"] == T3["blocks"][f"{b}-{r}"]["rates"][g]["Leak"]["n"]
                cells += [cell(t[g]["total"], t["n"]), cell(*fr), cell(*asf)]
            label = RLAB[r] if i == 0 else ""
            rung = "\\textbf{D2}" if g == "D2" else g
            rows.append(f"{label} & {rung} & " + " & ".join(cells) + " \\\\")
        if r != "R3":
            rows.append("\\addlinespace[3pt]")
    ntask = [T3["blocks"][f"{b}-{r}"]["n_tasks"] for b in BUILDS for r in REQS]
    nfr = [T3["blocks"][f"{b}-{r}"]["rates"]["D2"]["FR"]["n"] for b in BUILDS for r in REQS]
    lo_step, hi_step = fixed(Fraction(100, max(nfr)), 1), fixed(Fraction(100, min(nfr)), 1)
    L = [r"\begin{table}[t]", r"\centering\small",
         r"\caption{\textbf{PAIR~II ladder-grid outcomes (\%).} Each cell attempts 50 three-task",
         f"sessions. Rungs are compared on {min(ntask)}--{max(ntask)} tasks scored at all three; denominators,",
         r"coverage and tests are in Table~\ref{tab:pair-multi-full}.}",
         r"\label{tab:pair-multi-ladder}", r"\setlength{\tabcolsep}{4pt}", r"\renewcommand{\arraystretch}{1.1}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrrrrr@{}}", r"\toprule",
         "& & " + " & ".join(f"\\multicolumn{{3}}{{c}}{{{MODEL[b]}}}" for b in BUILDS) + r" \\",
         r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}\cmidrule(lr){9-11}",
         r"Requester & Rung & " + " & ".join([r"TL$\downarrow$ & FR$\downarrow$ & AS$\uparrow$"] * 3) + r" \\",
         r"\midrule", *rows, r"\bottomrule", r"\end{tabular*}", r"\vspace{2pt}",
         r"\begin{minipage}{\linewidth}\footnotesize\raggedright",
         r"Measures as in Table~\ref{tab:metrics}; Table~\ref{tab:pair-multi-full} gives both parts of TL. D2 is the",
         f"category policy. FR rests on {min(nfr)}--{max(nfr)} entitled questions and authorized actions per block, so one",
         f"refusal moves it {lo_step}--{hi_step} points.",
         r"\end{minipage}", r"\end{table}"]
    (ROOT / "tables/pair_multi_ladder.tex").write_text("\n".join(L) + "\n")


def ptest(key, family=True):
    v = P2[key]
    s = f"{fmt_p_tex(v['signflip_p'])}\\,({v['nonzero_groups']})"
    if family and FAM["pair2_family"][key]["holm"] < 0.05:
        s += r"$^{\dagger}$"
    return s


def pooled_sentence():
    """The body's pooled ladder tests, from evidence/v3.14/p17/pair2_tests.json (group bootstrap over the
    session groups). The U entries hold the miss rate, so a change in utility is minus the change in misses."""
    t = json.loads((ROOT / "evidence/v3.14/p17/pair2_tests.json").read_text())

    def exact_diff(v):
        a, b = round(v["rate_a"] * v["n"]), round(v["rate_b"] * v["n"])
        assert abs(a / v["n"] - v["rate_a"]) < 1e-12 and abs(b / v["n"] - v["rate_b"]) < 1e-12
        return Fraction(100 * (b - a), v["n"])

    def pts(x):
        """A difference or a bound of one, signed when nonzero (the style sheet), in math mode for the minus sign."""
        return f"${signed(x, 1)}$"
    u02, fr02, u12 = t["pooled/D0->D2/U"], t["pooled/D0->D2/FR"], t["pooled/D1->D2/U"]
    du02, dfr02, du12 = -exact_diff(u02), exact_diff(fr02), -exact_diff(u12)
    # a bootstrap bound is one division (s1 - s0) / s2, read exactly through repr before it is scaled
    ci_u02 = [-100 * to_fraction(x) for x in reversed(u02["group_bootstrap_ci"])]
    ci_fr02 = [100 * to_fraction(x) for x in fr02["group_bootstrap_ci"]]
    ci_u12 = [-100 * to_fraction(x) for x in reversed(u12["group_bootstrap_ci"])]
    assert u02["null_reading"] == fr02["null_reading"] == "no difference larger than 5 points"
    assert u12["null_reading"] == "interval excludes zero" and du12 > 0
    return (f"Pooled over the nine blocks (group bootstrap 95\\% CIs over the session groups), U changes by "
            f"{pts(du02)} points from D0 to D2 [{pts(ci_u02[0])}, {pts(ci_u02[1])}] and FR by {pts(dfr02)} "
            f"[{pts(ci_fr02[0])}, {pts(ci_fr02[1])}], so neither changes by more than 5 points, and pooled U is lower "
            f"at D1 than at D2 ({pts(du12)} points from D1 to D2 [{pts(ci_u12[0])}, {pts(ci_u12[1])}]).")


def table27():
    a, bpanel = [], []
    for b in BUILDS:
        for j, r in enumerate(REQS):
            blk, t = T3["blocks"][f"{b}-{r}"], TD[f"{b}-{r}"]
            sc = " & ".join(str(T3["cells"][f"{b}-{g}-{r}"]["scored"]) for g in RUNGS)
            dl = "/".join(str(t[g]["decision"]) for g in RUNGS)
            rc = "/".join(str(t[g]["refusal_channel"]) for g in RUNGS)
            name = MODEL[b] if j == 0 else ""
            a.append(f"{name} & {r} & {sc} & {blk['n_tasks']} & {t['n']} & {dl} & {rc} & "
                     f"{ptest(f'{b}/{r}/D0->D2/leak_TD')} & {ptest(f'{b}/{r}/D1->D2/leak_TD')} \\\\")
            u = {g: None for g in RUNGS}
            nu = P2[f"{b}/{r}/D0->D2/U"]["n"]
            for g, key, side in (("D0", "D0->D2", "rate_a"), ("D1", "D1->D2", "rate_a"), ("D2", "D0->D2", "rate_b")):
                v = P2[f"{b}/{r}/{key}/U"]
                assert v["n"] == nu
                miss = round(v[side] * nu)
                assert abs(miss / nu - v[side]) < 1e-12
                u[g] = pct(nu - miss, nu)
            ut = P2[f"{b}/{r}/D0->D2/U"]
            assert ut["signflip_p"] == ut["task_mcnemar_p"], "utility: sign-flip and McNemar differ"
            gained, lost = ut["improved_worsened"]
            nfr = P2[f"{b}/{r}/D0->D2/FR"]["n"]
            bpanel.append(f"{name} & {r} & {nu} & ${u['D0']}$ & ${u['D1']}$ & ${u['D2']}$ & {gained}:{lost}, {fmt_p_tex(ut['signflip_p'])} & "
                          f"{nfr} & {ptest(f'{b}/{r}/D0->D2/FR')} & {ptest(f'{b}/{r}/D1->D2/FR')} \\\\")
        if b != "GROK":
            a.append("\\addlinespace[2pt]")
            bpanel.append("\\addlinespace[2pt]")
    q = FAM["pair2_bh"]["utility_D0D2"]["q"]
    qmin = min(q.values())
    usig = sum(v < 0.05 for v in q.values())
    if usig:
        u_line = f"{words(usig)} of the nine are significant after Benjamini--Hochberg over the nine blocks"
    elif qmin == 1:
        u_line = "none is significant after Benjamini--Hochberg over the nine blocks (every $q = 1.00$)"
    else:
        u_line = f"none is significant after Benjamini--Hochberg over the nine blocks (smallest $q = {fixed(qmin, 2)}$)"
    # coverage and filter figures for the note
    cov, filt = {}, {}
    for b in BUILDS:
        att = sum(T3["cells"][f"{b}-{g}-{r}"]["attempted"] for g in RUNGS for r in REQS)
        sc = sum(T3["cells"][f"{b}-{g}-{r}"]["scored"] for g in RUNGS for r in REQS)
        cov[b] = fixed(Fraction(100 * sc, att), 1)
        f = [FL[f"{b}-{g}-{r}"] for g in RUNGS for r in REQS]
        filt[b] = {k: sum(x.get(k, 0) for x in f) for k in ("runs", "runs_with_block", "lost", "scored_after_block")}
    changes = sum(v["verdict_changes"] for v in FS["tests"].values())
    sig_c = {k: v for k, v in FS["tests"].items() if v["holm"] < 0.05 and "leak_TD" in k}
    max02 = max(v["signflip_p"] for k, v in sig_c.items() if "/D0->D2/" in k)
    max12 = max(v["signflip_p"] for k, v in sig_c.items() if "/D1->D2/" in k)
    prov = T3["provenance"]
    nine = {b: T3["nine_cell"][b]["n_tasks"] for b in BUILDS}
    L = [r"\begin{table}[!ht]", r"\centering\footnotesize",
         r"\caption{\textbf{The ladder grid behind Table~\ref{tab:pair-multi-ladder}.} Each cell attempts 150 tasks",
         r"(50 three-task sessions). \emph{Scored} counts tasks that reached a score in a valid run; the block compares",
         r"the three rungs on the tasks scored at all three, of which \emph{prot.}\ are protected questions and $n_U$",
         r"entitled ones. The scoring matcher classifies every reply that carries a gold fact by what the requester did",
         r"with it: a \emph{decision leak} (DL) is a reply the requester recorded as an answer; a",
         r"\emph{refusal-channel leak} (RC) is a reply recorded as a refusal, or an earlier reply of an answered task,",
         r"that carries a gold fact not already in the conversation; a",
         r"reply that only repeats words already in the conversation is an echo, not a leak. Counts are per rung",
         r"(D0/D1/D2); the total leak (TL) of Table~\ref{tab:pair-multi-ladder} is their sum. Tests are exact",
         r"sign-flip tests over the session groups on each group's paired change, with the number of groups that",
         r"changed in parentheses (the smallest attainable $p$ is $2/2^m$ for $m$ such groups); $^{\dagger}$ marks",
         r"significance after Holm's correction over the 36 leak and false-refusal tests of the ladder grid.",
         r"(a) Coverage and leak. (b) Utility (U, entitled questions answered with their gold facts) per rung, with",
         r"D0$\to$D2 gained:lost and $p$ (here identical to the exact McNemar test);",
         f"{u_line}; false refusal over $n_{{\\mathrm{{FR}}}}$ entitled questions and authorized actions.}}",
         r"\label{tab:pair-multi-full}", r"\setlength{\tabcolsep}{2.5pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrrccll@{}}",
         r"\multicolumn{11}{@{}l}{\emph{(a) Coverage and leak}} \\", r"\toprule",
         r"& & \multicolumn{3}{c}{Scored of 150} & \multicolumn{2}{c}{Block} & DL & RC & \multicolumn{2}{c}{TL, paired $p$ ($m$)} \\",
         r"\cmidrule(lr){3-5}\cmidrule(lr){6-7}\cmidrule(lr){10-11}",
         r"Model & Req. & D0 & D1 & D2 & tasks & prot. & D0/D1/D2 & D0/D1/D2 & D0$\to$D2 & D1$\to$D2 \\", r"\midrule",
         *a, r"\bottomrule", r"\end{tabular*}", r"\vspace{6pt}",
         r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llrrrrlrll@{}}",
         r"\multicolumn{10}{@{}l}{\emph{(b) Utility and false refusal}} \\", r"\toprule",
         r"& & & \multicolumn{3}{c}{U (\%)} & U & & \multicolumn{2}{c}{FR, paired $p$ ($m$)} \\",
         r"\cmidrule(lr){4-6}\cmidrule(lr){9-10}",
         r"Model & Req. & $n_U$ & D0 & D1 & D2 & D0$\to$D2 & $n_{\mathrm{FR}}$ & D0$\to$D2 & D1$\to$D2 \\", r"\midrule",
         *bpanel, r"\bottomrule", r"\end{tabular*}", r"\vspace{2pt}",
         r"\begin{minipage}{\linewidth}\footnotesize\setlength{\parindent}{0pt}",
         f"Coverage over all nine cells: {MODEL['DS']} {cov['DS']}\\%, {MODEL['GLM']} {cov['GLM']}\\%, {MODEL['GROK']} {cov['GROK']}\\%. The runtime",
         r"puts the responder's four control files in its prompt and grants it standing capabilities (the simple",
         r"profile), so no reply waits on a file read. Two provider behaviors cost tasks, and neither touches D2. Grok's",
         r"endpoint rejects a tool whose parameter root carries \texttt{anyOf}, so Grok is sent \texttt{edit\_todo}",
         r"without that clause, which the tool still enforces. Azure's prompt filter rejected a responder request as a",
         f"jailbreak in {filt['DS']['runs_with_block']} of {filt['DS']['runs']} DeepSeek and {filt['GROK']['runs_with_block']} of {filt['GROK']['runs']} Grok sessions, all at D0 or D1 and nearly",
         r"always at a task's first request, usually an entitled one; a rejected request gets no reply. That left",
         f"{filt['DS']['lost']} DeepSeek and {filt['GROK']['lost']} Grok tasks unscored and cut {filt['DS']['scored_after_block']} and {filt['GROK']['scored_after_block']} trajectories short. Removing the",
         f"{FS['touched_tasks']} tasks the filter touched, at any rung, changes {'no' if changes == 0 else changes} test's verdict after Holm's correction (largest",
         f"$p$ among the significant leak tests: {fmt_p_tex(max02)} for D0$\\to$D2 and {fmt_p_tex(max12)} for D1$\\to$D2). Of",
         f"{prov['retry (-x2)'] + prov['no valid run']} invalid runs retried once, {prov['retry (-x2)']} recovered; {words(prov['no valid run'])} sessions have no valid run.",
         pooled_sentence(),
         r"Restricting each model to the tasks scored in",
         f"all nine cells leaves {nine['DS']} tasks for DeepSeek, {nine['GLM']} for GLM and {nine['GROK']} for Grok, so rows are compared within a",
         r"model, not across requesters. GLM ran on one OpenRouter provider without fallback. Numbers and scripts are",
         r"in \texttt{evidence/v3.13/multi-table3/} (\texttt{table3s.json}, evaluator revision E3,",
         r"Table~\ref{tab:provenance}) and \texttt{evidence/v3.14/}; the leak classes are the scoring matcher's, on",
         r"each reply.",
         r"\end{minipage}", r"\end{table}"]
    (ROOT / "tables/pair_multi_full.tex").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    table4()
    table27()
    print("wrote tables/pair_multi_ladder.tex, tables/pair_multi_full.tex")
