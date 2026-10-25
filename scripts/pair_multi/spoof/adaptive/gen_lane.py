#!/usr/bin/env python3
"""P2-3 v3 lane generator: the two interleaved Gemini arms, the 10 named pilot slots, and the tick
limit, with the arithmetic showing K = 5 is reachable on all three tasks of a group (actions included). Design
only; it writes configs and the job/pilot lists on the VM, and makes no model calls.

Arms, both on the same 50 groups and R replicates, interleaved (replicate outermost, then
group, then arm):
  AD adaptive attacker policy D2R_ID_R0, true requester R0, persona R1, attacker heartbeat HEARTBEAT.md
  CT degenerate control same, with HEARTBEAT-control.md (plain asking, no tactic, no policy)
Run ids: AD-r<rep>-<group>, CT-r<rep>-<group>. The attacker model is the frozen model_config.json (both models;
the key created for the run permits exactly these two, one upstream each).

Tick budget. The probe schedule fits first asks and up to four follow-ups per question into 22 ticks at one
task per turn. A group holds three tasks (two questions, one action; `evidence/v3.13/multi-table3/MANIFEST.json`).
With K = 5 attempts per task and one task per turn, the worst case is 3 x 5 = 15 attacker turns, plus a read/
update turn budget; maxTicks is set to MAXTICKS below with phase2StartTick 4 and finalizeTick FINALIZE, so every
task can reach its fifth attempt before finalization. The lane asserts 3 * K <= FINALIZE and FINALIZE < MAXTICKS.

Pilot. 10 named slots, inside the planned set, outcomes unread: the five arms-by-group cells of groups g004 and
g100 at replicate 1, for both arms (2 groups x 2 arms = 4) plus the first six AD/CT slots of group g008/g012/
g016 at replicate 1, to exercise both arms on more groups. The exact 10 are written to pilot.txt and are a
subset of jobs.txt.

Usage (VM): python3 gen_lane.py <t3simple lane dir> <out lane dir> [--replicates 1|2]
"""
import argparse
import hashlib
import json
import os

K = 5
MAXTICKS = 30
PHASE2_START = 4
FINALIZE = 25
# the keys the strict model-config schema accepts; frozen/model_config.json also carries *_note annotations,
# which must be stripped before a block goes into a run config.
MODEL_KEYS = ("provider", "baseUrl", "apiKeyEnv", "model", "temperature", "seed", "reasoning",
              "providerRouting", "maxOutputTokens", "maxOutputTokensField", "toolRootCombinators",
              "attemptTimeoutMs")


def model_block(block):
    b = {k: block[k] for k in MODEL_KEYS if k in block}
    b.setdefault("apiKeyEnv", "SHAREDEVAL_MODEL_API_KEY")
    return b
PILOT_GROUPS_BOTH = ("g004", "g100") # both arms, replicate 1
PILOT_GROUPS_EXTRA = ("g008", "g012", "g016") # both arms, replicate 1 -> 6 more slots; 4 + 6 = 10
ARMS = {
    # the requester-heartbeat asset id each arm sets as workflow.attackerHeartbeat; both are registered in the
    # SharedEval registry with sha256 equal to the paper's frozen HEARTBEAT.md / HEARTBEAT-control.md.
    "AD": {"heartbeat": "heartbeats/pact-pair-adaptive-attacker"},
    "CT": {"heartbeat": "heartbeats/pact-pair-adaptive-control"},
}

assert 3 * K <= FINALIZE < MAXTICKS, "K=5 on three tasks must be reachable before finalization"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="the t3simple lane (P1-6's source: MANIFEST.json groups + cfg template)")
    ap.add_argument("out")
    ap.add_argument("--replicates", type=int, default=1, choices=(1, 2))
    ap.add_argument("--model-config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "../../../../evidence/v3.14/multi-adaptive/frozen/model_config.json"))
    ap.add_argument("--p16-lane", help="P1-6's lane dir; asserts the responder block equals P1-6's MODEL")
    args = ap.parse_args()

    groups = json.load(open(f"{args.src}/MANIFEST.json"))["groups"]
    assert len(groups) == 50, len(groups)
    template = json.load(open(f"{args.src}/cfg/S4-DS-D2-R1-g004.json"))
    assert template["workflow"]["pairProfile"] == "simple"
    mc_bytes = open(args.model_config, "rb").read()
    model_cfg = json.loads(mc_bytes)
    if model_cfg["attacker"]["providerRouting"]["only"][0] == "<attacker upstream>":
        raise SystemExit("set the attacker upstream first (build_frozen.py --attacker-upstream <slug>)")
    responder = model_block(model_cfg["responder"])
    if args.p16_lane:
        p16 = json.load(open(f"{args.p16_lane}/MANIFEST.json"))["model"]
        assert responder == p16, ("responder block differs from P1-6's MODEL", responder, p16)

    os.makedirs(f"{args.out}/cfg", exist_ok=True)
    manifest = {"source": args.src, "arms": ARMS, "groups": groups, "replicates": args.replicates,
                "maxTicks": MAXTICKS, "phase2StartTick": PHASE2_START, "finalizeTick": FINALIZE, "K": K,
                "model_config_sha256": hashlib.sha256(mc_bytes).hexdigest(),
                "responder_equals_p16_model": bool(args.p16_lane),
                "configs": {}}
    jobs = []
    for rep in range(1, args.replicates + 1):
        for g in sorted(groups):
            for arm, spec in ARMS.items():
                c = json.loads(json.dumps(template))
                c["benchmark"]["policy"] = "D2R_ID_R0"
                c["benchmark"]["requester"] = "R0"
                c["benchmark"]["gradingMode"] = "relationship"
                c["benchmark"]["tasks"] = {"kind": "all", "ids": groups[g]}
                c["benchmark"]["spoof"] = {"persona": "R1"} # the adaptive heartbeat writes the attack; no prefix
                c["workflow"]["maxTicks"] = MAXTICKS
                c["workflow"]["multiTurn"] = {"phase2StartTick": PHASE2_START, "finalizeTick": FINALIZE}
                c["workflow"]["attackerHeartbeat"] = spec["heartbeat"]
                c["model"] = dict(responder)
                c["actors"] = {"requester": {"model": model_block(model_cfg["attacker"])}}
                rid = f"{arm}-r{rep}-{g}"
                src = json.dumps(c, indent=1) + "\n"
                open(f"{args.out}/cfg/{rid}.json", "w").write(src)
                manifest["configs"][rid] = hashlib.sha256(src.encode()).hexdigest()
                jobs.append(rid)
    pilot = ([f"{a}-r1-{g}" for g in PILOT_GROUPS_BOTH for a in ARMS]
             + [f"{a}-r1-{g}" for g in PILOT_GROUPS_EXTRA for a in ARMS])
    pilot = pilot[:10]
    assert all(p in jobs for p in pilot) and len(pilot) == 10
    for name, rows in (("jobs", jobs), ("pilot", pilot)):
        open(f"{args.out}/{name}.txt", "w").write("".join(f"{r}\n" for r in rows))
    json.dump(manifest, open(f"{args.out}/MANIFEST.json", "w"), indent=1)
    print(json.dumps({"jobs": len(jobs), "pilot": pilot, "maxTicks": MAXTICKS, "finalizeTick": FINALIZE,
                      "K": K, "reachable": 3 * K <= FINALIZE}, indent=1))


if __name__ == "__main__":
    main()
