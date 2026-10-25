#!/usr/bin/env python3
"""Kernel check: the pre-registered task and group samples. Seed 20261005. No model call.

PAIR I: 60 of the 600 tasks, stratified by (kind, category) over the frozen dataset
  (evidence/v3.14/pair-dataset/questions.json: 400 questions in 5 categories, 200 actions in 9).
  Allocation: each stratum gets floor(60 * size / 600); the remaining slots go to the strata with the largest
  remainders, ties broken by a seeded shuffle of the stratum names (random.Random(20261005)). Within a
  stratum the tasks are random.Random(f"20261005:{kind}:{category}").sample(sorted task ids, k).
PAIR II: 20 of the ladder grid's 50 groups (evidence/v3.13/multi-table3/MANIFEST.json "groups", the same
  1,350-config manifest as the VM's t3simple/MANIFEST.json), random.Random(20261005).sample(sorted(groups), 20).
  Each group has 3 tasks, so 60 tasks.

Writes evidence/v3.14/kernel-check/samples.json and prints a short summary.
"""
import json
import math
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED = 20261005
N_PAIR1 = 60
N_GROUPS = 20


def pair1_sample():
    ds = json.loads((ROOT / "evidence/v3.14/pair-dataset/questions.json").read_text())
    strata = {}
    for q in ds["questions"]:
        strata.setdefault(("qa", q["category"]), []).append(f"PAIR-Q{q['id']}")
    for a in ds["actions"]:
        strata.setdefault(("action", a["category"]), []).append(f"PAIR-A{a['id']}")
    total = sum(len(v) for v in strata.values())
    assert total == 600, total
    quota = {k: (N_PAIR1 * len(v)) / total for k, v in strata.items()}
    alloc = {k: math.floor(q) for k, q in quota.items()}
    order = sorted(strata)
    random.Random(SEED).shuffle(order)
    rank = {k: i for i, k in enumerate(order)}
    rest = N_PAIR1 - sum(alloc.values())
    for k in sorted(strata, key=lambda k: (-(quota[k] - alloc[k]), rank[k]))[:rest]:
        alloc[k] += 1
    assert sum(alloc.values()) == N_PAIR1
    tasks = []
    per = {}
    for (kind, cat) in sorted(strata):
        ids = sorted(strata[(kind, cat)], key=lambda t: int(t.split("Q" if kind == "qa" else "A")[-1]))
        pick = random.Random(f"{SEED}:{kind}:{cat}").sample(ids, alloc[(kind, cat)])
        per[f"{kind}/{cat}"] = {"size": len(ids), "drawn": len(pick), "tasks": pick}
        tasks.extend(pick)
    return tasks, per


def pair2_sample():
    man = json.loads((ROOT / "evidence/v3.13/multi-table3/MANIFEST.json").read_text())
    groups = man["groups"]
    assert len(groups) == 50
    pick = sorted(random.Random(SEED).sample(sorted(groups), N_GROUPS))
    return {g: groups[g] for g in pick}


def main():
    t1, per = pair1_sample()
    g2 = pair2_sample()
    t2 = [t for g in g2.values() for t in g]
    assert len(t1) == len(set(t1)) == 60 and len(t2) == len(set(t2)) == 60
    out = {
        "seed": SEED,
        "pair1": {"rule": "stratified by (kind, category), largest-remainder allocation, seeded ties", "tasks": t1,
                  "strata": per},
        "pair2": {"rule": "20 of 50 ladder groups, random.Random(seed).sample(sorted(groups), 20)",
                  "groups": g2, "tasks": t2},
    }
    dest = ROOT / "evidence/v3.14/kernel-check/samples.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print("PAIR I strata:", {k: (v["size"], v["drawn"]) for k, v in per.items()})
    print("PAIR I questions", sum(t.startswith("PAIR-Q") for t in t1), "actions", sum(t.startswith("PAIR-A") for t in t1))
    print("PAIR II groups", list(g2), "questions", sum(t.startswith("PAIR-Q") for t in t2),
          "actions", sum(t.startswith("PAIR-A") for t in t2))


if __name__ == "__main__":
    main()
