#!/usr/bin/env python3
"""Central-claim test, secondary analyses, as specified in evidence/v3.14/coding-p1-3/PREREGISTRATION.md section 6a (committed
in 9b7676d before this file existed). They describe and never decide the primary claim.

  S-a  each primary test by requester (original labels, consensus codes; cell effects alpha[model, rung])
  S-b  the four primary tests under the category labels
  S-c  D2 action safety: protected actions changed, mismatch = the D2 verdict is PERFORM
  S-d  PAIR II ladder grid, D0 and D2, original relationship labels, mismatch from the CAT codes
  S-e  the identity comparison's arm without the header (PR), mismatch from the PRN codes; no D0, so
       logit P(y = 1) = alpha[requester] + beta * mm + u_task

Each p is a parametric-bootstrap LRT (B = 199, seed 0) with the profile interval for beta beside it;
Benjamini-Hochberg (q = 0.05) over the estimable tests.

Inputs: as analysis.py, plus evidence/v3.14/single-grid-tasks/tasks.jsonl.xz (stateChanged),
evidence/v3.14/ladder-per-task/ladder.jsonl.xz, evidence/v3.14/identity-per-task/identity.jsonl.xz and
evidence/v3.14/total-disclosure/pair2_classes_{ladder,identity}.jsonl.xz.
Output: evidence/v3.14/p13-results/secondary.json
"""
import collections
import json
import lzma
import os
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p13"))
import analysis  # noqa: E402
import design  # noqa: E402
import glmm  # noqa: E402

EV = ROOT / "evidence/v3.14"
PB, SEED, Q = 199, 0, 0.05
REQS = ("R0", "R1", "R2", "R3")
LEAK_CLASSES = {"decision", "refusal-channel"}


# ---------------------------------------------------------------- fitting

def counts(rows, rungs):
    """Events / rows by rung and mismatch status, for the write-up."""
    out = {}
    for u in rungs:
        for mm in (0, 1):
            sub = [r for r in rows if r["rung"] == u and r["mm"] == mm]
            out[f"{u}/{'mismatched' if mm else 'matched'}"] = {"rows": len(sub), "events": sum(r["y"] for r in sub)}
    return out


def design_noanchor(rows):
    """S-e: alpha[requester] + beta * mm; requester cells without events or non-events are dropped."""
    cells = collections.defaultdict(list)
    for r in rows:
        cells[r["requester"]].append(r["y"])
    keep = sorted(c for c, ys in cells.items() if 0 < sum(ys) < len(ys))
    dropped = sorted(c for c in cells if c not in keep)
    col = {c: k for k, c in enumerate(keep)}
    use = [r for r in rows if r["requester"] in col]
    X = np.zeros((len(use), len(keep) + 1))
    for j, r in enumerate(use):
        X[j, col[r["requester"]]] = 1
        X[j, -1] = r["mm"]
    d = glmm.Data(X, [r["y"] for r in use], [r["task"] for r in use], [f"cell:{c}" for c in keep] + ["mismatch"])
    return d, dropped


def fit_noanchor(rows, pb, seed):
    st = design.strata(rows, "PR")
    res = {"strata": {"matched": st.get(0, 0), "mismatched": st.get(1, 0)}, "n_rows": len(rows)}
    if st.get(0, 0) < design.MIN_CELLS or st.get(1, 0) < design.MIN_CELLS:
        return {**res, "estimable": False, "reason": f"stratum under {design.MIN_CELLS} item-requester cells"}
    d, dropped = design_noanchor(rows)
    res["dropped_cells"] = dropped
    k = d.X.shape[1] - 1
    if d.X[:, k].sum() in (0, len(d.y)):
        return {**res, "estimable": False, "reason": "mismatch not identified after dropping cells"}
    t = glmm.lrt(d, k, glmm.fit(d))
    f1 = t["full"]
    diag = {}
    p, _ = design.pb_lrt(d, k, f1, pb, seed, diag)
    lo, hi = glmm.profile_ci(d, k, f1)
    return {**res, "estimable": True, "beta": float(f1["theta"][k]), "sigma": f1["sigma"], "loglik": f1["loglik"],
            "converged": f1["converged"] and t["null"]["converged"], "full_refitted_from_null": t["refit"],
            "lrt_stat": t["stat"], "p_chi2": t["p"], "p": p, "p_method": f"parametric bootstrap, B = {pb}",
            "pb_diagnostics": diag, "profile_ci": [lo, hi], "n_used": int(len(d.y)), "n_tasks": int(d.G)}


def work(job):
    name, rows, policy = job
    if policy == "PR":
        out = fit_noanchor(rows, PB, SEED)
        out["counts"] = counts(rows, ("PR",))
    else:
        out = design.fit_test(rows, policy, pb=PB, seed=SEED)
        out["counts"] = counts(rows, ("D0", policy))
    return name, out


def bh(ps, q=Q):
    """Benjamini-Hochberg adjusted p (step-up) for a dict name -> p; significant where adjusted p <= q."""
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, adj, run = len(items), {}, 1.0
    for i in range(m - 1, -1, -1):
        name, p = items[i]
        run = min(run, p * m / (i + 1))
        adj[name] = run
    return adj


# ---------------------------------------------------------------- rows

def pair1_rows(outcomes, labels, verdict, note):
    return analysis.build_rows(outcomes, labels, verdict, note)


def s_a(rows):
    jobs = []
    for policy in ("D1", "D2"):
        for outcome in ("leak", "FR"):
            sub = design.test_rows([{**r, "verdict": r["verdicts"][policy]} for r in rows], policy, outcome)
            for q in REQS:
                part = [r for r in sub if r["requester"] == q]
                if part:
                    jobs.append((f"S-a {policy}-{outcome} {q}", part, policy))
    return jobs


def s_b(rows):
    jobs = []
    for policy in ("D1", "D2"):
        for outcome in ("leak", "FR"):
            sub = design.test_rows([{**r, "verdict": r["verdicts"][policy]} for r in rows], policy, outcome)
            jobs.append((f"S-b {policy}-{outcome} (category labels)", sub, policy))
    return jobs


def s_c(outcomes, labels, verdict):
    state = {}
    with lzma.open(EV / "single-grid-tasks/tasks.jsonl.xz", "rt") as f:
        for line in f:
            o = json.loads(line)
            if o["family"] in design.MODELS and o["policy"] in ("D0", "D2") and o["kind"] == "action":
                state[(o["cell"], o["taskId"])] = bool(o.get("stateChanged"))
    rows = []
    for o in outcomes:
        if (o["family"] not in design.MODELS or o["policy"] not in ("D0", "D2") or o["kind"] != "action"
                or not o["scored"]):
            continue
        t, q = o["task"], o["requester"]
        if labels[t][q] != "protect":
            continue
        v = verdict.get(("D2", q, t))
        if v is None:
            continue
        rows.append({"model": o["family"], "requester": q, "rung": o["policy"], "task": t,
                     "y": int(state[(o["cell"], t)]), "mm": int(v == "permit")})
    return [("S-c D2 action safety (unauthorized action)", rows, "D2")]


def pair2_verdicts(key, codes, packet):
    out = {}
    for code, k in key.items():
        if k["packet"] == packet and not k["planted"]:
            dec = codes[code]
            out[k["task"]] = None if dec is None else ("permit" if dec in analysis.SHARE else "withhold")
    return out


def pair2_row(t, q, lab, pe, status, cls, verdict):
    """One PAIR II row, or None. Leak rows: relationship-protected questions; FR rows: entitled tasks."""
    v = verdict.get(t)
    if v is None:
        return None
    if t.startswith("PAIR-Q") and lab == "protect":
        if cls is None:
            raise SystemExit(f"no leak class for {t} / {q}")
        return {"outcome": "leak", "y": int(cls in LEAK_CLASSES), "mm": int(v == "permit")}
    if lab == "entitle" and q != "R0":
        if t.startswith("PAIR-A") and status == "side_effect_before_failure":
            return None
        return {"outcome": "FR", "y": int(pe["actualDecision"] == "refuse"), "mm": int(v == "withhold")}
    return None


def s_d(labels, cat_verdict):
    recs = [json.loads(l) for l in lzma.open(EV / "ladder-per-task/ladder.jsonl.xz", "rt")]
    recs = [r for r in recs if "arm" in r]
    assert len(recs) == 1350
    ev = {}
    for r in recs:
        for t in r.get("tasks", []):
            if t["publicEvaluation"]:
                ev[(r["arm"], r["rung"], r["requester"], r["group"], t["task"])] = (t["publicEvaluation"], t["status"])
    tasks_of = {r["group"]: r["tasks_selected"] for r in recs}
    groups = sorted(tasks_of)
    assert len({t for g in groups for t in tasks_of[g]}) == 150, "a task in two groups"
    assert set(cat_verdict) == {t for g in groups for t in tasks_of[g]}, "CAT packet and ladder tasks differ"
    cls = {}
    for l in lzma.open(EV / "total-disclosure/pair2_classes_ladder.jsonl.xz", "rt"):
        o = json.loads(l)
        cls[(o["arm"], o["rung"], o["requester"], o["group"], o["task"])] = o["cls"]
    rows = {"leak": [], "FR": []}
    for b in ("DS", "GLM", "GROK"):
        for q in ("R1", "R2", "R3"):
            def items(u):
                return {(g, t) for g in groups for t in tasks_of[g] if (b, u, q, g, t) in ev}
            keep = items("D0") & items("D1") & items("D2")
            for g, t in sorted(keep):
                for u in ("D0", "D2"):
                    pe, status = ev[(b, u, q, g, t)]
                    row = pair2_row(t, q, labels[t][q], pe, status, cls.get((b, u, q, g, t)), cat_verdict)
                    if row:
                        rows[row["outcome"]].append({"model": b, "requester": q, "rung": u, "task": t,
                                                     "y": row["y"], "mm": row["mm"]})
    return [(f"S-d PAIR II ladder {o} (relationship labels, CAT codes)", rows[o], "D2") for o in ("leak", "FR")]


def s_e(labels, prn_verdict):
    recs = [json.loads(l) for l in lzma.open(EV / "identity-per-task/identity.jsonl.xz", "rt")]
    recs = [r for r in recs if "arm" in r]
    assert len(recs) == 400
    cls = {}
    for l in lzma.open(EV / "total-disclosure/pair2_classes_identity.jsonl.xz", "rt"):
        o = json.loads(l)
        cls[(o["arm"], o["requester"], o["group"], o["task"])] = o["cls"]
    rows = {"leak": [], "FR": []}
    seen = set()
    for r in recs:
        if r["arm"] != "PR":
            continue
        for t in r.get("tasks", []):
            pe = t["publicEvaluation"]
            if not pe:
                continue
            q, task = r["requester"], t["task"]
            assert (q, task) not in seen
            seen.add((q, task))
            row = pair2_row(task, q, labels[task][q], pe, t["status"], cls.get(("PR", q, r["group"], task)),
                            prn_verdict)
            if row:
                rows[row["outcome"]].append({"model": "PR", "requester": q, "rung": "PR", "task": task,
                                             "y": row["y"], "mm": row["mm"]})
    return [(f"S-e identity arm without header {o} (relationship labels, PRN codes)", rows[o], "PR")
            for o in ("leak", "FR")]


# ---------------------------------------------------------------- main

def main():
    C3 = analysis.C3
    key = json.loads((C3 / "key/key-P1-3.json").read_text())["lines"]
    A, B = analysis.read_answers("A"), analysis.read_answers("B")
    cons = analysis.code_sets(key, A, B)["consensus"]
    verdict = analysis.verdicts(key, cons)
    qs = json.loads((analysis.DS / "questions.json").read_text())
    note = {f"PAIR-Q{q['id']}": (q.get("source_notes") or q.get("source_todos") or ["?"])[0] for q in qs["questions"]}
    note.update({f"PAIR-A{a['id']}": a.get("target_item") or f"create:{a.get('target_folder')}" for a in qs["actions"]})
    outcomes = analysis.load_outcomes()
    labels = json.loads((analysis.LABELDIR / "original.json").read_text())["labels"]

    cat = {}
    for o in outcomes:
        assert cat.setdefault(o["task"], o["cat"]) == o["cat"], f"category label varies for {o['task']}"
    cat_labels = {t: {q: c for q in REQS} for t, c in cat.items()}

    rel_rows = pair1_rows(outcomes, labels, verdict, note)
    cat_rows = pair1_rows(outcomes, cat_labels, verdict, note)
    jobs = (s_a(rel_rows) + s_b(cat_rows) + s_c(outcomes, labels, verdict)
            + s_d(labels, pair2_verdicts(key, cons, "CAT")) + s_e(labels, pair2_verdicts(key, cons, "PRN")))
    print(f"{len(jobs)} tests", flush=True)
    results = {}
    with ProcessPoolExecutor(max_workers=int(os.environ.get("P13_WORKERS", "5"))) as ex:
        for name, out in ex.map(work, jobs):
            results[name] = out
            print(name, "estimable" if out.get("estimable") else "not estimable", flush=True)
    est = {k: v["p"] for k, v in results.items() if v.get("estimable")}
    adj = bh(est)
    for k, v in results.items():
        if k in adj:
            v["bh_adjusted_p"] = adj[k]
            v["significant_bh"] = adj[k] <= Q
    out = {"specification": "evidence/v3.14/coding-p1-3/PREREGISTRATION.md section 6a (commit 9b7676d)",
           "bootstrap": {"B": PB, "seed": SEED}, "bh_q": Q, "family_size": len(est), "tests": results}
    analysis.OUT.mkdir(parents=True, exist_ok=True)
    (analysis.OUT / "secondary.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    print("written", analysis.OUT / "secondary.json")


if __name__ == "__main__":
    main()
