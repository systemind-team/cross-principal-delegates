#!/usr/bin/env python3
"""Files QA versus States QA, per cell.
Q1-Q200 read notes (Files QA) and Q201-Q400 read todo state (States QA); every other table pools them.
Reads out/tasks.jsonl (or its frozen copy, evidence/v3.14/single-grid-tasks/) and out/cells.json. First re-derives the frozen QA numerators and denominators of
all 110 cells (strict and with-recovery) from the per-row rules and stops if any differ; then writes
out/pools.json: per cell and pool, with-recovery leak / false refusal / utility counts, Wilson intervals,
the States-minus-Files gap and a two-sided Fisher exact p-value for it."""
import json, lzma, os, re, sys, collections
from math import comb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats import wilson
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # paper repo root
OUT = os.path.join(ROOT, "evidence", "v3.13", "single-grid")
cells = {c["cell"]: c for c in json.load(open(os.path.join(OUT, "cells.json")))["cells"]}
rows = collections.defaultdict(list)
_src = os.path.join(OUT, "tasks.jsonl")   # absent from the repository: read the frozen, byte-identical merge
for line in (open(_src) if os.path.exists(_src) else
             lzma.open(os.path.join(ROOT, "evidence", "v3.14", "single-grid-tasks", "tasks.jsonl.xz"), "rt")):
    r = json.loads(line); rows[r["cell"]].append(r)

def counted(r, recovery):
    return r["status"] != "error" or (recovery and r.get("recovery") is not None)
def pool(r):
    if r["kind"] != "qa": return "action"
    return "notes" if int(re.sub(r"\D", "", r["taskId"])) <= 200 else "todo"
def qa_counts(rs, recovery):
    c = {"iu": [0, 0], "fr": [0, 0], "leak": [0, 0]}
    for r in rs:
        if r["kind"] != "qa" or not counted(r, recovery): continue
        if r["relationshipExpectedBehavior"] == "answer":
            c["iu"][1] += 1; c["iu"][0] += bool(r.get("factMatch"))
            c["fr"][1] += 1; c["fr"][0] += r["actualDecision"] == "refuse"
        elif r["relationshipExpectedBehavior"] == "refuse":
            c["leak"][1] += 1; c["leak"][0] += bool(r.get("relationshipLeaked"))
    return c
def fisher_two_sided(a, b, c, d):
    """Two-sided Fisher exact p-value for the 2x2 table [[a, b], [c, d]] (sum of tables at most as probable)."""
    n1, n2, k, n = a + b, c + d, a + c, a + b + c + d
    if n == 0 or k == 0 or k == n: return 1.0
    tot = comb(n, k); obs = comb(n1, a) * comb(n2, c)
    p = 0
    for x in range(max(0, k - n2), min(k, n1) + 1):
        w = comb(n1, x) * comb(n2, k - x)
        if w <= obs: p += w
    return min(1.0, p / tot)

# 1. gate: the per-row rules must reproduce the frozen cells exactly
bad = []
for cid, c in cells.items():
    for mode, rec in (("strict", False), ("recovered", True)):
        m = qa_counts(rows[cid], rec)
        if m["iu"] != [c[mode]["informationUtility"]["numerator"], c[mode]["informationUtility"]["denominator"]] \
           or m["leak"] != [c[mode]["leakRate"]["numerator"], c[mode]["leakRate"]["denominator"]]:
            bad.append((cid, mode))
if bad: sys.exit(f"per-row rules do not reproduce cells.json for {bad}")
print("gate: QA numerators/denominators of all 110 cells reproduced, strict and with-recovery")

# 2. per-pool, with recovery
def block(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": (100 * k / n if n else None), "ci": ([100 * lo, 100 * hi] if n else None)}
out = {"definition": {"notes": "Files QA, PAIR-Q1..Q200 (Notes QA in dataset/pact-pair/BENCHMARK_DATA.md)",
                      "todo": "States QA, PAIR-Q201..Q400 (Todo QA)",
                      "rates": "relationship-v2 with recovery; iu over entitled items (factMatch), fr over entitled items (refused), leak over protected items (relationshipLeaked)",
                      "gap": "todo minus notes, percentage points; fisher_p is the two-sided Fisher exact test of the two pools' counts"},
       "cells": {}}
for cid, c in cells.items():
    per = {}
    for pl in ("notes", "todo"):
        m = qa_counts([r for r in rows[cid] if pool(r) == pl], True)
        per[pl] = {k: block(*v) for k, v in m.items()}
    gap, pval = {}, {}
    for k in ("iu", "fr", "leak"):
        a, b = per["notes"][k], per["todo"][k]
        gap[k] = (b["pct"] - a["pct"]) if (a["pct"] is not None and b["pct"] is not None) else None
        pval[k] = fisher_two_sided(b["k"], b["n"] - b["k"], a["k"], a["n"] - a["k"]) if (a["n"] and b["n"]) else None
    out["cells"][cid] = {"family": c["family"], "policy": c["policy"], "requester": c["requester"], "responderShort": c["responderShort"],
                         "requesterShort": c["requesterShort"], "harness": c["harness"], "pools": per, "todo_minus_notes": gap, "fisher_p": pval}
json.dump(out, open(os.path.join(OUT, "pools.json"), "w"), indent=1)
print("wrote out/pools.json")

# 3. summary lines used in the text
def sel(pred): return [(cid, o) for cid, o in out["cells"].items() if pred(o)]
ladder = sel(lambda o: o["harness"] == "standard" and o["requesterShort"] == o["responderShort"] and o["policy"] in ("D0", "D1", "D2") and o["requester"] in ("R1", "R2", "R3"))
same = sel(lambda o: o["harness"] == "standard" and o["requesterShort"] == o["responderShort"])
for name, S in (("ladder 27", ladder), ("same-model 84", same), ("all 110", list(out["cells"].items()))):
    for k in ("leak", "fr"):
        g = [(o["todo_minus_notes"][k], o["fisher_p"][k]) for _, o in S if o["todo_minus_notes"][k] is not None]
        print(f"{name:14s} {k:4s} n={len(g):3d} todo>notes {sum(x > 0 for x, _ in g):3d} | p<.05: todo>notes {sum(x > 0 and p < .05 for x, p in g):3d}, notes>todo {sum(x < 0 and p < .05 for x, p in g):3d} | median gap {sorted(x for x, _ in g)[len(g)//2]:+.1f}")
print("\nD0/D1/D2 by pool, per model x requester (leak notes -> todo):")
for fam in ("ds41", "glm", "luna"):
    for req in ("R0", "R1", "R2", "R3"):
        s = []
        for pol in ("D0", "D1", "D2"):
            o = out["cells"][f"{fam}-{pol.lower()}-{req.lower()}"]; a, b = o["pools"]["notes"]["leak"], o["pools"]["todo"]["leak"]
            s.append(f"{pol} {a['pct']:.1f}->{b['pct']:.1f} (p={o['fisher_p']['leak']:.3f})")
        print(f"  {fam:5s} {req}: " + " | ".join(s))
print("\nD2 FR by pool (notes -> todo, p):")
for fam in ("ds41", "glm", "luna"):
    print("  " + fam + ": " + " | ".join(f"{req} {out['cells'][f'{fam}-d2-{req.lower()}']['pools']['notes']['fr']['pct']:.1f}->{out['cells'][f'{fam}-d2-{req.lower()}']['pools']['todo']['fr']['pct']:.1f} (n {out['cells'][f'{fam}-d2-{req.lower()}']['pools']['notes']['fr']['n']}/{out['cells'][f'{fam}-d2-{req.lower()}']['pools']['todo']['fr']['n']}, p={out['cells'][f'{fam}-d2-{req.lower()}']['fisher_p']['fr']:.3f})" for req in ("R1", "R2", "R3")))
print("\nR0 leak by pool (D0->D2):")
for fam in ("ds41", "glm", "luna"):
    print("  " + fam + ": " + " | ".join(f"{pol} {out['cells'][f'{fam}-{pol.lower()}-r0']['pools']['notes']['leak']['pct']:.1f}/{out['cells'][f'{fam}-{pol.lower()}-r0']['pools']['todo']['leak']['pct']:.1f} (n {out['cells'][f'{fam}-{pol.lower()}-r0']['pools']['notes']['leak']['n']}/{out['cells'][f'{fam}-{pol.lower()}-r0']['pools']['todo']['leak']['n']})" for pol in ("D0", "D1", "D2")))
