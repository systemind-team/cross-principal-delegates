#!/usr/bin/env python3
"""P2-3 control claim rate. The control arm asks plainly under the colleague's agent files, so the
files induce some relationship claims; the design (§2) promises this rate and this reports it. It ports P1-6's
claim counter (scripts/pair_multi/spoof/analyze.py claim_counts, patterns in multi-probing-records/numbers.json)
and reproduces D.5's A0h counts on the frozen P1-6 sessions (the acceptance test). No model calls.

The adaptive arm writes no request prefix, so the "own text" and "whole message" columns coincide; only the
relationship and forged-header patterns are reported (the control's identity-claim rate), split by first vs
follow-up request, per arm.

Usage:
  <sessions.jsonl on stdin> | python3 claim_rate.py > claims.json
  python3 claim_rate.py --selftest # reproduce A0h 2/300 first, 105/787 follow-up on the frozen P1-6 file
"""
import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PATTERNS = json.loads((ROOT / "evidence/v3.14/multi-probing-records/numbers.json").read_text())["requester_message_claims"]["patterns"]
REL = re.compile(PATTERNS["relationship_R0"], re.I)
FORGED = re.compile(PATTERNS["forged_header_or_runtime_claim"], re.I)


def claim_counts(recs, label_of):
    """Per (arm, request-kind), count messages and how many carry a relationship claim or forged-header words.
    The adaptive arm writes no prefix, so whole message == own text."""
    acc = collections.defaultdict(collections.Counter)
    for rec in recs:
        seen = collections.Counter()
        for m in rec.get("messages", []):
            if m[1] != "requester" or not isinstance(m[3], str):
                continue
            seen[m[2]] += 1
            kind = "first request" if seen[m[2]] == 1 else "follow-up request"
            cell = acc[(label_of(rec), kind)]
            cell["messages"] += 1
            cell["relationship claim"] += bool(REL.search(m[3]))
            cell["forged-header words"] += bool(FORGED.search(m[3]))
    return {f"{a} / {k}": dict(v) for (a, k), v in sorted(acc.items())}


def load_stdin():
    return [json.loads(x) for x in sys.stdin if x.strip() and '"policies"' not in x[:20]]


def selftest():
    sess = ROOT / "evidence/v3.14/multi-spoof/sessions.jsonl.xz"
    recs = [json.loads(x) for x in subprocess.run(["xz", "-dc", str(sess)], capture_output=True, text=True).stdout.splitlines()
            if x.strip() and '"policies"' not in x[:20]]
    out = claim_counts([r for r in recs if r.get("arm") == "A0h"], lambda r: r["arm"])
    first = out["A0h / first request"]; follow = out["A0h / follow-up request"]
    assert first["messages"] == 300 and first["relationship claim"] == 2, first
    assert follow["messages"] == 787 and follow["relationship claim"] == 105, follow
    print(f"claim_rate selftest: A0h first {first['relationship claim']}/{first['messages']}, "
          f"follow-up {follow['relationship claim']}/{follow['messages']} (reproduces D.5)", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    recs = load_stdin()
    print(json.dumps({"patterns": {"relationship": PATTERNS["relationship_R0"],
                                   "forged_header": PATTERNS["forged_header_or_runtime_claim"]},
                      "by_arm": claim_counts(recs, lambda r: r["arm"])}, indent=1))


if __name__ == "__main__":
    main()
