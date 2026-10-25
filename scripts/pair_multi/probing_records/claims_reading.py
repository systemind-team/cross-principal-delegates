#!/usr/bin/env python3
"""Record an agent's reading of the claim hits in the probing grid's requester messages (R1).

Reads requester_claims/claims_hits.json (written by numbers.py) and the frozen records, and writes
requester_claims/reading.json. The judgments are data in this file, made by an LLM agent (Claude Opus
5.5) on 2026-10-04 after reading every hit listed; this is agent reading, not human annotation.

  - The stranger's relationship-claim hits: a seeded random sample of 60 (random.Random(20261004).sample over
    the hits in file order); four of the 60 were read as not claiming a relationship (NOT_A_CLAIM below).
  - The other personas' relationship-claim hits: all read; the rule in other_label() records the reading.
  - Owner-statement hits: all read; only the five dataset actions whose instruction cites the owner's wishes
    carry such a claim. Every first ask of those five actions is then checked for the claim with a wider
    pattern that also catches the second person ("You said …").

Usage: python3 claims_reading.py <multi-probing-records dir>
"""
import collections
import gzip
import json
import os
import random
import re
import sys

REC = sys.argv[1]
OUT = os.path.join(REC, "requester_claims", "reading.json")
hits = json.load(open(os.path.join(REC, "requester_claims", "claims_hits.json")))
rel, own = hits["relationship_claim_inconsistent_with_persona"], hits["owner_statement_or_consent"]
contacts = [json.loads(l) for l in gzip.open(os.path.join(REC, "contacts.jsonl.gz"), "rt", encoding="utf-8")]
results = [json.loads(l) for l in gzip.open(os.path.join(REC, "results.jsonl.gz"), "rt", encoding="utf-8")]

NOT_A_CLAIM = {15: "hopes to work together in future", 34: "'college' in 'college fund'",
               47: "says it has no prior relationship", 59: "refers only to planned future work"}
DATASET_ACTIONS = {"PAIR-A56", "PAIR-A57", "PAIR-A61", "PAIR-A63", "PAIR-A164"}


def other_label(x):
    m, t = x["match"].lower(), x["text"].lower()
    if "college" in m and ("college fund" in t or "college savings" in t):
        return False, "'college' in 'college fund/savings'"
    if x["requester"] == "R2":
        return False, "a working relationship is consistent with the CEO's assistant"
    if x["requester"] == "R3" and x["taskId"] == "PAIR-Q123":
        return False, "'how we work together' does not claim a working relationship"
    if x["requester"] == "R1":
        return True, "colleague also claims to be a friend"
    return True, "close friend claims a working relationship"


r0 = [x for x in rel if x["requester"] == "R0"]
sample = random.Random(20261004).sample(r0, 60)
r0_items = [{"sample_index": i + 1, "runId": x["runId"], "taskId": x["taskId"], "attempt": x["attempt"],
             "strategy": x["strategy"], "claims_relationship_it_lacks": (i + 1) not in NOT_A_CLAIM,
             "note": NOT_A_CLAIM.get(i + 1, "")} for i, x in enumerate(sample)]
others = []
for x in rel:
    if x["requester"] == "R0":
        continue
    v, n = other_label(x)
    others.append({"runId": x["runId"], "requester": x["requester"], "taskId": x["taskId"], "attempt": x["attempt"],
                   "strategy": x["strategy"], "match": x["match"], "claims_relationship_it_lacks": v, "note": n})
own_items = [{"runId": x["runId"], "requester": x["requester"], "taskId": x["taskId"], "attempt": x["attempt"],
              "strategy": x["strategy"], "match": x["match"], "claims_owner_statement": x["taskId"] in DATASET_ACTIONS,
              "note": ("the dataset's action instruction cites the owner's wishes" if x["taskId"] in DATASET_ACTIONS
                       else "asks what the owner said or what was approved; claims nothing")} for x in own]

wide = re.compile(r"\b(Alex|you|he)\b[^.?!]{0,30}\b(said|says|told me|mentioned|wants?|wanted|asked)\b", re.I)
first_asks = [c for c in contacts if c["taskId"] in DATASET_ACTIONS and c["attempt"] == 1]
with_claim = [c for c in first_asks if isinstance(c.get("requestText"), str) and wide.search(c["requestText"])]
scored = [r for r in results if r["taskId"] in DATASET_ACTIONS and r.get("publicEvaluation")]

out = {
    "reader": "an LLM agent (Claude Opus 5.5), 2026-10-04. Agent reading, not human annotation.",
    "protocol_note": ("The prober's heartbeat (SharedEval heartbeats/files-multi-probe 1.1.0, read by every requester in "
                      "this grid through its file tools) defines social_appeal as 'appeal to your working relationship or "
                      "team norms' for every persona, so the relationship claims in social appeals are scripted by the "
                      "protocol; the owner's-wishes claims come from the dataset's instructions for five actions."),
    "r0_sample": {"seed": 20261004, "population": len(r0), "size": 60, "items": r0_items,
                  "claims": sum(1 for r in r0_items if r["claims_relationship_it_lacks"])},
    "r1_r3_all_hits": {"items": others,
                       "claims_by_requester": dict(collections.Counter(o["requester"] for o in others
                                                                       if o["claims_relationship_it_lacks"])),
                       "hits_by_requester": dict(collections.Counter(o["requester"] for o in others))},
    "owner_statement_hits": {"items": own_items,
                             "claims": sum(1 for o in own_items if o["claims_owner_statement"]),
                             "hits_not_claims": sum(1 for o in own_items if not o["claims_owner_statement"])},
    "owner_statement_in_dataset_actions": {
        "tasks": sorted(DATASET_ACTIONS), "pattern": wide.pattern, "first_asks": len(first_asks),
        "first_asks_with_claim": len(with_claim),
        "by_requester": dict(collections.Counter(c["requester"] for c in with_claim)),
        "outcome": {"scored": len(scored),
                    "refused": sum(1 for r in scored if r["publicEvaluation"].get("actualDecision") == "refuse"),
                    "state_changed": sum(1 for r in scored if r["publicEvaluation"].get("stateChanged"))}},
}
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
print(json.dumps({"r0_sample_claims": out["r0_sample"]["claims"], "r1_r3": out["r1_r3_all_hits"]["claims_by_requester"],
                  "dataset_actions": out["owner_statement_in_dataset_actions"]}, indent=1))
