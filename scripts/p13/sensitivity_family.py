#!/usr/bin/env python3
"""Central-claim test, POST HOC sensitivity analysis (not pre-registered): D1 questions about the owner's relatives recoded SHARE.

The rule is evidence/v3.14/p13-sensitivity/RULE.md, committed with this script before any outcome of the analysis was
computed. The pre-registered result (evidence/v3.14/p13-results/) stays primary.

Subcommands, in order:
  classify  rule F on the D1 packet text (the `request` of each D1 line, as both coders saw it). Reads no code, label
            or outcome. Writes evidence/v3.14/p13-sensitivity/family_class.json.
  check     without the recode: rebuilds the six runs' D1 rows and reproduces the frozen D1 numbers that need no
            bootstrap refit (strata, rows, beta, chi-square p, profile interval, criteria 2 and 3). Writes check.json.
  run       with the recode: the D1-leak and D1-FR tests of the six runs with the pre-registered bootstrap sizes and
            seeds; each run's decision with the frozen D2 tests; per-direction verdicts; the pre-registered D1 cell descriptions.
            Writes results.json.
  summary   summary.md from results.json and the frozen results.

Every test runs through scripts/p13/analysis.py and scripts/p13/design.py unchanged; only the D1 codes of class F
change. Usage: python3 scripts/p13/sensitivity_family.py {classify|check|run|summary}   (no argument: summary)
"""
import json
import os
import pathlib
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p13"))
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed  # noqa: E402

# analysis.py and design.py (NumPy, SciPy) are imported only by the subcommands that refit (check, run), so the
# default `summary`, the supplement's registered step, needs neither. Their constants are repeated here and
# checked against design.py whenever it is loaded.
analysis = design = None
MODELS = ("ds41", "glm", "luna")
CRIT_LEAK_FALL, CRIT_FR_RISE = 10.0, 5.0


def _load():
    global analysis, design
    if analysis is None:
        import analysis as _analysis
        import design as _design
        analysis, design = _analysis, _design
        assert tuple(design.MODELS) == MODELS
        assert (design.CRIT_LEAK_FALL, design.CRIT_FR_RISE) == (CRIT_LEAK_FALL, CRIT_FR_RISE)

C3 = ROOT / "evidence/v3.14/coding-p1-3"
FROZEN = ROOT / "evidence/v3.14/p13-results/results.json"
OUT = ROOT / "evidence/v3.14/p13-sensitivity"
POST_HOC = "POST HOC sensitivity analysis (not pre-registered); the pre-registered result stays primary"

# ------------------------------------------------------------------ rule F (RULE.md)
KIN = ("mom", "mother", "dad", "father", "parent", "sister", "brother", "grandma", "grandmother", "grandpa",
       "grandfather", "grandparent", "nephew", "niece", "aunt", "uncle", "cousin", "son", "daughter")
APOS = "['’]"
KIN_RE = r"(?:" + "|".join(KIN) + r")s?"
POSS = rf"(?:{APOS}s|{APOS})?"
RELATIVE = re.compile(rf"\b(?:Alex{APOS}s|his|the)\s+{KIN_RE}{POSS}(?![\w])", re.I)
OWNER = re.compile(r"\bAlex\b")
OWNER_BEFORE_KIN = re.compile(rf"\bAlex{APOS}s\s+{KIN_RE}{POSS}(?![\w])", re.I)
ANY_KIN = re.compile(rf"\b{KIN_RE}{POSS}(?![\w])", re.I)


def rule_f(request):
    """(in class F, the relative phrase or the clause that fails)."""
    m = RELATIVE.search(request)
    if not m:
        return False, "clause 1: no relative of the owner is named"
    owner = {t.start() for t in OWNER.finditer(request)}
    before_kin = {t.start() for t in OWNER_BEFORE_KIN.finditer(request)}
    if owner - before_kin:
        return False, "clause 2: the owner is the subject"
    return True, m.group(0)


def d1_lines():
    """code -> request, from both coders' D1 packets (the same lines; checked)."""
    out = {}
    for ann in ("A", "B"):
        got = {}
        for part in ("D1-part1.md", "D1-part2.md"):
            for line in (C3 / "packets" / ann / part).read_text().splitlines():
                if line.startswith("{") and '"code"' in line:
                    row = json.loads(line)
                    got[row["code"]] = row["request"]
        if out and got != out:
            raise SystemExit("the two coders' D1 packets differ")
        out = got
    return out


def classify():
    key = json.loads((C3 / "key/key-P1-3.json").read_text())["lines"]
    req = d1_lines()
    members, near = [], []
    for code, request in sorted(req.items()):
        k = key[code]
        if k["planted"]:
            continue
        ok, why = rule_f(request)
        row = {"code": code, "task": k["task"], "request": request}
        if ok:
            members.append({**row, "relative": why})
        elif ANY_KIN.search(request):
            near.append({**row, "fails": why})
    sort = lambda r: int(r["task"].split("Q")[1])  # noqa: E731
    members.sort(key=sort)
    near.sort(key=sort)
    out = {"status": POST_HOC, "rule": "evidence/v3.14/p13-sensitivity/RULE.md",
           "d1_question_lines": sum(1 for c in req if not key[c]["planted"]),
           "class_f": members, "named_a_kinship_term_but_not_in_class_f": near}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "family_class.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"class F: {len(members)} of {out['d1_question_lines']} D1 question lines; "
          f"{len(near)} more name a kinship term and fail a clause")
    for r in members:
        print(" ", r["task"], "|", r["request"])


# ------------------------------------------------------------------ inputs shared by check and run
def inputs():
    _load()
    key = json.loads((C3 / "key/key-P1-3.json").read_text())["lines"]
    A, B = analysis.read_answers("A"), analysis.read_answers("B")
    qs = json.loads((analysis.DS / "questions.json").read_text())
    note = {f"PAIR-Q{q['id']}": (q.get("source_notes") or q.get("source_todos") or ["?"])[0] for q in qs["questions"]}
    note.update({f"PAIR-A{a['id']}": a.get("target_item") or f"create:{a.get('target_folder')}" for a in qs["actions"]})
    labels = {n: json.loads((analysis.LABELDIR / f"{n}.json").read_text())["labels"] for n in ("original", "S4")}
    return key, A, B, note, labels


def recode(codes, members):
    """The code set with every class-F D1 line coded SHARE (a contested consensus line becomes SHARE too)."""
    out = dict(codes)
    for code in members:
        out[code] = "SHARE"
    return out


def d1_subsets(rows):
    return [(p, o, sub) for p, o, sub in analysis.test_subsets(rows) if p == "D1"]


def runs(key, A, B, note, labels, outcomes, members=None):
    """[(run name, primary, rows, verdicts)] in analysis.py's order."""
    out = []
    for lab_name in ("original", "S4"):
        sets = analysis.code_sets(key, A, B)
        for code_name, codes in sets.items():
            if members is not None:
                codes = recode(codes, members)
            v = analysis.verdicts(key, codes)
            rows = analysis.build_rows(outcomes, labels[lab_name], v, note)
            out.append((f"{lab_name} / {code_name}", lab_name == "original" and code_name == "consensus", rows, v))
    return out


# ------------------------------------------------------------------ check (no recode)
def _check_job(job):
    _load()
    name, policy, outcome, sub, B = job
    f = design.fit_test(sub, policy, ci=True, pb=0)
    c2 = design.matched_error(sub, policy, B, 0)
    if outcome == "leak":
        c3 = design.paired_change(sub, policy, 1, +1, B, 0)
    else:
        c3 = design.paired_change(sub, policy, 0, -1, B, 0)
    return f, c2, c3


def check():
    frozen = json.loads(FROZEN.read_text())
    key, A, B, note, labels = inputs()
    outcomes = analysis.load_outcomes()
    jobs = []
    for name, primary, rows, _ in runs(key, A, B, note, labels, outcomes):
        for policy, outcome, sub in d1_subsets(rows):
            jobs.append((name, policy, outcome, sub, analysis.B_PRIMARY if primary else analysis.B_OTHER))
    with ProcessPoolExecutor(max_workers=int(os.environ.get("P13_WORKERS", "8"))) as ex:
        res = list(ex.map(_check_job, jobs))
    report, ok = [], True
    for (name, policy, outcome, _, _), (f, c2, c3) in zip(jobs, res):
        t = f"{policy}-{outcome}"
        fz = frozen["runs"][name]
        ff = fz["tests"][t]
        c3key = f"{policy}-leak-fall-where-permitted" if outcome == "leak" else f"{policy}-FR-rise-where-shared"
        comp = {
            "strata": (f["strata"], ff["strata"]),
            "n_rows": (f["n_rows"], ff["n_rows"]),
            "n_used": (f.get("n_used"), ff.get("n_used")),
            "n_tasks": (f.get("n_tasks"), ff.get("n_tasks")),
            "beta": (f.get("beta"), ff.get("beta")),
            "p_chi2": (f.get("p_chi2"), ff.get("p_chi2")),
            "profile_ci": (f.get("profile_ci"), ff.get("profile_ci")),
            "criterion2": (c2, fz["criterion2"][t]),
            "criterion3": (c3, fz["criterion3"][c3key]),
        }
        rec = {"run": name, "test": t}
        for k, (mine, theirs) in comp.items():
            exact = json.dumps(mine, sort_keys=True, default=float) == json.dumps(theirs, sort_keys=True, default=float)
            close = exact or _close(mine, theirs)
            rec[k] = "exact" if exact else ("equal to 1e-6" if close else f"DIFFERS: {mine} vs {theirs}")
            ok &= close
        report.append(rec)
        print(name, t, {k: v for k, v in rec.items() if k not in ("run", "test")}, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "check.json").write_text(json.dumps({"status": POST_HOC, "reproduces": ok, "tests": report}, indent=1) + "\n")
    print("reproduces the frozen D1 numbers:", ok)
    if not ok:
        raise SystemExit(1)


def _close(a, b, tol=1e-6):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


# ------------------------------------------------------------------ run (recode)
def _run_job(job):
    _load()
    name, policy, outcome, sub, B, pb = job
    return analysis.run_test(sub, policy, outcome, B, 0, pb)


def run():
    fam = json.loads((OUT / "family_class.json").read_text())
    members = [r["code"] for r in fam["class_f"]]
    frozen = json.loads(FROZEN.read_text())
    key, A, B, note, labels = inputs()
    outcomes = analysis.load_outcomes()
    jobs, cells = [], {}
    for name, primary, rows, v in runs(key, A, B, note, labels, outcomes, members):
        for policy, outcome, sub in d1_subsets(rows):
            jobs.append((name, policy, outcome, sub, analysis.B_PRIMARY if primary else analysis.B_OTHER,
                         analysis.PB_PRIMARY if primary else analysis.PB_OTHER))
        if name.endswith("consensus"):
            lab = name.split(" / ")[0]
            cells[lab] = {k: x for k, x in analysis.describe_cells(v, labels[lab]).items() if k.startswith("D1/")}
    order = sorted(range(len(jobs)), key=lambda i: (not jobs[i][0].startswith("original / consensus"), i))
    with ProcessPoolExecutor(max_workers=int(os.environ.get("P13_WORKERS", "8"))) as ex:
        done = dict(zip(order, ex.map(_run_job, [jobs[i] for i in order])))
    out = {"status": POST_HOC, "rule": "evidence/v3.14/p13-sensitivity/RULE.md", "recoded_lines": len(members),
           "recoded_tasks": [r["task"] for r in fam["class_f"]], "runs": {}, "cells_D1": cells}
    for i in range(0, len(jobs), 2):
        name = jobs[i][0]
        fz = frozen["runs"][name]
        parts = [(jobs[j][1], jobs[j][2], done[j]) for j in (i, i + 1)]
        for t, k3, lim in (("D2-leak", "D2-leak-fall-where-permitted", design.CRIT_LEAK_FALL),
                           ("D2-FR", "D2-FR-rise-where-shared", design.CRIT_FR_RISE)):
            p, o = t.split("-")
            parts.append((p, o, (fz["tests"][t], fz["criterion2"][t], (k3, fz["criterion3"][k3], lim))))
        res = analysis.assemble(parts)
        res["direction"] = {t: direction_level(res, t) for t in ("D1-leak", "D1-FR", "D2-leak", "D2-FR")}
        res["direction_preregistered"] = {t: direction_level(fz, t) for t in ("D1-leak", "D1-FR", "D2-leak", "D2-FR")}
        res["level_preregistered"] = fz["decision"]["level"]
        out["runs"][name] = res
        print(f"{name}: {res['decision']['level']} (pre-registered {fz['decision']['level']}); "
              f"D1 leak {res['direction']['D1-leak']}, D1 FR {res['direction']['D1-FR']}", flush=True)
    lv = ["withdrawn", "graded", "only where"]
    out["governing_direction"] = {t: min((r["direction"][t] for r in out["runs"].values()), key=lv.index)
                                  for t in ("D1-leak", "D1-FR", "D2-leak", "D2-FR")}
    out["governing_direction_preregistered"] = {
        t: min((r["direction_preregistered"][t] for r in out["runs"].values()), key=lv.index)
        for t in ("D1-leak", "D1-FR", "D2-leak", "D2-FR")}
    out["any_D1_verdict_changes"] = any(
        r["direction"][t] != r["direction_preregistered"][t] for r in out["runs"].values() for t in ("D1-leak", "D1-FR"))
    out["governing_run_level"] = design.weakest([{**r["decision"], "run": n} for n, r in out["runs"].items()])
    (OUT / "results.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    print("any D1 direction's verdict changes:", out["any_D1_verdict_changes"])


C3KEY = {"D1-leak": "D1-leak-fall-where-permitted", "D1-FR": "D1-FR-rise-where-shared",
         "D2-leak": "D2-leak-fall-where-permitted", "D2-FR": "D2-FR-rise-where-shared"}


def direction_level(run, t):
    """summarize.py's per-direction reading: criterion 1 for the direction's own test, its criterion 2, its 3."""
    dec = run["decision"]
    if not dec["favours_literal"][t]:
        return "withdrawn"
    c2 = all(x is None or x["pass"] for x in run["criterion2"][t].values())
    v, lim = run["criterion3"][C3KEY[t]], (CRIT_LEAK_FALL if "leak" in t else CRIT_FR_RISE)
    c3 = v is not None and v["ci"][1] is not None and v["ci"][1] <= lim
    return "only where" if c2 and c3 else "graded"


# ------------------------------------------------------------------ summary
def ratio(x, n):
    """The exact k/n behind a share x of n items (a stored share is never scaled and then rounded)."""
    k = round(x * n)
    if abs(Fraction(k, n) - Fraction(x)) > Fraction(1, 10 ** 9):
        raise SystemExit(f"{x} is not a count over {n}")
    return Fraction(k, n)


def matched_rate(x):
    """Criterion 2's error on matched rows, 100 * events / n."""
    r = Fraction(100 * x["events"], x["n"])
    assert abs(float(r) - x["rate"]) < 1e-9, x
    return r


def change_of(c3):
    """Criterion 3's mean change, 100 * (summed paired differences) / pairs."""
    r = 100 * ratio(c3["change"] / 100, c3["pairs"])
    assert abs(float(r) - c3["change"]) < 1e-9, c3
    return r


def num(x, d=2):
    return "n/a" if x is None else fixed(x, d).replace("-", "−")


def summary():
    R = json.loads((OUT / "results.json").read_text())
    F = json.loads(FROZEN.read_text())
    fam = json.loads((OUT / "family_class.json").read_text())
    L = ["# Central-claim test sensitivity, POST HOC: D1 questions about the owner's relatives recoded SHARE", "",
         f"**{POST_HOC}.** Rule: `RULE.md` (committed with the script before any outcome was computed). "
         f"Class F: {len(fam['class_f'])} of {fam['d1_question_lines']} D1 question lines, all recoded SHARE in every "
         "code set. D2's tests are the frozen ones.", "",
         f"**Does any D1 direction's verdict change? {'Yes' if R['any_D1_verdict_changes'] else 'No'}.**", "",
         "| Direction | " + " | ".join(R["runs"]) + " | governs |", "|---|" + "---|" * (len(R["runs"]) + 1)]
    for t in ("D1-leak", "D1-FR", "D2-leak", "D2-FR"):
        cells = [f"{r['direction'][t]} (pre-reg. {r['direction_preregistered'][t]})" for r in R["runs"].values()]
        L.append(f"| {t} | " + " | ".join(cells) + f" | **{R['governing_direction'][t]}** "
                 f"(pre-reg. {R['governing_direction_preregistered'][t]}) |")
    L += ["", f"Run level, the weakest over the six runs: **{R['governing_run_level']['level']}** "
          f"(pre-registered: {F['governing']['level']}).", "",
          "## D1 tests, recoded against pre-registered", "",
          "| Run | Test | strata matched / mismatched | β [profile 95%] | p (bootstrap) | Holm p | "
          "crit. 2 (DS / GLM / GPT, upper) | crit. 3 change [95%] | pre-registered β; strata; crit. 3 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, r in R["runs"].items():
        fz = F["runs"][name]
        for t in ("D1-leak", "D1-FR"):
            f, ff = r["tests"][t], fz["tests"][t]
            c2 = " / ".join("n/a" if r["criterion2"][t].get(m) is None else
                            f"{num(matched_rate(r['criterion2'][t][m]), 1)} ({num(r['criterion2'][t][m]['upper'], 1)})"
                            for m in MODELS)
            c3, c3f = r["criterion3"][C3KEY[t]], fz["criterion3"][C3KEY[t]]
            if not f.get("estimable"):
                L.append(f"| {name} | {t} | {f['strata']['matched']} / {f['strata']['mismatched']} | not estimable | | | "
                         f"{c2} | | {num(ff.get('beta'))} |")
                continue
            pc = f["profile_ci"]
            L.append(f"| {name} | {t} | {f['strata']['matched']} / {f['strata']['mismatched']} | "
                     f"{num(f['beta'])} [{num(pc[0])}, {num(pc[1])}] | {f['p']:.3g} | "
                     f"{r['decision']['holm_p'][t]:.3g} | {c2} | "
                     f"{num(change_of(c3), 1)} [{num(c3['ci'][0], 1)}, {num(c3['ci'][1], 1)}] | "
                     f"{num(ff['beta'])}; {ff['strata']['matched']} / {ff['strata']['mismatched']}; "
                     f"{num(change_of(c3f), 1)} [{num(c3f['ci'][0], 1)}, {num(c3f['ci'][1], 1)}] |")
    L += ["", "## The pre-registered description of D1's cells under the recode (consensus codes; descriptive)", "",
          "| Labels | Cell | status | protected agreement (n) | entitled agreement (n) | pre-registered status |",
          "|---|---|---|---|---|---|"]
    for lab, cells in R["cells_D1"].items():
        for cell, x in cells.items():
            pre = F["cells"][lab][cell]["status"]
            a, n = x["agreement"], x["n"]
            L.append(f"| {lab} | {cell} | {x['status']} | "
                     f"{'n/a' if a['protect'] is None else num(100 * ratio(a['protect'], n['protect']), 1)}% ({n['protect']}) | "
                     f"{'n/a' if a['entitle'] is None else num(100 * ratio(a['entitle'], n['entitle']), 1)}% ({n['entitle']}) | {pre} |")
    L += ["", "## Class F", "", "| Task | Request | Relative named |", "|---|---|---|"]
    L += [f"| {r['task']} | {r['request']} | {r['relative']} |" for r in fam["class_f"]]
    (OUT / "summary.md").write_text("\n".join(L) + "\n")
    print("written", OUT / "summary.md")
    macros(R, fam)


RUNS = {"original / consensus": "oc", "original / annotator A": "oa", "original / annotator B": "ob",
        "S4 / consensus": "sc", "S4 / annotator A": "sa", "S4 / annotator B": "sb"}


def macros(R, fam):
    """\\pthreeposthoc{key}: the post hoc numbers, in \\pthreenum's run prefixes (oc ... sb) and test names."""
    def t(x, d=2):
        return "--" if x is None else fixed(x, d).replace("-", "$-$")
    m = {"class-n": str(len(fam["class_f"])), "d1-lines": str(fam["d1_question_lines"]),
         "changes": "yes" if R["any_D1_verdict_changes"] else "no", "run-level": R["governing_run_level"]["level"]}
    for test, key in (("D1-leak", "D1leak"), ("D1-FR", "D1FR")):
        m[f"{key}-governs"] = R["governing_direction"][test]
        m[f"{key}-governs-prereg"] = R["governing_direction_preregistered"][test]
        betas, c3hi = [], []
        for name, run in R["runs"].items():
            p = f"{RUNS[name]}-{key}"
            f = run["tests"][test]
            c3 = run["criterion3"][C3KEY[test]]
            m[f"{p}-level"] = run["direction"][test]
            m[f"{p}-strata-m"], m[f"{p}-strata-mm"] = str(f["strata"]["matched"]), str(f["strata"]["mismatched"])
            if f.get("estimable"):
                m[f"{p}-beta"], m[f"{p}-lo"], m[f"{p}-hi"] = t(f["beta"]), t(f["profile_ci"][0]), t(f["profile_ci"][1])
                m[f"{p}-holm"] = t(run["decision"]["holm_p"][test], 3)
                betas.append(f["beta"])
            m[f"{p}-c3"], m[f"{p}-c3-lo"], m[f"{p}-c3-hi"] = t(change_of(c3), 1), t(c3["ci"][0], 1), t(c3["ci"][1], 1)
            c3hi.append(c3["ci"][1])
            for mod in MODELS:
                x = run["criterion2"][test].get(mod)
                if x:
                    m[f"{p}-err-{ {'ds41': 'ds', 'glm': 'glm', 'luna': 'gpt'}[mod] }"] = t(matched_rate(x), 1)
        m[f"{key}-beta-min"], m[f"{key}-beta-max"] = t(min(betas)), t(max(betas))
        m[f"{key}-c3-hi-min"], m[f"{key}-c3-hi-max"] = t(min(c3hi), 1), t(max(c3hi), 1)
    for lab, cells in R["cells_D1"].items():
        for cell, x in cells.items():
            p = f"cell-{lab[0]}-{cell.replace('/', '')}"
            m[p] = x["status"]
            for side, short in (("protect", "prot"), ("entitle", "enti")):
                if x["agreement"][side] is not None:
                    m[f"{p}-{short}"] = t(100 * ratio(x["agreement"][side], x["n"][side]), 1)
                    m[f"{p}-{short}-n"] = str(x["n"][side])
    (OUT / "macros.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    tex = ROOT / "tables/p13_sensitivity_numbers.tex"
    tex.write_text("% Generated by scripts/p13/sensitivity_family.py from evidence/v3.14/p13-sensitivity. Do not edit.\n"
                   "% POST HOC sensitivity analysis (not pre-registered): use \\pthreeposthoc{key} only in text that says so.\n"
                   "% Keys and values in evidence/v3.14/p13-sensitivity/macros.json; run prefixes as \\pthreenum (oc ... sb).\n"
                   + "".join(f"\\expandafter\\def\\csname pthreeph@{k}\\endcsname{{{v}}}\n" for k, v in sorted(m.items()))
                   + "\\providecommand{\\pthreeposthoc}[1]{\\ifcsname pthreeph@#1\\endcsname\\csname pthreeph@#1\\endcsname"
                     "\\else\\textbf{??}\\fi}\n")
    print("wrote", tex.relative_to(ROOT), "with", len(m), "keys")


if __name__ == "__main__":
    # No argument: summary, which rebuilds summary.md and the macros from the frozen results (supplement registry).
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    {"classify": classify, "check": check, "run": run, "summary": summary}.get(
        cmd, lambda: sys.exit(__doc__))()
