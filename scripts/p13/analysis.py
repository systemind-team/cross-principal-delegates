#!/usr/bin/env python3
"""The central-claim test, the pre-registered analysis (evidence/v3.14/coding-p1-3/PREREGISTRATION.md). Run only after both
annotators have returned their answers; the commit that adds this file predates the codes.

Inputs
  evidence/v3.14/coding-p1-3/key/key-P1-3.json          hidden key (code -> packet, requester, task)
  evidence/v3.14/coding-p1-3/answers/{A,B}/*.csv         the two annotators' answers (copied byte for byte)
  evidence/v3.14/coding-p1-3/rule_codes.json             deterministic clause map (third check)
  evidence/v3.14/labels/<variant>.json                   label sets: "original" and "S4"
  evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz   total-leak per-task outcomes for every PAIR I cell
  evidence/v3.14/pair-dataset/questions.json             source note of each task (bootstrap cluster)
Output
  evidence/v3.14/p13-results/results.json and summary.md
"""
import collections
import csv
import json
import lzma
import os
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p13"))
import design  # noqa: E402

C3 = ROOT / "evidence/v3.14/coding-p1-3"
LABELDIR = ROOT / "evidence/v3.14/labels"
OUTCOMES = ROOT / "evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz"
DS = ROOT / "evidence/v3.14/pair-dataset"
OUT = ROOT / "evidence/v3.14/p13-results"
B_PRIMARY, B_OTHER, B_KAPPA = 1000, 300, 2000
PB_PRIMARY, PB_OTHER = 999, 499      # parametric-bootstrap replicates for the likelihood-ratio p
SHARE = {"SHARE", "PERFORM"}
WITHHOLD = {"WITHHOLD", "DECLINE"}


def read_answers(ann):
    out = {}
    for f in sorted((C3 / "answers" / ann).glob("*.csv")):
        for row in csv.DictReader(open(f, newline="")):
            code, dec = row["code"].strip(), (row.get("decision") or "").strip().upper()
            if code in out:
                raise SystemExit(f"annotator {ann}: code {code} answered twice")
            out[code] = dec
    return out


def kappa(pairs):
    """Cohen's kappa for a list of (a, b) binary codes (1 = permit)."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def agreement(key, A, B, rule):
    """Per packet (and D2 per requester): 2x2 table, raw agreement, prevalence, kappa with an item
    bootstrap interval; planted accuracy per annotator; agreement of each annotator with the clause map."""
    groups = collections.defaultdict(list)
    planted = collections.defaultdict(lambda: {"A": [0, 0], "B": [0, 0]})
    for code, k in key.items():
        a, b = A.get(code), B.get(code)
        if a is None or b is None or a not in SHARE | WITHHOLD or b not in SHARE | WITHHOLD:
            raise SystemExit(f"missing or invalid answer for {code}: {a!r} / {b!r}")
        if k["planted"]:
            for ann, v in (("A", a), ("B", b)):
                planted[k["packet"]][ann][0] += v == k["answer"]
                planted[k["packet"]][ann][1] += 1
            continue
        pair = (int(a in SHARE), int(b in SHARE))
        groups[k["packet"]].append((code, pair))
        if k["packet"].startswith("D2"):
            groups["D2"].append((code, pair))
    rng = np.random.default_rng(0)
    out = {}
    for g, items in sorted(groups.items()):
        pairs = [p for _, p in items]
        tab = collections.Counter(pairs)
        boots = []
        for _ in range(B_KAPPA):
            s = [pairs[i] for i in rng.integers(0, len(pairs), len(pairs))]
            k_ = kappa(s)
            if k_ is not None:
                boots.append(k_)
        boots.sort()
        rule_agree = {ann: sum(int(rule[c]["decision"] in SHARE) == p[i] for c, p in items) / len(items)
                      for i, ann in enumerate(("A", "B"))}
        out[g] = {"n": len(pairs), "table": {f"A={a},B={b}": tab[(a, b)] for a in (1, 0) for b in (1, 0)},
                  "raw_agreement": sum(a == b for a, b in pairs) / len(pairs),
                  "prevalence_permit": {"A": sum(a for a, _ in pairs) / len(pairs), "B": sum(b for _, b in pairs) / len(pairs)},
                  "kappa": kappa(pairs),
                  "kappa_ci": [boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]] if boots else None,
                  "contested": sum(a != b for a, b in pairs), "agreement_with_rule": rule_agree}
    return out, {k: {ann: {"correct": v[ann][0], "n": v[ann][1]} for ann in ("A", "B")} for k, v in planted.items()}


def verdicts(key, codes):
    """(policy, requester, task) -> permit / withhold / None (contested). D1 is requester-independent."""
    v = {}
    for code, k in key.items():
        if k["planted"] or k["packet"] not in ("D1",) and not k["packet"].startswith("D2"):
            continue
        dec = codes[code]
        val = None if dec is None else ("permit" if dec in SHARE else "withhold")
        if k["packet"] == "D1":
            for r in ("R0", "R1", "R2", "R3"):
                v[("D1", r, k["task"])] = val
        else:
            v[("D2", k["requester"], k["task"])] = val
    return v


def code_sets(key, A, B):
    cons = {c: (A[c] if (A[c] in SHARE) == (B[c] in SHARE) else None) for c in key}
    return {"consensus": cons, "annotator A": dict(A), "annotator B": dict(B)}


def load_outcomes():
    with lzma.open(OUTCOMES, "rt") as f:
        return [json.loads(l) for l in f]


def build_rows(outcomes, labels, verdict, note):
    """One row per scored task in a same-model PAIR I cell at D0, D1 or D2."""
    rows = []
    for o in outcomes:
        if o["family"] not in design.MODELS or o["policy"] not in ("D0", "D1", "D2") or not o["scored"]:
            continue
        t, r = o["task"], o["requester"]
        lab = labels[t][r]
        kind = "question" if t.startswith("PAIR-Q") else "action"
        if kind == "question" and lab == "protect":
            y = o["total_disclosure"]
        elif lab == "entitle":
            y = o["decision"] == "refuse"
        else:
            continue
        if y is None:
            continue
        base = {"model": o["family"], "requester": r, "rung": o["policy"], "task": t, "kind": kind,
                "label": lab, "y": int(bool(y)), "note": note[t]}
        rows.append({**base, "verdicts": {p: verdict.get((p, r, t)) for p in ("D1", "D2")}})
    return rows


def run_test(sub, policy, outcome, B, seed, pb):
    """One of the four tests of one run, on its rows `sub` (design.test_rows): the fit, the note-bootstrap
    interval, criterion 2 and criterion 3's change."""
    f = design.fit_test(sub, policy, pb=pb, seed=seed)
    if f.get("estimable"):
        d, _, used = design.design(sub, policy)

        def beta_stat(sample, policy=policy):
            dd, _, _ = design.design(sample, policy)
            if dd.X[:, -1].sum() == 0:
                return None
            return float(design.glmm.fit(dd)["theta"][-1])
        f["note_bootstrap_ci"] = design.cluster_boot(used, beta_stat, B, seed)
    crit2 = design.matched_error(sub, policy, B, seed)
    if outcome == "leak":
        crit3 = (f"{policy}-leak-fall-where-permitted", design.paired_change(sub, policy, 1, +1, B, seed),
                 design.CRIT_LEAK_FALL)
    else:
        crit3 = (f"{policy}-FR-rise-where-shared", design.paired_change(sub, policy, 0, -1, B, seed),
                 design.CRIT_FR_RISE)
    return f, crit2, crit3


def test_subsets(rows):
    """The rows of each of the four tests."""
    return [(policy, outcome, design.test_rows([{**r, "verdict": r["verdicts"][policy]} for r in rows], policy, outcome))
            for policy in ("D1", "D2") for outcome in ("leak", "FR")]


def assemble(parts):
    """parts: [(policy, outcome, (f, crit2, crit3))] for the four tests of one run -> the run's result."""
    tests, crit2, crit3 = {}, {}, {}
    for policy, outcome, (f, c2, (k3, v3, lim)) in parts:
        name = f"{policy}-{outcome}"
        tests[name], crit2[name], crit3[k3] = f, c2, (v3, lim)
    dec = design.decide(tests, crit2, crit3)
    return {"tests": tests, "criterion2": crit2, "criterion3": {k: v[0] for k, v in crit3.items()}, "decision": dec}


def run(rows, B, seed, pb):
    return assemble([(policy, outcome, run_test(sub, policy, outcome, B, seed, pb))
                     for policy, outcome, sub in test_subsets(rows)])


def describe_cells(verdict, labels):
    """The pre-registered description of a requester's cell: matched if the coded verdict agrees with the
    labels on at least 90% of protected and of entitled tasks, mismatched if either is below 70%."""
    out = {}
    for p in ("D1", "D2"):
        for r in ("R0", "R1", "R2", "R3"):
            agree = {"protect": [0, 0], "entitle": [0, 0]}
            for (pp, rr, t), v in verdict.items():
                if pp != p or rr != r or v is None or (p == "D1" and not t.startswith("PAIR-Q")):
                    continue
                lab = labels[t][r]
                if lab is None:       # a cell the label set removes (S4); build_rows skips it too
                    continue
                agree[lab][1] += 1
                agree[lab][0] += (v == "permit") == (lab == "entitle")
            fr = {k: (a / n if n else None) for k, (a, n) in agree.items()}
            vals = [x for x in fr.values() if x is not None]
            status = ("matched" if vals and all(x >= 0.9 for x in vals) else
                      "mismatched" if any(x < 0.7 for x in vals) else "partial")
            out[f"{p}/{r}"] = {"agreement": fr, "n": {k: v[1] for k, v in agree.items()}, "status": status}
    return out


def _test_job(job):
    run_name, policy, outcome, sub, B, pb = job
    return run_test(sub, policy, outcome, B, 0, pb)


def main():
    key = json.loads((C3 / "key/key-P1-3.json").read_text())["lines"]
    A, B = read_answers("A"), read_answers("B")
    rule = json.loads((C3 / "rule_codes.json").read_text())["codes"]
    agree, planted = agreement(key, A, B, rule)
    qs = json.loads((DS / "questions.json").read_text())
    note = {f"PAIR-Q{q['id']}": (q.get("source_notes") or q.get("source_todos") or ["?"])[0] for q in qs["questions"]}
    note.update({f"PAIR-A{a['id']}": a.get("target_item") or f"create:{a.get('target_folder')}" for a in qs["actions"]})
    outcomes = load_outcomes()
    results = {"agreement": agree, "planted": planted, "runs": {}, "cells": {}}
    decisions = []
    jobs = []
    for lab_name in ("original", "S4"):
        labels = json.loads((LABELDIR / f"{lab_name}.json").read_text())["labels"]
        for code_name, codes in code_sets(key, A, B).items():
            v = verdicts(key, codes)
            rows = build_rows(outcomes, labels, v, note)
            primary = lab_name == "original" and code_name == "consensus"
            for policy, outcome, sub in test_subsets(rows):
                jobs.append((f"{lab_name} / {code_name}", policy, outcome, sub, B_PRIMARY if primary else B_OTHER,
                             PB_PRIMARY if primary else PB_OTHER))
            if code_name == "consensus":
                results["cells"][lab_name] = describe_cells(v, labels)
    # The 24 tests (six runs x four tests) are independent: each bootstrap draws from its own generator seeded 0,
    # so they run in parallel processes and the output is the same as running run() on each run in turn
    # (log in PREREGISTRATION section 8). The primary run's tests go first, as they take longest.
    order = sorted(range(len(jobs)), key=lambda i: (jobs[i][0] != "original / consensus", i))
    with ProcessPoolExecutor(max_workers=int(os.environ.get("P13_WORKERS", "8"))) as ex:
        done = dict(zip(order, ex.map(_test_job, [jobs[i] for i in order])))
    for i in range(0, len(jobs), 4):
        name = jobs[i][0]
        res = assemble([(jobs[j][1], jobs[j][2], done[j]) for j in range(i, i + 4)])
        results["runs"][name] = res
        decisions.append({**res["decision"], "run": name})
        print(f"{name}: {res['decision']['level']}", flush=True)
    results["governing"] = design.weakest(decisions)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=float) + "\n")
    print("governing result:", results["governing"]["level"], "from", results["governing"]["run"])


if __name__ == "__main__":
    main()
