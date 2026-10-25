#!/usr/bin/env python3
"""SharedEval revision of each ablation session, from its launch logs on the VM (read only).

    ssh <host> "python3 -" < revisions.py > evidence/v3.14/ablation-ladder/revisions.json

A session relaunched by the scheduler has several logs (<runId>.p1.log, .p2.log, ...); the last pass that printed
a sourceRevision is the one whose folder the records come from. Output: {runId: {"revision": sha, "passes": n}}.
"""
import glob
import json
import os
import re

L = "<vm>/runs/ablation/logs"
out = {}
for f in sorted(glob.glob(f"{L}/AB-*.log")):
    m = re.match(r"(AB-.+)\.p(\d+)\.log$", os.path.basename(f))
    if not m:
        continue
    rid, n = m.group(1), int(m.group(2))
    rev = re.findall(r'"sourceRevision": "([0-9a-f]{40})"', open(f, errors="replace").read())
    cur = out.setdefault(rid, {"revision": None, "passes": 0, "_last": -1})
    cur["passes"] = max(cur["passes"], n)
    if rev and n > cur["_last"]:
        cur["revision"], cur["_last"] = rev[-1], n
for v in out.values():
    v.pop("_last")
print(json.dumps(out, indent=0, sort_keys=True))
