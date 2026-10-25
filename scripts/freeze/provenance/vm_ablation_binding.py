#!/usr/bin/env python3
"""What the D.6 ablation lane bound at run time (read-only on the VM, fed over stdin):

    ssh <host> 'nice -n 19 python3 -' < scripts/freeze/provenance/vm_ablation_binding.py > ablation_binding.json

The same reads as vm_checks.py's recorded() for one more lane, <vm>/runs/ablation, split by arm
(AB-D0T, AB-D1T: Table 33's D0 and D1; AB-D0S, AB-D2S: the simple-profile arms): per run, only
binding.sharedOs.sharedOsRevision and .sharedOsRuntimeDigest from .sharedeval-file-workflow/binding.json and
backend.kernelRevision and .kernelRuntimeDigest from run.json. Nothing else is opened.
"""
import collections
import glob
import json
import os

LANE = "<vm>/runs/ablation"
out = {"lane": "ablation", "arms": {}}
for arm in ("AB-D0T", "AB-D1T", "AB-D0S", "AB-D2S"):
    bind, kern = collections.Counter(), collections.Counter()
    runs = sorted(glob.glob(f"{LANE}/cfg/runs/{arm}-*/multi"))
    for m in runs:
        try:
            b = json.load(open(f"{m}/.sharedeval-file-workflow/binding.json")).get("binding", {}).get("sharedOs", {})
            bind[(b.get("sharedOsRevision"), b.get("sharedOsRuntimeDigest"))] += 1
        except Exception:
            bind[("unreadable", "unreadable")] += 1
        try:
            k = json.load(open(f"{m}/run.json")).get("backend", {}) or {}
            kern[(k.get("kernelRevision"), k.get("kernelRuntimeDigest"))] += 1
        except Exception:
            kern[("unreadable", "unreadable")] += 1
    fmt = lambda c: [{"revision": k[0], "runtime_digest": k[1], "runs": n} for k, n in sorted(c.items(), key=lambda x: -x[1])]
    out["arms"][arm] = {"runs": len(runs), "binding_sharedOs": fmt(bind), "run_json_backend_kernel": fmt(kern)}
print(json.dumps(out, indent=1))
