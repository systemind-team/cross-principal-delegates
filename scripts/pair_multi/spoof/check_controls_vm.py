#!/usr/bin/env python3
"""P1-6: the control arms' run configs are byte-identical to the 10-02 header comparison's (read only, on the VM).

SP-A0h-r<k>-<g>.json must equal I2-ID-R0-<g>.json, and SP-A0n-r<k>-<g>.json must equal I2-PR-R0-<g>.json, for both
replicates and all 50 groups; an impersonation config must differ from its control only by benchmark.spoof.

Usage (VM): python3 check_controls_vm.py <spoof lane> <10-02 lane> > controls_check.json
"""
import glob
import hashlib
import json
import os
import sys

L, REF = sys.argv[1], sys.argv[2]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
rows, only_spoof_differs = [], []
for f in sorted(glob.glob(f"{L}/cfg/SP-*.json")):
    _, arm, rep, g = os.path.basename(f)[:-5].split("-")
    if arm in ("A0h", "A0n"):
        ref = f"{REF}/cfg/I2-{'ID' if arm == 'A0h' else 'PR'}-R0-{g}.json"
        rows.append({"config": os.path.basename(f), "reference": os.path.basename(ref), "identical": sha(f) == sha(ref)})
    else:
        ctrl = json.load(open(f"{L}/cfg/SP-{'A0h' if arm in ('C1h', 'C2h', 'P1h') else 'A0n'}-{rep}-{g}.json"))
        mine = json.load(open(f))
        spoof = mine["benchmark"].pop("spoof", None)
        only_spoof_differs.append(mine == ctrl and spoof is not None)
json.dump({"controls": len(rows), "controls_identical": sum(r["identical"] for r in rows),
           "impersonation_configs": len(only_spoof_differs),
           "impersonation_configs_differing_only_by_spoof": sum(only_spoof_differs), "rows": rows}, sys.stdout, indent=1)
print()
