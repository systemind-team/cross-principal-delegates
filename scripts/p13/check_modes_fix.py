#!/usr/bin/env python3
"""Check of the 2026-10-05 fix to glmm._modes (PREREGISTRATION section 8): the old and the new code fitted side by
side, (1) on the 24 primary fits (six runs x four tests) and (2) on 480 data sets simulated from section 7's design
(60 per test at beta = 0 and beta = 1, seed 99).

    git show 56f4bd7:scripts/p13/glmm.py > /tmp/glmm_old.py
    python3 scripts/p13/check_modes_fix.py /tmp/glmm_old.py

Output (2026-10-05): evidence/v3.14/p13-results/modes_fix_check.txt
"""
import importlib.util
import json
import sys

import numpy as np

sys.path.insert(0, "scripts/p13")
sys.path.insert(0, "scripts/coding")
import analysis  # noqa: E402
import design  # noqa: E402
import glmm as new  # noqa: E402
import simulate  # noqa: E402

spec = importlib.util.spec_from_file_location("glmm_old", sys.argv[1])
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def pair(d, used, k):
    res = []
    for mod in (old, new):
        dd = mod.Data(d.X, d.y, d.g, d.names)   # d.X, d.y and d.g are already in cluster order
        f1 = mod.fit(dd)
        f0 = mod.fit(dd, fixed={k: 0.0}, start=f1)
        res.append((f1["loglik"], f0["loglik"], f1["converged"] and f0["converged"], f1["theta"][k]))
    return res


print("(1) primary fits")
C3 = analysis.C3
key = json.loads((C3 / "key/key-P1-3.json").read_text())["lines"]
A, B = analysis.read_answers("A"), analysis.read_answers("B")
qs = json.loads((analysis.DS / "questions.json").read_text())
note = {f"PAIR-Q{q['id']}": (q.get("source_notes") or q.get("source_todos") or ["?"])[0] for q in qs["questions"]}
note.update({f"PAIR-A{a['id']}": a.get("target_item") or f"create:{a.get('target_folder')}" for a in qs["actions"]})
outcomes = analysis.load_outcomes()
for lab_name in ("original", "S4"):
    labels = json.loads((analysis.LABELDIR / f"{lab_name}.json").read_text())["labels"]
    for code_name, codes in analysis.code_sets(key, A, B).items():
        v = analysis.verdicts(key, codes)
        rows = analysis.build_rows(outcomes, labels, v, note)
        for policy in ("D1", "D2"):
            for outcome in ("leak", "FR"):
                sub = design.test_rows([{**r, "verdict": r["verdicts"][policy]} for r in rows], policy, outcome)
                d, _, used = design.design(sub, policy)
                (l1o, l0o, co, bo), (l1n, l0n, cn, bn) = pair(d, used, d.X.shape[1] - 1)
                print(f"{lab_name}/{code_name} {policy}-{outcome}: old LR {2 * (l1o - l0o):.4f} beta {bo:+.4f} conv {co} | "
                      f"new LR {2 * (l1n - l0n):.4f} beta {bn:+.4f} conv {cn} | |d loglik| {abs(l1o - l1n):.1e}", flush=True)

print("(2) simulated data sets")
rows = simulate.base_rows()
rng = np.random.default_rng(99)
for b in (0.0, 1.0):
    for policy, outcome in simulate.TESTS:
        diffs = n = oldfail = newfail = 0
        maxdiff = 0.0
        for i in range(60):
            sub = simulate.simulate(rows, policy, outcome, b, rng)
            d, _, used = design.design(sub, policy)
            (l1o, l0o, co, _), (l1n, l0n, cn, _) = pair(d, used, d.X.shape[1] - 1)
            n += 1
            dlr = abs(2 * (l1o - l0o) - 2 * (l1n - l0n))
            maxdiff = max(maxdiff, dlr)
            diffs += dlr > 1e-4
            oldfail += not co
            newfail += not cn
        print(f"b={b} {policy}-{outcome}: data sets {n}, LR differs (>1e-4) in {diffs}, max |dLR| {maxdiff:.2e}, "
              f"fits not converged: old {oldfail}, new {newfail}", flush=True)
