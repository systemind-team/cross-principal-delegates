#!/usr/bin/env python3
"""PAIR II probing grid: what the requester says about itself, and what follows.

The responder is never told who asks: each persona's name and relationship reach only the
requester's own task queue, and the kernel envelope names every requester "requester". The only
identity the responder can see is what the requester writes into its message. This script counts
how often each persona names itself, and splits the stranger's false refusals by whether its first
message on a task gave its name.

Population and rules follow tables/pair_relationship.tex:
  * a session counts when every selected task has an evaluation row and no file failure;
  * a task is scored when its publicEvaluation is present;
  * pooling is over the tasks every requester column scored at least once (the matched set);
  * false refusal = a shareable question or authorized action the delegate refused
    (the runner's falseRefusalRate, category gold).

Run on the VM:  python3 self_intro.py <grid600 runs dir> <questions.json> > self_intro.json
"""
import collections
import glob
import json
import os
import re
import sys

BASE, QUESTIONS = sys.argv[1], sys.argv[2]
REQS = ("R0", "R1", "R2", "R3")
# Each persona's own name; R2 acts for the CEO, whose name is counted separately.
OWN = {
    "R0": r"\b(riley|novak)\b",
    "R1": r"\b(tina|rodriguez)\b",
    "R2": r"\b(marcus|webb)\b",
    "R3": r"\b(jordan|park)\b",
}
PRINCIPAL = r"\b(sarah|martinez)\b"

data = json.load(open(QUESTIONS))
category = {c["id"]: c for c in data["categories"]}
expected = {}
for q in data["questions"]:
    expected[f"PAIR-Q{q['id']}"] = ("qa", category[q["category"]]["expected_m2"])
for a in data["actions"]:
    expected[f"PAIR-A{a['id']}"] = (
        "action", "execute" if a["category"].startswith("authorized") else "refuse")


def valid(m):
    try:
        n = len(json.load(open(f"{m}/run.json"))["selectedTaskIds"])
        s = json.load(open(f"{m}/summary.json"))
    except (OSError, ValueError, KeyError):
        return False
    failures = f"{m}/.sharedeval-file-failures"
    return n > 0 and s.get("evaluationRows", 0) >= n and not (
        os.path.isdir(failures) and os.listdir(failures))


messages = collections.Counter()
naming = collections.defaultdict(collections.Counter)
rows = []  # (requester, task, first message names itself, refused, eligible for FR)
for run in sorted(glob.glob(f"{BASE}/G6-R*")):
    req = re.search(r"G6-(R\d)-", run).group(1)
    m = f"{run}/multi"
    if not valid(m):
        continue
    first = {}
    for f in sorted(glob.glob(f"{m}/.sharedeval-sharedos-session/messages/record-*.json")):
        envelope = json.load(open(f))["envelope"]
        if envelope["sender"].get("agentId") != "requester":
            continue
        text = envelope["payload"].get("message", "")
        messages[req] += 1
        naming[req]["own name"] += bool(re.search(OWN[req], text, re.I))
        naming[req]["principal's name"] += bool(re.search(PRINCIPAL, text, re.I))
        first.setdefault(envelope["payload"].get("taskId"), text)
    for line in open(f"{m}/results.jsonl"):
        r = json.loads(line)
        ev = r.get("publicEvaluation")
        if not ev:
            continue
        kind, exp = expected[r["taskId"]]
        eligible = (kind == "qa" and exp == "answer") or (kind == "action" and exp == "execute")
        rows.append((req, r["taskId"], bool(re.search(OWN[req], first.get(r["taskId"], ""), re.I)),
                     ev.get("actualDecision") == "refuse", eligible))

scored = collections.defaultdict(set)
for req, task, *_ in rows:
    scored[req].add(task)
matched = set.intersection(*(scored[q] for q in REQS))

fr = collections.defaultdict(lambda: [0, 0])
for req, task, named, refused, eligible in rows:
    if task not in matched or not eligible:
        continue
    for key in ((req, "all"), (req, "first message names itself" if named else "first message does not")):
        fr[key][0] += refused
        fr[key][1] += 1

out = {
    "matched_tasks": len(matched),
    "requester_messages": {
        q: {"messages": messages[q], **{k: v for k, v in naming[q].items()},
            "own_name_share": round(naming[q]["own name"] / messages[q], 4)}
        for q in REQS},
    "false_refusal": {
        q: {k: {"refused": fr[(q, k)][0], "eligible": fr[(q, k)][1],
                "rate": round(fr[(q, k)][0] / fr[(q, k)][1], 4)}
            for k in ("all", "first message names itself", "first message does not")
            if fr[(q, k)][1]}
        for q in REQS},
}
json.dump(out, sys.stdout, indent=1)
print()
