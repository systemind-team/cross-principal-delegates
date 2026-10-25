#!/usr/bin/env python3
"""List the plan's task-runs that Azure rate limiting killed, so they can run again.

  python3 retry_list.py <runs-dir> <out.json>

A task-run is listed if it ended in error and at least one of its model requests ended as a provider error
with HTTP 429 after the runner's retries were exhausted: the model never produced the outcome being measured.
Every other error (quarantined requester turns, which the rescore may recover, and failures without a 429)
stands as it is. The rerun uses the cell's config with only the task ids changed (run id <cell>-retry).
"""
import collections, glob, json, os, sys

runs, out = sys.argv[1], sys.argv[2]


def requests(obj, acc):
    if isinstance(obj, dict):
        if "outcome" in obj and ("usage" in obj or "httpStatus" in obj):
            acc.append(obj)
        for v in obj.values():
            requests(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            requests(v, acc)


cells, other = {}, collections.Counter()
for run in sorted(glob.glob(os.path.join(runs, "grok-d[0-9]-r[0-9]"))):
    cell = os.path.basename(run)
    for d in sorted(glob.glob(os.path.join(run, "single", "*"))):
        result = json.loads(open(os.path.join(d, "results.jsonl")).readline())
        if result["status"] != "error":
            continue
        acc = []
        for f in glob.glob(os.path.join(d, ".sharedeval-file-workflow", "records", "*.json")):
            requests(json.load(open(f)), acc)
        if any(q["outcome"] == "provider_error" and q.get("httpStatus") == 429 for q in acc):
            cells.setdefault(cell, []).append({"taskId": result["taskId"], "errorCode": result["errorCode"]})
        else:
            other[result["errorCode"]] += 1
json.dump({"rule": "status error and a model request ended provider_error with HTTP 429 after retries",
           "taskRuns": sum(len(v) for v in cells.values()), "notListed": dict(other), "cells": cells},
          open(out, "w"), indent=1)
print(f"{sum(len(v) for v in cells.values())} rate-limited task-runs in {len(cells)} cells; not listed: {dict(other)}")
