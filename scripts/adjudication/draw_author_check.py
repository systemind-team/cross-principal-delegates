#!/usr/bin/env python3
"""P1-2: draw the items for the author check (protocol v2 §8).

Run after both annotators have labelled and every disagreement is adjudicated, before any rate is computed. The
seed is seeds.json's author_check_seed, read off the sha256 of the frame's cells.json, so nobody chooses the items.
Planted items are excluded. With random.Random(seed), over item ids sorted within each pool:
  10 items (annotator option (c), one Claude and one Gemini annotator):
     4 from S2; 3 from S1 (S1L and S1F); 3 from the S3 and S5 items (S3P, S3I, S5F, S5L) that either annotator
     labelled as conveying a fact, or uniformly from all S3 and S5 items for any of the 3 places that pool
     cannot fill;
  20 items (fallback, two Claude annotators; at least 20, 10 of them from S1 and S2):
     5 from S2; 5 from S1; 5 as the third pool above; 5 from the remaining strata (S4P, S4I, S6F, S6C, SR).
The author labels the drawn items blind to every label, from the same packet text and the same guidelines.

Usage: python3 draw_author_check.py <10|20> <seeds.json> <key.jsonl> <packet dir> <labels A dir> <labels B dir> <out.jsonl>
"""
import glob
import hashlib
import json
import os
import random
import sys

SIZE, SEEDS, KEY, PACKETS, LA, LB, OUT = sys.argv[1:8]
SIZE = int(SIZE)
assert SIZE in (10, 20)
seed = json.load(open(SEEDS))["author_check_seed"]
rng = random.Random(seed)
key = {r["item_id"]: r for r in map(json.loads, open(KEY))}


def labels(folder):
    out = {}
    for path in glob.glob(os.path.join(folder, "*.jsonl")):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                if "item_id" in r:
                    out[r["item_id"]] = bool(r.get("facts_conveyed"))
    return out


A, B = labels(LA), labels(LB)
real = sorted(i for i, k in key.items() if k["kind"] == "real")
pool = lambda strata: [i for i in real if key[i]["stratum"] in strata]
s35 = pool({"S3P", "S3I", "S5F", "S5L"})
s35_conv = [i for i in s35 if A.get(i) or B.get(i)]
plan = ([("S2", pool({"S2"}), 4), ("S1", pool({"S1L", "S1F"}), 3), ("S3/S5 conveyed by either", s35_conv, 3)]
        if SIZE == 10 else
        [("S2", pool({"S2"}), 5), ("S1", pool({"S1L", "S1F"}), 5), ("S3/S5 conveyed by either", s35_conv, 5),
         ("other strata", pool({"S4P", "S4I", "S6F", "S6C", "SR"}), 5)])
drawn, used = [], set()
for name, ids, n in plan:
    take = rng.sample(ids, min(n, len(ids)))
    if len(take) < n:                                   # fill from all S3/S5 items, uniformly
        rest = [i for i in s35 if i not in take and i not in used]
        take += rng.sample(rest, n - len(take))
    used.update(take)
    drawn += [(name, i) for i in take]
wanted = {i for _, i in drawn}
lines = {}
for path in sorted(glob.glob(os.path.join(PACKETS, "*.jsonl"))):
    for line in open(path):
        item = json.loads(line)
        if item["item_id"] in wanted:
            lines[item["item_id"]] = line if line.endswith("\n") else line + "\n"
assert set(lines) == wanted
order = [i for _, i in drawn]
rng.shuffle(order)
with open(OUT, "w") as fh:
    for i in order:
        fh.write(lines[i])
print(json.dumps({"seed": seed, "size": SIZE, "key_sha256": hashlib.sha256(open(KEY, "rb").read()).hexdigest(),
                  "drawn": [{"pool": s, "item_id": i, "stratum": key[i]["stratum"]} for s, i in drawn],
                  "author_packet": OUT}, indent=1))
