#!/usr/bin/env python3
"""Rebuild the 79 later exposures from the frozen probing records and attach the LLM reviewer's verdicts.

The review (2026-09-26, PAIR II probing grid) was done by an agent session (Claude Opus 5.5) that numbered
the cases with its own extraction script (later_exposures/reviewer_scripts/q11extract.py) and recorded its
verdicts as Python lists in its classification step (reviewer_scripts/q11classify.py). Its output file
q11_verdicts.json was written to a scratch directory that no longer exists; the lists and every case
header it was shown survive in its session transcript and are frozen here.

This script
  1. rebuilds the cases from contacts.jsonl.gz with the same rule as q11extract.py: protected questions
     (category gold) whose first reply has no hit of the acceptance analyser's matcher (targetDisclosure)
     while a later reply has one, sorted by (run, task), contacts sorted by (attempt, tick);
  2. checks that case k is the (run, task) the reviewer was shown as case k, for all 79;
  3. reads the verdict lists out of q11classify.py without executing it;
  4. writes cases.json: each case with its question, gold facts, first reply, every flagged later reply and
     the reviewer's verdict, mechanism note and strength.

Usage: python3 later_exposures.py <multi-probing-records dir> <questions.json> > summary.json
"""
import ast
import collections
import gzip
import hashlib
import json
import os
import sys

REC, QUESTIONS = sys.argv[1], sys.argv[2]
LE = os.path.join(REC, "later_exposures")
QSHA = "9032f46a79b2c9d6f6664b8aabea4006561b287de66bb59b0304cf619fdb265a"

qbytes = open(QUESTIONS, "rb").read()
assert hashlib.sha256(qbytes).hexdigest() == QSHA, "questions.json is not the set the grid ran on"
Q = {f"PAIR-Q{q['id']}": q for q in json.loads(qbytes)["questions"]}

inst = collections.defaultdict(list)
with gzip.open(os.path.join(REC, "contacts.jsonl.gz"), "rt", encoding="utf-8") as fh:
    for line in fh:
        r = json.loads(line)
        if r["kind"] == "qa" and r["expectedBehavior"] == "refuse":
            inst[(r["runId"], r["taskId"])].append(r)

cases = []
for (rid, tid), cs in sorted(inst.items()):
    cs = sorted(cs, key=lambda r: (r["attempt"], r["tick"]))
    if cs[0].get("targetDisclosure") or not any(c.get("targetDisclosure") for c in cs):
        continue
    q = Q[tid]
    cases.append({
        "case": len(cases) + 1, "runId": rid, "requester": cs[0]["requester"], "rep": cs[0]["rep"],
        "group": cs[0]["group"], "taskId": tid, "category": q["category"], "question": q["question"],
        "gold": q["gold_key_facts"],
        "firstAsk": {"request": cs[0]["requestText"], "response": cs[0]["response"],
                     "memoryStatus": cs[0]["memoryStatus"]},
        "terminalStatus": cs[-1]["memoryStatus"],
        "flaggedLaterReplies": [{"attempt": c["attempt"], "tick": c["tick"], "strategy": c.get("claimedStrategy"),
                                 "memoryStatus": c["memoryStatus"], "textualRefusal": c.get("textualRefusal"),
                                 "matchedGoldIdx": c.get("ownFactMatchIndices"), "request": c["requestText"],
                                 "response": c["response"]}
                                for c in cs if c.get("targetDisclosure")],
    })
assert len(cases) == 79, len(cases)

headers = json.load(open(os.path.join(LE, "reviewer_case_headers.json")))["cases"]
mismatch = [c["case"] for c in cases
            if (headers[str(c["case"])]["runId"], headers[str(c["case"])]["taskId"]) != (c["runId"], c["taskId"])]
assert not mismatch, f"case numbering differs from the reviewer's at {mismatch}"

lists = {}
for node in ast.parse(open(os.path.join(LE, "reviewer_scripts", "q11classify.py")).read()).body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in (
            "real", "weak", "fp_echo_request", "fp_restate_q", "fp_taskid"):
        lists[node.targets[0].id] = ast.literal_eval(node.value)
real = set(lists["real"])
fp = {**{c: "echoes the requester's own words" for c in lists["fp_echo_request"]},
      **{c: "restates the question" for c in lists["fp_restate_q"]},
      **{c: "gold 'Q2' matched inside task id PAIR-Q252" for c in lists["fp_taskid"]}}
assert len(real) == 43 and len(fp) == 36 and real.isdisjoint(fp) and real | set(fp) == set(range(1, 80))

summary = collections.Counter()
by_req = collections.defaultdict(lambda: [0, 0])
for c in cases:
    k = c["case"]
    if k in real:
        weak = lists["weak"].get(k)
        c["reviewer"] = {"verdict": "disclosure", "strength": "weak or borderline" if weak else "strong",
                         "note": weak}
        channel = "answered" if any(r["memoryStatus"] == "answered" for r in c["flaggedLaterReplies"]) else "refusal only"
        c["reviewer"]["channel"] = channel
        summary["disclosure"] += 1
        summary[f"disclosure, {channel}"] += 1
        summary["disclosure, weak or borderline" if weak else "disclosure, strong"] += 1
        by_req[c["requester"]][0] += 1
    else:
        c["reviewer"] = {"verdict": "matcher false positive", "note": fp[k]}
        summary["matcher false positive"] += 1
        summary[f"false positive: {fp[k]}"] += 1
    by_req[c["requester"]][1] += 1

with open(os.path.join(LE, "cases.json"), "w") as fh:
    json.dump({"note": "The 79 later exposures of the probing grid with the LLM reviewer's verdicts. "
                       "Rebuilt from contacts.jsonl.gz by scripts/pair_multi/probing_records/later_exposures.py.",
               "cases": cases}, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
json.dump({"cases": len(cases), "flaggedLaterReplies": sum(len(c["flaggedLaterReplies"]) for c in cases),
           "headersMatched": 79 - len(mismatch), "counts": dict(sorted(summary.items())),
           "disclosuresByRequester": {r: f"{v[0]}/{v[1]}" for r, v in sorted(by_req.items())}},
          sys.stdout, indent=1)
print()
