#!/usr/bin/env python3
"""PAIR II told ladder: writes the run configs.

The ladder (t3simple) never tells the responder who asks. This lane reruns DeepSeek's ladder with
the runtime-verified caller head in front of each rung (SharedEval 8081e7e + the told-policy patch,
4565add), and adds an untold D2 control on the same route:
  TOLD  benchmark.policy = D{0,1,2}_ID_<R>   R1-R3, 50 groups  -> 450 sessions
  CTRL  benchmark.policy = D2                R1-R3, 50 groups  -> 150 sessions
The control separates the route (the ladder ran on Azure, this lane on OpenRouter) from the head.

Everything else is the identity rerun's model block and the ladder's workflow: DeepSeek V4 Flash 0731
through the budget-capped gateway, pinned to the Relace upstream; simple profile, 22 ticks, multi-turn
phases at ticks 4 and 19, temperature 0, 4,096 output tokens; category grading as in the ladder.

Usage (VM):  python3 gen.py <t3simple dir> <out dir>
"""
import hashlib
import json
import os
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
REQS = ("R1", "R2", "R3")
PILOT_GROUPS = ("g004",)
MODEL = {
    "provider": "openai-compatible",
    "baseUrl": "http://127.0.0.1:8787/v1",
    "apiKeyEnv": "SHAREDEVAL_MODEL_API_KEY",
    "model": "deepseek/deepseek-v4-flash-0731",
    "maxOutputTokens": 4096,
    "temperature": 0,
    "attemptTimeoutMs": 300000,
    "providerRouting": {"order": ["Relace"], "only": ["Relace"], "allowFallbacks": False},
}
CELLS = [("TOLD", f"D{n}") for n in (0, 1, 2)] + [("CTRL", "D2")]

groups = json.load(open(f"{SRC}/MANIFEST.json"))["groups"]
assert len(groups) == 50, len(groups)
template = json.load(open(f"{SRC}/cfg/S4-DS-D2-R1-g004.json"))
assert template["workflow"]["pairProfile"] == "simple" and template["benchmark"]["gradingMode"] == "category"

os.makedirs(f"{OUT}/cfg", exist_ok=True)
jobs, manifest = [], {"source": SRC, "groups": groups, "model": MODEL, "configs": {}}
for g, ids in sorted(groups.items()):          # groups outer: a partial run stays balanced
    for r in REQS:
        for arm, rung in CELLS:
            c = json.loads(json.dumps(template))
            c["model"] = dict(MODEL)
            c["benchmark"]["policy"] = f"{rung}_ID_{r}" if arm == "TOLD" else rung
            c["benchmark"]["requester"] = r
            c["benchmark"]["gradingMode"] = "category"
            c["benchmark"]["tasks"] = {"kind": "all", "ids": ids}
            rid = f"T3-{arm}-{rung}-{r}-{g}"
            src = json.dumps(c, indent=1) + "\n"
            open(f"{OUT}/cfg/{rid}.json", "w").write(src)
            manifest["configs"][rid] = hashlib.sha256(src.encode()).hexdigest()[:16]
            jobs.append(rid)
open(f"{OUT}/jobs.txt", "w").write("".join(f"{j}\n" for j in jobs))
open(f"{OUT}/pilot.txt", "w").write("".join(f"{j}\n" for j in jobs if j.rsplit("-", 1)[1] in PILOT_GROUPS))
json.dump(manifest, open(f"{OUT}/MANIFEST.json", "w"), indent=1)
print(len(jobs), "configs;", sum(1 for j in jobs if j.rsplit("-", 1)[1] in PILOT_GROUPS), "in the pilot")
