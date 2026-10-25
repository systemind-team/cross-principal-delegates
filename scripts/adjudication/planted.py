#!/usr/bin/env python3
"""P1-2: build the 40 planted items from real replies outside the draw.

Inputs, both in the sealed folder (outside <internal>, never shown to an annotator):
  planted_bases.jsonl  draw.py's base replies, one per slot, with their question, requests, facts and reply;
  planted_edits.json   per slot, the edits (each an exact substring of the base and its replacement, applied once)
                       and the known answer: label, facts conveyed (1-based), narrowed facts, existence type.
Each edit must match its base exactly once, and every planted item must differ from its base. Eight items per
label (FULL, PARTIAL, NARROWED, EXISTENCE, NONE).

Writes, in the sealed folder:
  planted_items.jsonl    the 40 items in packet form (question, earlier_requests, request, protected_facts, reply),
                         keyed by slot;
  planted_answers.jsonl  slot, base unit, edit kind and known answer.
Prints the sha256 of both files. The hash of planted_answers.jsonl is committed and posted before any packet goes
out; the file itself is committed after both annotators have returned their labels.

Usage: python3 planted.py <sealed dir>
"""
import collections
import hashlib
import json
import os
import sys

D = sys.argv[1]
bases = {b["slot"]: b for b in map(json.loads, open(os.path.join(D, "planted_bases.jsonl")))}
edits = json.load(open(os.path.join(D, "planted_edits.json")))["slots"]
assert set(bases) == set(edits) and len(bases) == 40


def apply(text, pairs, where):
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"{where}: edit matches {n} times: {old[:60]!r}")
        text = text.replace(old, new)
    return text


items, answers = [], []
for slot in sorted(bases):
    b, e = bases[slot], edits[slot]
    request = apply(b["request"], e.get("request", []), f"{slot} request")
    reply = apply(b["reply"], e.get("reply", []), f"{slot} reply")
    assert reply != b["reply"], slot
    a = e["answer"]
    assert a["label"] == b["class"], (slot, a["label"], b["class"])
    n = len(b["protected_facts"])
    assert all(1 <= i <= n for i in a.get("facts_conveyed", []) + a.get("narrowed", [])), slot
    if a["label"] == "FULL":
        assert sorted(a["facts_conveyed"]) == list(range(1, n + 1)), slot
    if a["label"] == "PARTIAL":
        assert 0 < len(a["facts_conveyed"]) < n, slot
    if a["label"] in ("NARROWED", "EXISTENCE", "NONE"):
        assert not a["facts_conveyed"], slot
    items.append({"slot": slot, "question": b["question"], "earlier_requests": b["earlier_requests"], "request": request,
                  "protected_facts": b["protected_facts"], "reply": reply})
    answers.append({"slot": slot, "study": b["study"], "base_unit": b["unit"], "edit": b["edit"], **a,
                    "request_edited": request != b["request"]})
assert collections.Counter(a["label"] for a in answers) == {k: 8 for k in ("FULL", "PARTIAL", "NARROWED", "EXISTENCE", "NONE")}

out = {}
for name, rows in (("planted_items.jsonl", items), ("planted_answers.jsonl", answers)):
    with open(os.path.join(D, name), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out[name] = hashlib.sha256(open(os.path.join(D, name), "rb").read()).hexdigest()
print(json.dumps(out, indent=1))
