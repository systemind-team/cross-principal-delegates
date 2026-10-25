#!/usr/bin/env python3
"""P2-3 design (no spend): provider-reported tokens and cost per actor in every P1-6 run folder (read only).

Run on the experiment VM with the script on stdin, so nothing is written there:
    ssh <host> "python3 - <vm>/runs/pair2spoof" < tokens_vm.py | xz -9 > tokens.jsonl.xz

For each run folder under <lane>/cfg/runs/ (pilot, both passes and reruns: every folder the $12.51 ledger paid
for), one JSON line with
  folder, summary_cost_usd (summary.json usage.costUsd, the cost extract_vm.py froze per attempt),
  evaluation_rows, selected_tasks, contact_calls, ticks_with_records, and
  actors.<actor>: requests, ticks, requests by served provider, and the sums of the provider-reported usage
                  (promptTokens, cachedTokens, completionTokens, reasoningTokens, costUsd);
  calls: one row per provider request, [actor, tick, index within the tick, promptTokens, cachedTokens,
         completionTokens, reasoningTokens, costUsd, provider], in record order.
It reads each tick record's privateEvidence.providerTelemetry only: no key, no ledger and no model text.
"""
import glob
import json
import os
import sys

L = sys.argv[1]
FIELDS = ("promptTokens", "cachedTokens", "completionTokens", "reasoningTokens", "costUsd")


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return None


for folder in sorted(glob.glob(f"{L}/cfg/runs/*")):
    m = folder + "/multi"
    summ = load(m + "/summary.json") or {}
    usage = summ.get("usage") or {}
    rec = {"folder": os.path.basename(folder), "summary_cost_usd": usage.get("costUsd"),
           "evaluation_rows": summ.get("evaluationRows"), "selected_tasks": summ.get("selectedTasks"),
           "contact_calls": usage.get("contactCalls"), "ticks_with_records": 0, "actors": {}, "calls": []}
    for f in sorted(glob.glob(m + "/.sharedeval-file-workflow/records/record-*.json")):
        d = load(f) or {}
        payload = d.get("payload") or {}
        tick = (payload.get("event") or {}).get("tick")
        tel = ((payload.get("privateEvidence") or {}).get("providerTelemetry")) or {}
        rec["ticks_with_records"] += 1
        for actor in sorted(tel):
            reqs = (tel[actor] or {}).get("requests") or []
            a = rec["actors"].setdefault(actor, {"requests": 0, "ticks": 0, "by_provider": {},
                                                 "requests_without_usage": 0, **{k: 0 for k in FIELDS}})
            if reqs:
                a["ticks"] += 1
            for i, q in enumerate(reqs):
                a["requests"] += 1
                prov = q.get("provider") or "not recorded"
                a["by_provider"][prov] = a["by_provider"].get(prov, 0) + 1
                u = q.get("usage") or {}
                if not u:
                    a["requests_without_usage"] += 1
                for k in FIELDS:
                    a[k] += u.get(k) or 0
                rec["calls"].append([actor, tick, i] + [u.get(k) for k in FIELDS] + [prov])
    print(json.dumps(rec, sort_keys=True))
