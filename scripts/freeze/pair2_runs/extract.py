#!/usr/bin/env python3
"""Extract PAIR II per-task records from SharedEval run folders on the experiment VM (read only).

Run on the VM with the script on stdin and the output piped through a compressor, so nothing is written
there:
    ssh <host> "python3 - identity | xz -9" < extract.py > identity.jsonl.xz
    ssh <host> "python3 - ladder   | xz -9" < extract.py > ladder.jsonl.xz
    ssh <host> "python3 - told     | xz -9" < extract.py > told.jsonl.xz

One JSON line per session slot (cell, requester, group): the run folder chosen by the analyses' own rule
(first attempt if valid, else its "-x2" retry if valid, else none; valid = evaluationRows == selectedTasks and
contactCalls > 0), each task's publicEvaluation and status, every message of the session in ledger order
(sequence, sender, task, text: the requester's `message` or the responder's `response`), and the sha256 of
the POLICY.md the responder read. A final line {"policies": {sha256: text}} carries each policy text once.
"""
import glob
import hashlib
import json
import os
import sys

LANES = {
    "identity": ("<vm>/runs/pair2id2", "I2-{arm}-{r}-{g}", {"arm": ("PR", "ID")}, ("R0", "R1", "R2", "R3")),
    "ladder": ("<vm>/runs/t3simple", "S4-{arm}-{rung}-{r}-{g}",
               {"arm": ("DS", "GLM", "GROK"), "rung": ("D0", "D1", "D2")}, ("R1", "R2", "R3")),
    "told": ("<vm>/runs/pair2told", "T3-{arm}-{rung}-{r}-{g}",
             {"arm": ("TOLD", "CTRL"), "rung": ("D0", "D1", "D2")}, ("R1", "R2", "R3")),
}


def valid(m):
    try:
        s = json.load(open(m + "/summary.json"))
        u = s.get("usage") or {}
        return s.get("evaluationRows") == s.get("selectedTasks") and (u.get("contactCalls") or 0) > 0
    except (OSError, ValueError):
        return False


def cells(spec):
    keys = list(spec)
    if len(keys) == 1:
        for a in spec[keys[0]]:
            yield {keys[0]: a}
    else:
        for a in spec["arm"]:
            for rung in spec["rung"]:
                if a == "CTRL" and rung != "D2":
                    continue
                yield {"arm": a, "rung": rung}


def main():
    lane = sys.argv[1]
    L, pat, spec, reqs = LANES[lane]
    groups = json.load(open(L + "/MANIFEST.json"))["groups"]
    policies = {}
    for cell in cells(spec):
        for r in reqs:
            for g in sorted(groups):
                rid = pat.format(r=r, g=g, **cell)
                first = f"{L}/cfg/runs/{rid}/multi"
                retry = f"{L}/cfg/runs/{rid}-x2/multi"
                m = first if valid(first) else retry if valid(retry) else None
                rec = {"lane": lane, **cell, "requester": r, "group": g, "tasks_selected": groups[g],
                       "run": None if m is None else os.path.relpath(m, L)}
                if m is not None:
                    rows = [json.loads(l) for l in open(m + "/results.jsonl")]
                    rec["tasks"] = [{"task": x.get("taskId"), "status": x.get("status"),
                                     "contactStatus": x.get("contactStatus"),
                                     "publicEvaluation": x.get("publicEvaluation")} for x in rows]
                    msgs = []
                    for f in glob.glob(m + "/.sharedeval-sharedos-session/messages/record-*.json"):
                        e = json.load(open(f))
                        env = e["envelope"]
                        pl = env["payload"]
                        who = env["sender"]["agentId"]
                        text = pl.get("message") if who == "requester" else pl.get("response")
                        msgs.append([e["sequence"], who, pl.get("taskId"), text])
                    rec["messages"] = sorted(msgs, key=lambda x: x[0])
                    ps = glob.glob(m[:-len("/multi")] + "/workspaces/runs/*/workspaces/responder/versions/*/POLICY.md")
                    texts = sorted({open(p).read() for p in ps})
                    shas = []
                    for t in texts:
                        h = hashlib.sha256(t.encode()).hexdigest()
                        policies[h] = t
                        shas.append(h)
                    rec["policy_sha256"] = shas
                print(json.dumps(rec, ensure_ascii=False))
    print(json.dumps({"policies": policies}, ensure_ascii=False))


if __name__ == "__main__":
    main()
