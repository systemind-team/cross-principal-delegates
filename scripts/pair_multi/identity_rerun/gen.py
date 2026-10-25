#!/usr/bin/env python3
"""PAIR II with the requester's identity: writes the run configs.

Two arms on the ladder's 50 groups and four requesters, one run per cell:
  ID  benchmark.policy = D2R_ID_<R>    a runtime-verified head names the requester, then the
                                       principles body (the head is the only difference);
  PR  benchmark.policy = D2R_PRINCIPLES the same body with nothing telling the responder who asks.
Both arms are graded against the relationship labels (v2), as PAIR I is.

Everything else is the ladder's DeepSeek configuration (t3simple, SharedEval 8081e7e): simple
profile, 22 ticks, multi-turn phases at ticks 4 and 19, temperature 0, 4,096 output tokens. The
model is DeepSeek V4 Flash 0731, the ladder's build, reached through the budget-capped gateway
and pinned to one OpenRouter upstream.

Usage (VM):  python3 gen.py <t3simple dir> <out dir>
Writes <out>/cfg/I2-<ARM>-<R>-<g>.json, jobs.txt, pilot.txt and MANIFEST.json.
"""
import hashlib
import json
import os
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
ARMS = ("ID", "PR")
REQS = ("R0", "R1", "R2", "R3")
PILOT_GROUPS = ("g004", "g100")
MODEL = {
    "provider": "openai-compatible",
    "baseUrl": "http://127.0.0.1:8787/v1",
    "apiKeyEnv": "SHAREDEVAL_MODEL_API_KEY",
    "model": "deepseek/deepseek-v4-flash-0731",
    "maxOutputTokens": 4096,
    "temperature": 0,
    "attemptTimeoutMs": 300000,
    # One upstream for every call. Unpinned, OpenRouter split this build between two hosts, one of
    # which returned malformed responses to 40% of requester calls (the first launch, stopped).
    "providerRouting": {"order": ["Relace"], "only": ["Relace"], "allowFallbacks": False},
}

groups = json.load(open(f"{SRC}/MANIFEST.json"))["groups"]
assert len(groups) == 50, len(groups)
template = json.load(open(f"{SRC}/cfg/S4-DS-D2-R1-g004.json"))
assert template["workflow"]["pairProfile"] == "simple"

os.makedirs(f"{OUT}/cfg", exist_ok=True)
jobs, manifest = [], {"source": SRC, "groups": groups, "model": MODEL, "configs": {}}
# groups outer, cells inner: a partial run stays balanced across arms and requesters
for g, ids in sorted(groups.items()):
    for r in REQS:
        for arm in ARMS:
            c = json.loads(json.dumps(template))
            c["model"] = dict(MODEL)
            c["benchmark"]["policy"] = f"D2R_ID_{r}" if arm == "ID" else "D2R_PRINCIPLES"
            c["benchmark"]["requester"] = r
            c["benchmark"]["gradingMode"] = "relationship"
            c["benchmark"]["tasks"] = {"kind": "all", "ids": ids}
            rid = f"I2-{arm}-{r}-{g}"
            src = json.dumps(c, indent=1) + "\n"
            open(f"{OUT}/cfg/{rid}.json", "w").write(src)
            manifest["configs"][rid] = hashlib.sha256(src.encode()).hexdigest()[:16]
            jobs.append(rid)
open(f"{OUT}/jobs.txt", "w").write("".join(f"{rid}\n" for rid in jobs))
open(f"{OUT}/pilot.txt", "w").write(
    "".join(f"{rid}\n" for rid in jobs if rid.rsplit("-", 1)[1] in PILOT_GROUPS))
json.dump(manifest, open(f"{OUT}/MANIFEST.json", "w"), indent=1)
print(len(jobs), "configs;", sum(1 for j in jobs if j.rsplit("-", 1)[1] in PILOT_GROUPS), "in the pilot")
