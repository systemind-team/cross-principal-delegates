#!/usr/bin/env python3
"""Aggregate AI review verdicts over the stratified sample; select the human-review subset.
Reads out/review/packets.jsonl + out/review/ai_chunk*.jsonl; writes out/review/ai_verdicts.jsonl,
out/review/summary.json and out/review/human_subset.jsonl (seeded)."""
import json, glob, os, collections, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); REV = os.path.join(ROOT, "out", "review")
packets = {p["id"]: p for p in (json.loads(l) for l in open(os.path.join(REV, "packets.jsonl")))}
verdicts = {}
for f in sorted(glob.glob(os.path.join(REV, "ai_chunk*.jsonl"))):
    for l in open(f):
        l = l.strip()
        if not l: continue
        v = json.loads(l); verdicts[v["id"]] = v
missing = [i for i in packets if i not in verdicts]
print(f"packets {len(packets)} verdicts {len(verdicts)} missing {len(missing)}")
with open(os.path.join(REV, "ai_verdicts.jsonl"), "w") as f:
    for i in packets:
        if i in verdicts: f.write(json.dumps(verdicts[i]) + "\n")
S = collections.defaultdict(lambda: collections.Counter())
by_model = collections.defaultdict(lambda: collections.Counter())
for i, v in verdicts.items():
    p = packets[i]; st = p["stratum"]; m = p["responder_model"]
    S[st]["n"] += 1; by_model[(st, m)]["n"] += 1
    if v["matcher_verdict_correct"] is False:
        S[st]["matcher_wrong"] += 1; by_model[(st, m)]["matcher_wrong"] += 1
    S[st][f"err:{v['error_type']}"] += 1
    S[st][f"util:{v['utility_semantic']}"] += 1; by_model[(st, m)][f"util:{v['utility_semantic']}"] += 1
    S[st][f"leak:{v['leak_semantic']}"] += 1; by_model[(st, m)][f"leak:{v['leak_semantic']}"] += 1
    S[st][f"dec:{v['decision_read']}"] += 1
    S[st][f"ref:{v['refusal_reason_type']}"] += 1; by_model[(st, m)][f"ref:{v['refusal_reason_type']}"] += 1
    S[st][f"act:{v['action_assessment']}"] += 1; by_model[(st, m)][f"act:{v['action_assessment']}"] += 1
    S[st][f"conf:{v['confidence']}"] += 1
    # label-based count, independent of the reviewer: the category contract answers this item for everyone
    if p.get("category") == "work_public" and p.get("category_expected") == "answer":
        S[st]["label_public"] += 1; by_model[(st, m)]["label_public"] += 1
summary = {st: dict(c) for st, c in S.items()}
summary["by_model"] = {f"{st}|{m}": dict(c) for (st, m), c in by_model.items()}
json.dump(summary, open(os.path.join(REV, "summary.json"), "w"), indent=1)
for st in sorted(S):
    c = S[st]; print(f"\n{st}: n={c['n']} matcher_wrong={c['matcher_wrong']}")
    for k, v in sorted(c.items()):
        if k.startswith(("err:", "util:", "leak:", "ref:", "act:", "dec:")) and v: print(f"   {k:32s} {v}")
print("\nper model (S1 leak reading / S2 refusal reasons / S3 utility / S6 actions / S8):")
for (st, m), c in sorted(by_model.items()):
    if st in ("S1_explicit_leak", "S2_d2_false_refusal", "S3_luna_iu_incorrect", "S6_r2_action_safety_fail", "S8_leak_in_refusal", "S4_d1_r3_refusal"):
        keys = [k for k in c if k.startswith(("leak:", "ref:", "util:", "act:")) and c[k]]
        print(f"   {st:26s} {m:9s} n={c['n']:3d} wrong={c['matcher_wrong']:3d} " + " ".join(f"{k}={c[k]}" for k in sorted(keys)))
# human subset: disagreements in the headline strata + calibration agreements
rng = random.Random(20260925)
def ids(pred): return [i for i, v in verdicts.items() if pred(packets[i], v)]
sel = []
sel += rng.sample(ids(lambda p, v: p["stratum"] == "S1_explicit_leak" and v["matcher_verdict_correct"] is False), k=min(10, len(ids(lambda p, v: p["stratum"] == "S1_explicit_leak" and v["matcher_verdict_correct"] is False))))
sel += rng.sample(ids(lambda p, v: p["stratum"] == "S8_leak_in_refusal" and v["leak_semantic"] == "disclosed"), k=min(10, len(ids(lambda p, v: p["stratum"] == "S8_leak_in_refusal" and v["leak_semantic"] == "disclosed"))))
sel += rng.sample(ids(lambda p, v: p["stratum"] == "S3_luna_iu_incorrect" and v["utility_semantic"] == "correct"), k=min(8, len(ids(lambda p, v: p["stratum"] == "S3_luna_iu_incorrect" and v["utility_semantic"] == "correct"))))
sel += rng.sample(ids(lambda p, v: p["stratum"] == "S2_d2_false_refusal" and v["refusal_reason_type"] == "gold_tension"), k=min(6, len(ids(lambda p, v: p["stratum"] == "S2_d2_false_refusal" and v["refusal_reason_type"] == "gold_tension"))))
sel += rng.sample(ids(lambda p, v: p["stratum"] == "S2_d2_false_refusal" and v["refusal_reason_type"] == "policy_conservatism"), k=min(4, len(ids(lambda p, v: p["stratum"] == "S2_d2_false_refusal" and v["refusal_reason_type"] == "policy_conservatism"))))
sel += rng.sample(ids(lambda p, v: p["stratum"] == "S6_r2_action_safety_fail" and v["action_assessment"] == "unauthorized_change_confirmed"), k=min(4, len(ids(lambda p, v: p["stratum"] == "S6_r2_action_safety_fail" and v["action_assessment"] == "unauthorized_change_confirmed"))))
# calibration: agreements (matcher correct) across S1/S3/S8/S7
sel += rng.sample(ids(lambda p, v: p["stratum"] in ("S1_explicit_leak", "S3_luna_iu_incorrect", "S8_leak_in_refusal", "S7_control_correct") and v["matcher_verdict_correct"] is True and p["id"] not in sel), k=12)
seen = set(); sel = [i for i in sel if not (i in seen or seen.add(i))]
with open(os.path.join(REV, "human_subset.jsonl"), "w") as f:
    for i in sel: f.write(json.dumps(dict(packet=packets[i], ai=verdicts[i])) + "\n")
print(f"\nhuman subset: {len(sel)} traces", collections.Counter(packets[i]["stratum"] for i in sel))
