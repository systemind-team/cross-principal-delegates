#!/usr/bin/env python3
"""Azure content-filter blocks in t3simple: which tasks they cost, per cell. Read-only.

A block = a responder request answered HTTP 400. Every 400 whose body was logged (fetchlog/,
errors only, all full-grid runs) is checked for finish_reason content_filter; the pilot runs
(g004, g100) predate the log and are attributed by status alone.
"""
import json, glob, os, collections, sys
L = "<vm>/runs/t3simple"; os.chdir(L)
src = open("analyze_s4.py").read(); cut = src.index("# per (cell, group, task) evaluation"); g = {}; exec(src[:cut], g)
choice, TASKS, kindof = g["choice"], g["TASKS"], g["kindof"]
BUILDS, POLS, REQS = g["BUILDS"], g["POLS"], g["REQS"]
# 1. every logged provider error, by body
bodies = collections.Counter()
for f in glob.glob(L + "/fetchlog/*/*.err.txt"):
    st = open(f[:-8] + ".status.txt").read().strip()
    try:
        j = json.loads(open(f).read())
        ch = (j.get("choices") or [{}])[0]
        why = (ch.get("content_filter_results") or {}).get("error", {}).get("message") if ch.get("finish_reason") == "content_filter" else (j.get("error") or {}).get("code")
    except Exception:
        why = "unparsed"
    bodies[(st, why)] += 1
print("logged provider errors (status, cause):", dict(bodies))
# 2. per chosen run: tasks with a blocked contact, scored or not
cell = collections.defaultdict(collections.Counter)
touched = []
for (b, p, r, gr), m in choice.items():
    if m is None: continue
    blocked = collections.Counter()
    for f in glob.glob(m + "/.sharedeval-file-workflow/records/record-*.json"):
        try: rec = json.load(open(f))
        except Exception: continue
        pl = rec.get("payload") or {}
        ca = pl.get("contactAuthority") or {}
        tel = (pl.get("privateEvidence") or {}).get("providerTelemetry") or {}
        n400 = sum(1 for q in (tel.get("responder") or {}).get("requests") or [] if q.get("httpStatus") == 400)
        if n400 and ca.get("taskId"): blocked[ca["taskId"]] += 1
    rows = {json.loads(l)["taskId"]: json.loads(l) for l in open(m + "/results.jsonl")}
    c = cell[(b, p, r)]
    c["runs"] += 1; c["runs_with_block"] += bool(blocked)
    for t in TASKS[gr]:
        scored = (rows.get(t) or {}).get("publicEvaluation") is not None
        c["tasks"] += 1
        if blocked.get(t):
            touched.append([b, p, r, gr, t])
            c["lost" if not scored else "scored_after_block"] += 1
            if not scored and kindof(t) == "qa_refuse": c["lost_protected"] += 1
        elif not scored:
            c["lost_other"] += 1
out = {f"{b}-{p}-{r}": dict(cell[(b, p, r)]) for b in BUILDS for p in POLS for r in REQS}
out["touched"] = touched
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else L + "/filter_loss.json", "w"), indent=1)
for b in BUILDS:
    tot = collections.Counter()
    for p in POLS:
        for r in REQS: tot.update(cell[(b, p, r)])
    print(f"{b}: runs {tot['runs']} with a block {tot['runs_with_block']} | tasks {tot['tasks']}: lost to a block {tot['lost']} "
          f"(protected {tot['lost_protected']}), scored though a later contact was blocked {tot['scored_after_block']}, lost otherwise {tot['lost_other']}")
    for p in POLS:
        print("   ", p, " ".join(f"{r}: lost {cell[(b,p,r)]['lost']} blk-runs {cell[(b,p,r)]['runs_with_block']}" for r in REQS))
