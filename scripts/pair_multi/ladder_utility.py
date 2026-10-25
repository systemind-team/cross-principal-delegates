#!/usr/bin/env python3
"""Multi-turn ladder: information utility next to false refusal. Read-only over run artifacts.

Table 4 reports decision leak, false refusal and action safety. A low false refusal says the
delegate answered; it does not say the answer carried the facts asked for. This script scores that
second question on the same population as Table 4 (analyze_s4.py rules):
  * source run per (build, rung, requester, group): first attempt if valid, else its -x2 retry;
  * inside each (build, requester) block, rungs are compared on tasks scored at all three rungs;
  * U = shareable question (category gold, expected_m2 == answer) answered with the gold facts
    (publicEvaluation.factMatch, the deterministic matcher, which misses some paraphrases at every
    rung alike); paired exact McNemar D0 -> D2 on the same tasks.

Usage (VM):  python3 ladder_utility.py <t3simple dir> <questions.json> > ladder_utility.json
"""
import collections
import json
import math
import os
import sys

L, QUESTIONS = sys.argv[1], sys.argv[2]
data = json.load(open(QUESTIONS))
category = {c["id"]: c for c in data["categories"]}
allowed = {f"PAIR-Q{q['id']}" for q in data["questions"]
           if category[q["category"]]["expected_m2"] == "answer"}
groups = json.load(open(f"{L}/MANIFEST.json"))["groups"]
BUILDS, POLS, REQS = ("DS", "GLM", "GROK"), ("D0", "D1", "D2"), ("R1", "R2", "R3")


def valid(m):
    try:
        s = json.load(open(f"{m}/summary.json"))
        u = s.get("usage") or {}
        return s.get("evaluationRows") == s.get("selectedTasks") and (u.get("contactCalls") or 0) > 0
    except (OSError, ValueError):
        return False


ev = {}
for b in BUILDS:
    for p in POLS:
        for r in REQS:
            for g in sorted(groups):
                first = f"{L}/cfg/runs/S4-{b}-{p}-{r}-{g}/multi"
                retry = f"{L}/cfg/runs/S4-{b}-{p}-{r}-{g}-x2/multi"
                m = first if valid(first) else retry if valid(retry) else None
                if m is None:
                    continue
                for line in open(f"{m}/results.jsonl"):
                    pe = json.loads(line).get("publicEvaluation")
                    if pe:
                        ev[(b, p, r, g, pe["taskId"])] = pe


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


out = {"blocks": {}}
for b in BUILDS:
    for r in REQS:
        keep = [(g, t) for g in groups for t in groups[g]
                if t in allowed and all((b, p, r, g, t) in ev for p in POLS)]
        block = {"n": len(keep)}
        for p in POLS:
            hit = sum(bool(ev[(b, p, r, g, t)].get("factMatch")) for g, t in keep)
            answered = sum(ev[(b, p, r, g, t)].get("actualDecision") == "answer" for g, t in keep)
            block[p] = {"U": round(100 * hit / len(keep), 1), "answered": round(100 * answered / len(keep), 1)}
        x = [bool(ev[(b, "D0", r, g, t)].get("factMatch")) for g, t in keep]
        y = [bool(ev[(b, "D2", r, g, t)].get("factMatch")) for g, t in keep]
        lost = sum(1 for u, v in zip(x, y) if u and not v)
        gained = sum(1 for u, v in zip(x, y) if v and not u)
        block["D0_to_D2"] = {"lost": lost, "gained": gained, "p": round(mcnemar(lost, gained), 4)}
        out["blocks"][f"{b}-{r}"] = block
json.dump(out, sys.stdout, indent=1)
print()
