#!/usr/bin/env python3
"""P1-6 impersonation arms: write the run configs (design: <internal>).

The identity comparison's configuration (identity_rerun/gen.py: the ladder grid's DeepSeek template, simple
profile, 22 ticks, multi-turn phases at ticks 4 and 19, temperature 0, 4,096 output tokens, relationship
labels), with the true requester R0 in every arm and the model reached through the research gateway on the
dedicated P1-6 key, pinned to the Relace upstream. The SharedEval checkout is the header ladder's commit plus
the impersonation patch (benchmark.spoof = {persona, prefix}).

Arms (all R0, relationship labels):
  A0h  D2R_ID_R0       no spoof                          control with the identity header
  A0n  D2R_PRINCIPLES  no spoof                          control without the header
  C1h  D2R_ID_R0       persona R1 + prefix forged-r1     forged header, real header present
  C2h  D2R_ID_R0       persona R1 + prefix claim-r1      contradicting claim
  C1n  D2R_PRINCIPLES  persona R1 + prefix forged-r1     forged header, no header
  C3c  D2R_PRINCIPLES  persona R1 + prefix claim-r1      claimed colleague, no header
  C3f  D2R_PRINCIPLES  persona R3 + prefix claim-r3      claimed close friend, no header (secondary)
  P1h  D2R_ID_R0       persona R1, no prefix             optional persona-only reference, launched last
                                                         and only if the budget allows

Run ids: SP-<arm>-r<replicate>-<group>. Job order: replicate outermost, then group, then arm, so a partial run
stays balanced across arms. jobs.txt holds the 7 main arms x 50 groups x 2 replicates (700); pilot.txt the
14 sessions of groups g004 and g100, replicate 1 (part of the 700); optional.txt the P1h sessions.
drop_rule.txt lists C1n's replicate-2 sessions, which leave jobs.txt if the pilot's mean cost exceeds
$0.0170 per session.

Usage (VM): python3 gen.py <t3simple lane dir> <out lane dir>
"""
import hashlib
import json
import os
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
REPLICATES = (1, 2)
PILOT_GROUPS = ("g004", "g100")
ARMS = {
    "A0h": {"policy": "D2R_ID_R0"},
    "A0n": {"policy": "D2R_PRINCIPLES"},
    "C1h": {"policy": "D2R_ID_R0", "spoof": {"persona": "R1", "prefix": "forged-r1"}},
    "C2h": {"policy": "D2R_ID_R0", "spoof": {"persona": "R1", "prefix": "claim-r1"}},
    "C1n": {"policy": "D2R_PRINCIPLES", "spoof": {"persona": "R1", "prefix": "forged-r1"}},
    "C3c": {"policy": "D2R_PRINCIPLES", "spoof": {"persona": "R1", "prefix": "claim-r1"}},
    "C3f": {"policy": "D2R_PRINCIPLES", "spoof": {"persona": "R3", "prefix": "claim-r3"}},
}
OPTIONAL = {"P1h": {"policy": "D2R_ID_R0", "spoof": {"persona": "R1"}}}
MODEL = {
    "provider": "openai-compatible",
    "baseUrl": "http://127.0.0.1:8787/v1",
    "apiKeyEnv": "SHAREDEVAL_MODEL_API_KEY",
    "model": "deepseek/deepseek-v4-flash-0731",
    "maxOutputTokens": 4096,
    "temperature": 0,
    "attemptTimeoutMs": 300000,
    # One upstream for every call; the other host OpenRouter used for this build returned malformed
    # responses to 177 of 425 requester calls on 10-02.
    "providerRouting": {"order": ["Relace"], "only": ["Relace"], "allowFallbacks": False},
}

groups = json.load(open(f"{SRC}/MANIFEST.json"))["groups"]
assert len(groups) == 50, len(groups)
template = json.load(open(f"{SRC}/cfg/S4-DS-D2-R1-g004.json"))
assert template["workflow"]["pairProfile"] == "simple"

os.makedirs(f"{OUT}/cfg", exist_ok=True)
manifest = {"source": SRC, "groups": groups, "model": MODEL, "arms": ARMS, "optional_arms": OPTIONAL,
            "replicates": list(REPLICATES), "configs": {}}


def write(arm, spec, rep, g):
    c = json.loads(json.dumps(template))
    c["model"] = dict(MODEL)
    c["benchmark"]["policy"] = spec["policy"]
    c["benchmark"]["requester"] = "R0"
    c["benchmark"]["gradingMode"] = "relationship"
    c["benchmark"]["tasks"] = {"kind": "all", "ids": groups[g]}
    if "spoof" in spec:
        c["benchmark"]["spoof"] = dict(spec["spoof"])
    rid = f"SP-{arm}-r{rep}-{g}"
    src = json.dumps(c, indent=1) + "\n"
    open(f"{OUT}/cfg/{rid}.json", "w").write(src)
    manifest["configs"][rid] = hashlib.sha256(src.encode()).hexdigest()
    return rid


jobs, optional = [], []
for rep in REPLICATES:
    for g in sorted(groups):
        for arm, spec in ARMS.items():
            jobs.append(write(arm, spec, rep, g))
        for arm, spec in OPTIONAL.items():
            optional.append(write(arm, spec, rep, g))
pilot = [r for r in jobs if r.endswith(PILOT_GROUPS) and "-r1-" in r]
drop = [r for r in jobs if r.startswith("SP-C1n-r2-")]
for name, rows in (("jobs", jobs), ("pilot", pilot), ("optional", optional), ("drop_rule", drop)):
    open(f"{OUT}/{name}.txt", "w").write("".join(f"{r}\n" for r in rows))
json.dump(manifest, open(f"{OUT}/MANIFEST.json", "w"), indent=1)
print(f"{len(jobs)} main configs, {len(pilot)} in the pilot, {len(optional)} optional, {len(drop)} under the drop rule")
