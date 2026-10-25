#!/usr/bin/env python3
"""t3simple: Table 3 grid under the simple PACT-Pair profile.

Same 50 groups, same task ids, same model blocks and workflow as t3full; only
workflow.pairProfile changes (strict -> simple), plus model.toolRootCombinators
= 'drop' for Grok (xAI rejects edit_todo's root anyOf; SharedEval 8081e7e).
DeepSeek and GLM requests stay byte-identical to what 26dd392 would send.
Writes cfg/S4-<B>-<P>-<R>-<g>.json, jobs-<B>.txt, pilot-<B>.txt, MANIFEST.json.
"""
import json, glob, os, re, hashlib, collections
SRC = "<vm>/runs/t3full/cfg"
L = "<vm>/runs/t3simple"
BUILDS, POLS, REQS = ("DS", "GLM", "GROK"), ("D0", "D1", "D2"), ("R1", "R2", "R3")
PILOT_GROUPS = ("g004", "g100")

# group -> task ids, taken from every t3full config and required to agree
groups = collections.defaultdict(set)
for f in glob.glob(f"{SRC}/T3-*.json"):
    m = re.match(r"T3-(DS|GLM|GROK)-(D\d)-(R\d)-(g\d+)\.json$", os.path.basename(f))
    if not m:
        continue
    groups[m.group(4)].add(tuple(json.load(open(f))["benchmark"]["tasks"]["ids"]))
assert len(groups) == 50, len(groups)
assert all(len(v) == 1 for v in groups.values()), "a group has two task lists"
groups = {g: list(next(iter(v))) for g, v in sorted(groups.items())}

templates = {b: json.load(open(f"{SRC}/T3-{b}-D2-R3-g004.json")) for b in BUILDS}
for b, t in templates.items():
    assert t["workflow"]["pairProfile"] == "strict", b

os.makedirs(f"{L}/cfg", exist_ok=True)
jobs = {b: [] for b in BUILDS}
manifest = {"source": SRC, "groups": groups, "configs": {}}
# groups outer, cells inner: a partial grid is balanced across cells
for g, ids in groups.items():
    for b in BUILDS:
        for r in REQS:
            for p in POLS:
                c = json.loads(json.dumps(templates[b]))
                c["benchmark"]["policy"] = p
                c["benchmark"]["requester"] = r
                c["benchmark"]["tasks"]["ids"] = ids
                c["workflow"]["pairProfile"] = "simple"
                if b == "GROK":
                    c["model"]["toolRootCombinators"] = "drop"
                rid = f"S4-{b}-{p}-{r}-{g}"
                src = json.dumps(c, indent=1) + "\n"
                open(f"{L}/cfg/{rid}.json", "w").write(src)
                manifest["configs"][rid] = hashlib.sha256(src.encode()).hexdigest()[:16]
                jobs[b].append(rid)
for b in BUILDS:
    open(f"{L}/jobs-{b}.txt", "w").write("".join(f"{rid} 1\n" for rid in jobs[b]))
    open(f"{L}/pilot-{b}.txt", "w").write("".join(f"{rid} 1\n" for rid in jobs[b] if rid.rsplit("-", 1)[1] in PILOT_GROUPS))
json.dump(manifest, open(f"{L}/MANIFEST.json", "w"), indent=1)
print({b: len(v) for b, v in jobs.items()}, "pilot", {b: sum(1 for r in v if r.rsplit('-', 1)[1] in PILOT_GROUPS) for b, v in jobs.items()})
print(json.dumps(templates["GLM"]["model"]), json.dumps(templates["DS"]["model"]))
