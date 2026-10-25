#!/usr/bin/env python3
"""Kernel check: totals of replay_decisions.mjs output files (one JSON line per run).

Usage: replay_summary.py <label>=<file.jsonl> [...]   prints one JSON object: per label the runs, replay errors
(with their messages counted), decisions, recorded allowed/denied with the denial reasons, runs whose usage
reconstruction matched their usage records, and the three agreement counts; plus every differing decision.
"""
import collections
import json
import sys


def main(pairs):
    out = {}
    for pair in pairs:
        label, path = pair.split("=", 1)
        b = collections.Counter()
        errors = collections.Counter()
        diffs = []
        for line in open(path):
            r = json.loads(line)
            if "error" in r:
                errors[r["error"]] += 1
                continue
            b["runs"] += 1
            b["usage_calibrated_runs"] += bool(r["usage_calibrated"])
            for k in ("decisions", "recorded_allowed", "recorded_denied", "k2_equals_recorded", "k1_equals_recorded",
                      "k1_equals_k2"):
                b[k] += r[k]
            for reason, n in r["denied_reasons"].items():
                b[f"denied:{reason}"] += n
            diffs += [{"run": r["run"], **d} for d in r["differences"]]
        out[label] = {"totals": dict(b), "replay_errors": dict(errors), "differences": diffs}
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
