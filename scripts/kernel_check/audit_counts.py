#!/usr/bin/env python3
"""Kernel check: kernel audit records of SharedEval run directories, counted.

For each run directory given (a SharedEval run root holding multi/ or single/), reads every SharedOS audit
record the harness persisted (`<mode>/.sharedeval-sharedos-session/audit/record-*.json`, field `event`) and
prints one JSON line: run id, mode, record count, counts by (type, outcome, reason), the set of event keys
seen, the per-task terminal statuses from results.jsonl, and summary.json's statuses.

Usage: audit_counts.py <run-root> [<run-root> ...]
Reads only; writes nothing.
"""
import collections
import glob
import json
import os
import sys


def one(root):
    for mode in ("multi", "single"):
        d = os.path.join(root, mode)
        if os.path.isdir(os.path.join(d, ".sharedeval-sharedos-session")):
            break
    else:
        return {"run": os.path.basename(root.rstrip("/")), "error": "no sharedos session directory"}
    counts = collections.Counter()
    keys = collections.Counter()
    files = sorted(glob.glob(os.path.join(d, ".sharedeval-sharedos-session/audit/record-*.json")))
    for f in files:
        e = json.load(open(f))["event"]
        counts["|".join((e["type"], e["outcome"], e.get("reason", "")))] += 1
        keys.update(e.keys())
    results = []
    rp = os.path.join(d, "results.jsonl")
    if os.path.exists(rp):
        for line in open(rp):
            if line.strip():
                r = json.loads(line)
                results.append([r.get("taskId"), r.get("status")])
    summary = {}
    sp = os.path.join(d, "summary.json")
    if os.path.exists(sp):
        s = json.load(open(sp))
        summary = {"statuses": s.get("statuses"), "evaluationRows": s.get("evaluationRows"),
                   "selectedTasks": s.get("selectedTasks")}
    return {"run": os.path.basename(root.rstrip("/")), "mode": mode, "audit_records": len(files),
            "by_type_outcome_reason": dict(sorted(counts.items())), "event_keys": dict(sorted(keys.items())),
            "results": results, "summary": summary}


if __name__ == "__main__":
    for root in sys.argv[1:]:
        print(json.dumps(one(root), sort_keys=True))
