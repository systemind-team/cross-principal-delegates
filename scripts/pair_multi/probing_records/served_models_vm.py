#!/usr/bin/env python3
"""Which model served the requester (the prober) and the responder in every probing-grid session.

Reads every run's .sharedeval-file-workflow/records/record-*.json and counts provider calls by actor and
served model (payload.privateEvidence.providerTelemetry.<actor>.requests[].servedModel). Read-only.

Usage (VM): python3 served_models_vm.py <grid lane dir> > served_models.json
"""
import collections
import glob
import json
import sys

LANE = sys.argv[1]
served = collections.Counter()
runs = records = unreadable = 0
for d in sorted(glob.glob(f"{LANE}/cfg/runs/G6-*/multi/.sharedeval-file-workflow/records")):
    runs += 1
    for f in glob.glob(f"{d}/record-*.json"):
        records += 1
        try:
            r = json.load(open(f))
        except (OSError, ValueError):
            unreadable += 1
            continue
        telemetry = ((r.get("payload") or {}).get("privateEvidence") or {}).get("providerTelemetry") or {}
        for actor, v in telemetry.items():
            for q in (v or {}).get("requests") or []:
                served[f"{actor} / {q.get('servedModel') or 'not recorded'}"] += 1
json.dump({"runs": runs, "records": records, "unreadable_records": unreadable,
           "provider_calls_by_actor_and_served_model": dict(sorted(served.items()))}, sys.stdout, indent=1)
print()
