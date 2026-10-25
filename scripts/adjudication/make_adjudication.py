#!/usr/bin/env python3
"""P1-2: build the adjudicator's packet from the two annotators' label disagreements (protocol v2 §8), and map its
answers back to A and B afterwards. Run after both label sets pass validate_labels.py and the gates.

The adjudicator is a Claude model other than both annotators, Opus 5.5 and Opus 5, seated blind like them. For each
item whose labels differ it sees the packet item unchanged and the two labels with their facts and quotes, as
"label X" and "label Y" in an order drawn per item with random.Random(author_check_seed + 1); it never learns which
annotator wrote which. It answers {"item_id", "choice": "X" | "Y" | "UNREADABLE", "reason": <one sentence citing the
reply>}. Planted items are never sent (their answers are known).

  build:  python3 make_adjudication.py build <seeds.json> <key.jsonl> <packets A> <labels A> <labels B>
                  <out packet.jsonl> <sealed map.jsonl>
  map:    python3 make_adjudication.py map <sealed map.jsonl> <adjudicator answers.jsonl> > adjudication.jsonl
The mapped file (item_id, chosen: "A" | "B" | "UNREADABLE", reason) is what score.py reads.
"""
import glob
import json
import os
import random
import sys


def labels(folder):
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                if "item_id" in r:
                    out[r["item_id"]] = r
    return out


def build(seeds, key, packets, la, lb, out, sealed):
    rng = random.Random(json.load(open(seeds))["author_check_seed"] + 1)
    key = {r["item_id"]: r for r in map(json.loads, open(key))}
    items = {}
    for path in sorted(glob.glob(os.path.join(packets, "*.jsonl"))):
        for line in open(path):
            it = json.loads(line)
            items[it["item_id"]] = it
    A, B = labels(la), labels(lb)
    keep = ("label", "facts_conveyed", "facts_narrowed", "existence_type", "quote")
    rows, mapping = [], []
    for iid in sorted(items):
        if key[iid]["kind"] != "real" or iid not in A or iid not in B or A[iid]["label"] == B[iid]["label"]:
            continue
        x_is_a = rng.random() < 0.5
        X, Y = (A[iid], B[iid]) if x_is_a else (B[iid], A[iid])
        rows.append({**items[iid], "label_X": {k: X.get(k) for k in keep}, "label_Y": {k: Y.get(k) for k in keep}})
        mapping.append({"item_id": iid, "X": "A" if x_is_a else "B", "Y": "B" if x_is_a else "A"})
    rng.shuffle(rows)
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(sealed, "w") as f:
        for m in mapping:
            f.write(json.dumps(m) + "\n")
    print(json.dumps({"disagreements": len(rows), "packet": out, "map": sealed}))


def map_back(sealed, answers):
    m = {r["item_id"]: r for r in map(json.loads, open(sealed))}
    for line in open(answers):
        if not line.strip():
            continue
        r = json.loads(line)
        c = r.get("choice")
        chosen = "UNREADABLE" if c == "UNREADABLE" else m[r["item_id"]][c]
        print(json.dumps({"item_id": r["item_id"], "chosen": chosen, "reason": r.get("reason", "")}, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(*sys.argv[2:9])
    elif sys.argv[1] == "map":
        map_back(sys.argv[2], sys.argv[3])
    else:
        sys.exit("usage: build ... | map ...")
