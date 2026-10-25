#!/usr/bin/env python3
"""PAIR I grok-4.6 supplement: fix the two task sets and the run plan before any grok request is sent.

Hard set. Every (task, requester) pair on which at least one of the three PAIR I models (DeepSeek, GLM,
GPT-5.6; standard harness, same model on both sides), graded by the relationship-v2 labels with recovery,
  - leaked a protected QA item under D1 or D2, counting total leak (a reply recorded as an answer that
    carries a gold fact, or a refusal whose literal reply carries one, per diag_scan.json), or
  - refused an entitled QA item or an authorized action under D2 (the paper's false refusal).
Random set. 100 of the 600 tasks in proportion to the three surfaces (34 Files QA Q1-Q200, 33 States QA
Q201-Q400, 33 actions A1-A200): each surface is ranked by SHA-256("pair1-grok-random/v1:<seed>:<taskId>")
and cut at its quota. Every random task runs for all four requesters.
Run plan. Each requester's cell runs the union of its hard pairs and the random tasks, under D0, D1 and D2.
Trial. 20 task-runs drawn from the run plan by SHA-256("pair1-grok-trial/v1:<seed>:<cell>:<taskId>"), to
price a task-run; the trial's outcomes are discarded and its tasks run again in the plan.

  python3 scripts/single_grid/grok/select_sets.py [--frozen DIR]

DIR holds the frozen tasks.jsonl and diag_scan.json (default evidence/v3.13/single-grid/). Writes
hard_set.jsonl, random_set.json and run_plan.json to evidence/v3.13/single-grid-grok/design/; a rerun
reproduces them byte for byte.
"""
import argparse, collections, hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (DESIGN_DIR, FROZEN_DIR, FROZEN_SHA256, MODELS, NEW, POLICIES, REQUESTERS, cell_id, check_frozen,
                    hard_reasons, load_jsonl, refusal_hits, surface, task_order)

SEED = 20261005
RANDOM_QUOTA = {"files_qa": 34, "states_qa": 33, "action": 33}
TRIAL_SIZE = 20
HARD_LABEL = "relationship"


def rank(salt, *parts):
    return hashlib.sha256(":".join((salt, str(SEED)) + parts).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", default=FROZEN_DIR)
    args = ap.parse_args()
    check_frozen(args.frozen)
    rows = [r for r in load_jsonl(os.path.join(args.frozen, "tasks.jsonl")) if r["family"] in MODELS]
    hits = refusal_hits(json.load(open(os.path.join(args.frozen, "diag_scan.json"))))
    tasks = sorted({r["taskId"] for r in rows}, key=task_order)
    by_surface = collections.Counter(surface(t) for t in tasks)
    assert by_surface == {"files_qa": 200, "states_qa": 200, "action": 200}, by_surface
    assert len(rows) == 3 * 7 * 4 * 600, len(rows)

    # hard set
    reasons = hard_reasons(rows, hits, HARD_LABEL)
    hard = sorted(reasons, key=lambda k: (k[1], task_order(k[0])))
    with open(os.path.join(DESIGN_DIR, "hard_set.jsonl"), "w") as f:
        for t, req in hard:
            f.write(json.dumps({"taskId": t, "requester": req, "surface": surface(t),
                                "reasons": sorted(reasons[(t, req)])}) + "\n")

    # random set
    chosen = []
    for s, quota in RANDOM_QUOTA.items():
        pool = sorted((t for t in tasks if surface(t) == s), key=lambda t: rank("pair1-grok-random/v1", t))
        chosen += pool[:quota]
    chosen.sort(key=task_order)
    label_counts = {}
    for req in REQUESTERS:
        rr = {r["taskId"]: r for r in rows if r["cell"] == cell_id("ds41", "D0", req) and r["taskId"] in set(chosen)}
        label_counts[req] = {lab: dict(collections.Counter(f"{rr[t]['kind']}:{rr[t][f]}" for t in chosen))
                             for lab, f in (("relationship", "relationshipExpectedBehavior"),
                                            ("category", "benchmarkExpectedBehavior"))}
    json.dump({"seed": SEED, "salt": "pair1-grok-random/v1", "quota": RANDOM_QUOTA, "tasks": chosen,
               "requesters": list(REQUESTERS), "labelCounts": label_counts},
              open(os.path.join(DESIGN_DIR, "random_set.json"), "w"), indent=1)

    # run plan and trial
    cells, runs = {}, []
    for req in REQUESTERS:
        hard_ids = {t for t, q in hard if q == req}
        ids = sorted(hard_ids | set(chosen), key=task_order)
        for pol in POLICIES:
            cid = cell_id(NEW, pol, req)
            cells[cid] = {"policy": f"{pol}_{req}", "requester": req, "n": len(ids),
                          "hard": len(hard_ids), "random": len(chosen), "overlap": len(hard_ids & set(chosen)),
                          "ids": ids}
            runs += [(cid, t) for t in ids]
    trial_runs = sorted(runs, key=lambda x: rank("pair1-grok-trial/v1", *x))[:TRIAL_SIZE]
    trial = collections.defaultdict(list)
    for cid, t in trial_runs:
        trial[cid].append(t)
    by_kind = collections.Counter("qa" if t.startswith("PAIR-Q") else "action" for _, t in runs)
    plan = {"seed": SEED, "frozenInputs": FROZEN_SHA256, "hardLabel": HARD_LABEL,
            "taskRuns": len(runs), "taskRunsByKind": dict(by_kind), "hardPairs": len(hard),
            "randomPairs": len(chosen) * len(REQUESTERS), "cells": cells,
            "trial": {"salt": "pair1-grok-trial/v1", "taskRuns": TRIAL_SIZE,
                      "cells": {c: sorted(v, key=task_order) for c, v in sorted(trial.items())}}}
    json.dump(plan, open(os.path.join(DESIGN_DIR, "run_plan.json"), "w"), indent=1)

    print(f"hard pairs {len(hard)}: " + ", ".join(f"{q} {sum(1 for _, x in hard if x == q)}" for q in REQUESTERS))
    kinds = collections.Counter(x.split(":")[2] for v in reasons.values() for x in v)
    print(f"  reasons (model-policy instances): {dict(sorted(kinds.items()))}")
    print(f"random tasks {len(chosen)} x {len(REQUESTERS)} requesters; overlap with hard per requester: "
          + ", ".join(f"{c['requester']} {c['overlap']}" for k, c in cells.items() if k.endswith('-d0-' + c['requester'].lower())))
    print(f"run plan: {len(runs)} task-runs over {len(cells)} cells {dict(by_kind)}; trial {TRIAL_SIZE} task-runs in {len(trial)} cells")


if __name__ == "__main__":
    main()
