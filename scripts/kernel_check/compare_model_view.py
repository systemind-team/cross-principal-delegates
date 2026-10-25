#!/usr/bin/env python3
"""Kernel check: did two runs show the model the same thing?

Compares the actor-context logs of two SharedEval run roots (`<run>/multi/.sharedeval-actor-context/actors/<actor>/
record-*.json`: every turn's begin input, every message and tool result the model was given, every finish).
Run-derived identifiers are normalized before comparing: 40- and 64-hex digests (trace, execution, message,
call, grant and namespace ids are derived from the run id), UUIDs, and each run's own run id. Timestamps are
normalized too. Then the records are compared field by field, per actor, in sequence order.

Usage: compare_model_view.py <run-root-A> <run-root-B>   prints one JSON object (counts and first differences)
"""
import glob
import json
import os
import re
import sys

HEX = re.compile(r"\b[0-9a-f]{40}\b|\b[0-9a-f]{64}\b")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
TIME = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")


def norm(value, run_id):
    text = json.dumps(value, sort_keys=True)
    text = text.replace(run_id, "<run>")
    text = HEX.sub("<hex>", text)
    text = UUID.sub("<uuid>", text)
    return TIME.sub("<time>", text)


def load(root):
    run_id = os.path.basename(root.rstrip("/"))
    actors = {}
    for d in sorted(glob.glob(os.path.join(root, "multi/.sharedeval-actor-context/actors/*/"))):
        recs = []
        for f in sorted(glob.glob(os.path.join(d, "record-*.json"))):
            r = json.load(open(f))
            recs.append({k: v for k, v in r.items() if k not in ("hash", "previousHash", "inputHash")})
        actor = recs[0]["actorId"] if recs else os.path.basename(d.rstrip("/"))
        actors[actor] = [norm(r, run_id) for r in recs]
    return actors


def main(a, b):
    A, B = load(a), load(b)
    out = {"actors_a": sorted(A), "actors_b": sorted(B), "per_actor": {}, "first_differences": []}
    for actor in sorted(set(A) | set(B)):
        ra, rb = A.get(actor, []), B.get(actor, [])
        same = sum(1 for x, y in zip(ra, rb) if x == y)
        out["per_actor"][actor] = {"records_a": len(ra), "records_b": len(rb), "identical": same}
        for i, (x, y) in enumerate(zip(ra, rb)):
            if x != y and len(out["first_differences"]) < 5:
                j = next(k for k in range(min(len(x), len(y))) if x[k] != y[k]) if x[:len(y)] != y[:len(x)] else min(len(x), len(y))
                out["first_differences"].append({"actor": actor, "record": i + 1, "a": x[max(0, j - 120):j + 200],
                                                 "b": y[max(0, j - 120):j + 200]})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
