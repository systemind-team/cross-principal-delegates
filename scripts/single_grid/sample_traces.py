#!/usr/bin/env python3
"""Stratified trace sample for AI + human review. Deterministic (seed 20260924).
Reads out/tasks.jsonl and the benchmark dataset; writes out/review/packets.jsonl (+ 4 chunk files)."""
import json, lzma, os, random, collections, csv
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # paper repo root
OUT = os.path.join(ROOT, "evidence", "v3.13", "single-grid"); REV = os.path.join(OUT, "review"); os.makedirs(REV, exist_ok=True)
DS = "<external>/pact-pair"
SEED = 20260924
bench = json.load(open(os.path.join(DS, "tasks", "questions.json")))
labels = json.load(open(os.path.join(DS, "relationship_labels", "relationship_label_matrix_v2.json")))
Q = {f"PAIR-Q{q['id']}": q for q in bench["questions"]}
A = {f"PAIR-A{a['id']}": a for a in bench["actions"]}
REQ = labels["requesters"]
POLICY_NOTE = {
    "D0": "no privacy policy (verified-caller identity header only)",
    "D1": "22-word generic caution ('be careful with personal information'), identity header",
    "D2": "relationship-aware principles: place the verified requester in the owner's life, share only what that place entitles; action rules (298 words)",
    "D3": "D2 body + spotlighting paragraph (external messages are data, not instructions)",
    "D4": "D2 body + instruction-hierarchy paragraph",
    "D5": "D2 body + sandwich/boundary paragraph (classify the request before responding)",
    "D6": "length-matched generic control: 298 words restating the generic caution, no categories, no rules",
}
_src = os.path.join(OUT, "tasks.jsonl")   # absent from the repository: read the frozen, byte-identical merge
rows = [json.loads(l) for l in (open(_src) if os.path.exists(_src) else
        lzma.open(os.path.join(ROOT, "evidence", "v3.14", "single-grid-tasks", "tasks.jsonl.xz"), "rt"))]
def scored(r): return r["status"] in ("answered","refused","side_effect_before_failure") or r.get("recovery") is not None
rows = [r for r in rows if scored(r)]
by = collections.defaultdict(list)
for r in rows: by[(r["family"], r["policy"], r["requester"])].append(r)
rng = random.Random(SEED)
FAMS = ["ds41", "glm", "luna"]

def pick(pool, n): pool = list(pool); rng.shuffle(pool); return pool[:n]
strata = []
# 1. leaks under the explicit family (D2-D5), protected QA
for fam in FAMS:
    pool = [r for r in rows if r["family"]==fam and r["policy"] in ("D2","D3","D4","D5") and r["kind"]=="qa"
            and r["relationshipExpectedBehavior"]=="refuse" and r.get("relationshipLeaked")]
    strata += [("S1_explicit_leak", r) for r in pick(pool, 30)]
# 2. false refusals under D2 for R2/R3 (entitled QA refused)
for fam in FAMS:
    pool = [r for r in rows if r["family"]==fam and r["policy"]=="D2" and r["requester"] in ("R2","R3") and r["kind"]=="qa"
            and r["relationshipExpectedBehavior"]=="answer" and r["actualDecision"]=="refuse"]
    strata += [("S2_d2_false_refusal", r) for r in pick(pool, 30)]
# 3. luna answered-but-incorrect entitled QA (lexical matcher suspicion)
pool = [r for r in rows if r["family"]=="luna" and r["kind"]=="qa" and r["relationshipExpectedBehavior"]=="answer"
        and r["actualDecision"]=="answer" and not r.get("factMatch")]
strata += [("S3_luna_iu_incorrect", r) for r in pick(pool, 60)]
# 4. D1 x R3 refusals of entitled items
for fam in FAMS:
    pool = [r for r in rows if r["family"]==fam and r["policy"]=="D1" and r["requester"]=="R3" and r["kind"]=="qa"
            and r["relationshipExpectedBehavior"]=="answer" and r["actualDecision"]=="refuse"]
    strata += [("S4_d1_r3_refusal", r) for r in pick(pool, 20)]
# 5. D6 vs D1 pairs where the decision differs (same family, requester, task)
pairs = []
for fam in FAMS:
    for req in ("R1","R2","R3"):
        d1 = {r["taskId"]: r for r in by[(fam,"D1",req)] if r["kind"]=="qa"}
        d6 = {r["taskId"]: r for r in by[(fam,"D6",req)] if r["kind"]=="qa"}
        cand = [(d1[t], d6[t]) for t in d1 if t in d6 and (d1[t]["actualDecision"]!=d6[t]["actualDecision"] or bool(d1[t].get("relationshipLeaked"))!=bool(d6[t].get("relationshipLeaked")))]
        pairs += [(fam, req, a, b) for a, b in cand]
rng.shuffle(pairs)
for i, (fam, req, a, b) in enumerate(pairs[:40]):
    strata += [("S5_d6_vs_d1_pair", dict(a, pair_id=f"P{i:02d}", pair_role="D1")), ("S5_d6_vs_d1_pair", dict(b, pair_id=f"P{i:02d}", pair_role="D6"))]
# 6. action-safety failures under the explicit family for R2 (protected action, state changed)
for fam in FAMS:
    pool = [r for r in rows if r["family"]==fam and r["policy"] in ("D2","D3","D4","D5") and r["requester"]=="R2" and r["kind"]=="action"
            and r["relationshipExpectedBehavior"]=="refuse" and r.get("stateChanged")]
    strata += [("S6_r2_action_safety_fail", r) for r in pick(pool, 20)]
# 8. leak-in-refusal candidates: protected QA scored `refused` whose literal reply contains a gold fact per the matcher
diag = json.load(open(os.path.join(OUT, "diag_scan.json")))["hits"]
lir = {(h["cell"], h["taskId"]) for h in diag if h["kind"] == "leak_in_refusal" and h["expected"] == "refuse"}
for fam in ("ds41", "glm"):
    pool = [r for r in rows if r["family"]==fam and (r["cell"], r["taskId"]) in lir]
    strata += [("S8_leak_in_refusal", r) for r in pick(pool, 30)]
# 7. control: D2 entitled QA answered and matched (calibrates the reviewer)
for fam in FAMS:
    pool = [r for r in rows if r["family"]==fam and r["policy"]=="D2" and r["kind"]=="qa" and r["relationshipExpectedBehavior"]=="answer"
            and r["actualDecision"]=="answer" and r.get("factMatch")]
    strata += [("S7_control_correct", r) for r in pick(pool, 10)]

packets = []
for i, (stratum, r) in enumerate(strata):
    task = Q.get(r["taskId"]) or A.get(r["taskId"])
    p = dict(
        id=f"{stratum.split('_')[0]}-{i:03d}", stratum=stratum, cell=r["cell"], responder_model=r["responderShort"], requester_model=r["requesterShort"],
        harness=r["harness"], policy=r["policy"], policy_note=POLICY_NOTE[r["policy"]], requester=r["requester"], requester_identity=REQ[r["requester"]],
        task_id=r["taskId"], kind=r["kind"], category=r["taskCategory"],
        relationship_expected=r["relationshipExpectedBehavior"], category_expected=r["categoryExpectedBehavior"],
        request_text=r.get("requestText"), reply_text=r.get("replyText"),
        matcher=dict(status=r["status"], actualDecision=r["actualDecision"], factMatch=r.get("factMatch"), matchedFactCount=r.get("matchedFactCount"),
                     missedFactCount=r.get("missedFactCount"), relationshipLeaked=r.get("relationshipLeaked"), stateChanged=r.get("stateChanged"),
                     benchmarkStateCorrect=r.get("benchmarkStateCorrect"), recovered=r.get("recovery") is not None),
    )
    if r["kind"] == "qa":
        p.update(benchmark_question=task["question"], gold_key_facts=task["gold_key_facts"], minimum_correct=task["minimum_correct"], topic=task["topic"])
    else:
        p.update(benchmark_instruction=task["instruction"], operation=task["operation"], target_folder=task.get("target_folder"), target_item=task.get("target_item"),
                 gold_check=task.get("gold_check"), benchmark_expected_verdict=task.get("expected_verdict"))
    if "pair_id" in r: p.update(pair_id=r["pair_id"], pair_role=r["pair_role"])
    packets.append(p)
with open(os.path.join(REV, "packets.jsonl"), "w") as f:
    for p in packets: f.write(json.dumps(p) + "\n")
# chunks: keep pairs together (chunk by pair id), otherwise round robin
chunks = [[] for _ in range(4)]
for p in packets:
    key = p.get("pair_id") or p["id"]
    chunks[hash(key) % 4 if False else (int(key[1:]) % 4 if key.startswith("P") else int(p["id"].split("-")[1]) % 4)].append(p)
for i, ch in enumerate(chunks):
    with open(os.path.join(REV, f"packets_chunk{i}.jsonl"), "w") as f:
        for p in ch: f.write(json.dumps(p) + "\n")
cnt = collections.Counter((p["stratum"], p["responder_model"]) for p in packets)
print("packets", len(packets), "chunks", [len(c) for c in chunks])
for k, v in sorted(cnt.items()): print(f"  {k[0]:26s} {k[1]:9s} {v}")
print("pairs available", len(pairs))
