#!/usr/bin/env python3
"""The order in which the probing grid's prober applied its strategies, and when it used `repeat`.

Input: the frozen per-ask records, evidence/v3.14/multi-probing-records/contacts.jsonl.gz (pass another path as the
first argument). For every protected question instance
(run x task, category gold `refuse`), the follow-up requests (isRetry) in tick order and their claimed strategy.
Checks that the per-strategy counts reproduce Table 25 [29]'s Asks column (2,004 / 2,001 / 1,999 / 1,984 / 265).
Also: the instances whose follow-ups are exactly the four non-repeat strategies in their usual order
(business justification, urgency, social appeal, decomposition), those whose first four follow-ups are, and what came
fifth in the latter.
Output: evidence/v3.14/probing-strategy-order/order.json
"""
import collections
import gzip
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "evidence/v3.14/multi-probing-records/contacts.jsonl.gz"
seqs = collections.defaultdict(list)
for line in gzip.open(SRC, "rt"):
    r = json.loads(line)
    if r.get("kind") == "qa" and r.get("expectedBehavior") == "refuse":
        seqs[(r["runId"], r["taskId"])].append(r)
FOUR = ["business_justification", "urgency", "social_appeal", "decomposition"]
order, position = collections.Counter(), collections.defaultdict(collections.Counter)
began, after = 0, collections.Counter()       # instances whose first four follow-ups are FOUR in order
for rs in seqs.values():
    rs.sort(key=lambda r: (r.get("tick", 0), r.get("attempt", 0)))
    strat = [r.get("claimedStrategy") for r in rs if r.get("isRetry")]
    if strat:
        order[" > ".join(str(s) for s in strat)] += 1
    if strat[:4] == FOUR:
        began += 1
        after[str(strat[4]) if len(strat) > 4 else "nothing"] += 1
    for i, s in enumerate(strat):
        position[str(s)][i + 1] += 1
asks = {s: sum(c.values()) for s, c in position.items()}
want = {"business_justification": 2004, "urgency": 2001, "social_appeal": 1999, "decomposition": 1984, "repeat": 265}
assert all(asks[s] == n for s, n in want.items()), asks
reasked = sum(order.values())
out = {"source": "evidence/v3.14/multi-probing-records/contacts.jsonl.gz",
       "source_sha256": hashlib.sha256(SRC.read_bytes()).hexdigest(), "instances": len(seqs),
       "instances_reasked": reasked, "asks_by_strategy": asks,
       "position_by_strategy": {s: dict(sorted(c.items())) for s, c in position.items()},
       "most_common_sequences": order.most_common(10),
       "exactly_the_four_in_order": order[" > ".join(FOUR)], "began_with_the_four_in_order": began,
       "after_the_four": dict(after)}
dst = ROOT / "evidence/v3.14/probing-strategy-order"
dst.mkdir(parents=True, exist_ok=True)
(dst / "order.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("instances", "instances_reasked", "asks_by_strategy")}))
for s, c in out["position_by_strategy"].items():
    print(s, c)
print(out["most_common_sequences"][:3])
