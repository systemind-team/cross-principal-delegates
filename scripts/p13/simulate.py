#!/usr/bin/env python3
"""Simulation check of the central-claim test before any code meets an outcome.

The design is PAIR I's: three models x R0-R3 x D0, D1, D2 x the 600 tasks, the relationship labels, the
tasks' source notes, and literal verdicts from the deterministic clause map (rule_coder.py) as a stand-in
for the annotators' codes. So that D2's leak test is estimable in the stand-in, 40 work_public questions
drawn with a fixed seed are flagged public (D2 then permits them to R0 and R3). No outcome of any run is
read: every y below is simulated.

Data-generating model, per test (policy p, outcome):
  logit P(y=1) = a[model, requester] + g_p * [rung = p] + d * mm + b * mm * [rung = p] + s * u_task
Scenarios: b = 0 (size of the likelihood-ratio test), b = 1 and b = 2 (power, bias, profile-interval
coverage on the first 100 replicates).
Output: evidence/v3.14/p13-simulation/results.json
"""
import collections
import json
import pathlib
import random
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p13"))
sys.path.insert(0, str(ROOT / "scripts" / "coding"))
import design  # noqa: E402
import rule_coder  # noqa: E402

OUT = ROOT / "evidence/v3.14/p13-simulation"
LABELS = ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json"
DS = ROOT / "evidence/v3.14/pair-dataset"
TESTS = (("D1", "leak"), ("D1", "FR"), ("D2", "leak"), ("D2", "FR"))
PARAMS = {  # (cell mean logit at D0, policy shift g_p, d, s)
    "leak": (0.3, -2.5, 0.5, 1.5),
    "FR": (-3.0, 0.0, 0.3, 1.2),
}


def base_rows():
    lab = json.loads(LABELS.read_text())
    QL = {f"PAIR-Q{q['id']}": q for q in lab["questions"]}
    AL = {f"PAIR-A{a['id']}": a for a in lab["actions"]}
    qs = json.loads((DS / "questions.json").read_text())
    note = {}
    for q in qs["questions"]:
        src = (q.get("source_notes") or q.get("source_todos") or ["?"])[0]
        note[f"PAIR-Q{q['id']}"] = src
    for a in qs["actions"]:
        note[f"PAIR-A{a['id']}"] = a.get("target_item") or f"create:{a.get('target_folder')}"
    qcat, acat, folder = rule_coder.load()
    rng = random.Random(20261004)
    wp = sorted(t for t, c in qcat.items() if c == "work_public")
    public = set(rng.sample(wp, 40))
    rows = []
    for m in design.MODELS:
        for r in ("R0", "R1", "R2", "R3"):
            for rung in ("D0", "D1", "D2"):
                for t in list(QL) + list(AL):
                    kind = "question" if t in QL else "action"
                    lab_share = QL[t][r] == "L" if kind == "question" else AL[t][r] == "execute"
                    v = {}
                    for p in ("D1", "D2"):
                        if p == "D1" and kind == "action":
                            v[p] = None
                            continue
                        dec, _ = rule_coder.code(p, r, t, qcat, acat, folder, public)
                        v[p] = "permit" if dec in ("SHARE", "PERFORM") else "withhold"
                    rows.append({"model": m, "requester": r, "rung": rung, "task": t, "kind": kind,
                                 "label": "entitle" if lab_share else "protect", "v": v, "note": note[t]})
    return rows


def simulate(rows, policy, outcome, b, rng):
    sub = design.test_rows([{**r, "verdict": r["v"][policy], "y": 0} for r in rows], policy, outcome)
    mean, g, d, s = PARAMS[outcome]
    cells = sorted({(r["model"], r["requester"]) for r in sub})
    a = {c: mean + rng.normal(0, 0.5) for c in cells}
    u = {t: rng.normal() for t in sorted({r["task"] for r in sub})}
    for r in sub:
        on = r["rung"] == policy
        eta = a[(r["model"], r["requester"])] + g * on + d * r["mm"] + b * r["mm"] * on + s * u[r["task"]]
        r["y"] = int(rng.random() < 1 / (1 + np.exp(-eta)))
    return sub


def main():
    reps = {0.0: int(sys.argv[1]) if len(sys.argv) > 1 else 300, 1.0: int(sys.argv[2]) if len(sys.argv) > 2 else 150,
            2.0: int(sys.argv[2]) if len(sys.argv) > 2 else 150}
    ci_reps = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    rows = base_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    res = {"design": {}, "scenarios": {}}
    for policy, outcome in TESTS:
        sub = design.test_rows([{**r, "verdict": r["v"][policy], "y": 0} for r in rows], policy, outcome)
        res["design"][f"{policy}-{outcome}"] = {"rows": len(sub), **design.strata(sub, policy)}
    t0 = time.time()
    for b, R in reps.items():
        for policy, outcome in TESTS:
            name = f"{policy}-{outcome}"
            ps, betas, cover, ncov, nest = [], [], 0, 0, 0
            for i in range(R):
                sub = simulate(rows, policy, outcome, b, rng)
                want_ci = b > 0 and i < ci_reps
                f = design.fit_test(sub, policy, ci=want_ci)
                if not f["estimable"]:
                    continue
                nest += 1
                ps.append(f["p"])
                betas.append(f["beta"])
                if want_ci:
                    ncov += 1
                    lo, hi = f["profile_ci"]
                    cover += lo <= b <= hi
            ps = np.array(ps)
            res["scenarios"][f"b={b}/{name}"] = {
                "replicates": R, "estimable": nest,
                "reject_at_0.05": float(np.mean(ps < 0.05)) if nest else None,
                "mean_beta": float(np.mean(betas)) if nest else None,
                "sd_beta": float(np.std(betas, ddof=1)) if nest > 1 else None,
                "profile_ci_coverage": (cover / ncov) if ncov else None, "ci_replicates": ncov}
            print(f"b={b} {name}: {res['scenarios'][f'b={b}/{name}']}  ({time.time() - t0:.0f}s)", flush=True)
    res["params"] = {k: dict(zip(("cell_mean_logit_D0", "policy_shift", "delta", "sigma"), v))
                     for k, v in PARAMS.items()}
    res["seeds"] = {"public_flag_draw": 20261004, "simulation": 7}
    (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    print("wrote", (OUT / "results.json").relative_to(ROOT))


if __name__ == "__main__":
    main()
