#!/usr/bin/env python3
"""Table 41 (tab:net-instruments) and the body's "16 of the 53", from summary/net_traces.txt.

summary/net_traces.txt is the text dump of the 149 judged replies of the preliminary run on the eight edges the
NET string matcher can decide (four lanes: DeepSeek V4 Flash at D0, D1 and D2, GLM at D2). Each entry gives the
edge, the arm (PERMITTED / WITHHELD), the rung, the model, the LLM judge's verdict and the matcher's hits.
Lower block: the 2x2 agreement over all 149 replies. Upper block: per rung, on the DeepSeek lanes, over the edges of
the set delivered at that rung (a reply on the forbidden arm), the share of edges with at least one reply flagged on
each arm (forbidden = WITHHELD, permitted = PERMITTED); every six-edge subset of the eight is tried; exactly one reproduces
the printed values, and the script checks that it is the six non-borderline edges of the frozen world
(evidence/v3.14/net-world/paired_edges_24.json).
Output: evidence/v3.14/net-preliminary/instruments.json (the table's values) and verdicts.json (each reply's run,
holder, requester, arm, rung, model, the judge's verdict and the matcher's hits)
"""
import collections
import itertools
import json
import pathlib
import re
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, pct  # noqa: E402

text = (ROOT / "summary/net_traces.txt").read_text()
head = re.compile(r"^\[(\d+)/149\] (\S+)\s+(PERMITTED|WITHHELD)\s+\|\s+(D\d)[^|]*\|\s+(.+?)(\s+<--.*)?$")
entries, cur = [], None
for line in text.splitlines():
    m = head.match(line)
    if m:
        cur = {"i": int(m.group(1)), "edge": m.group(2), "arm": m.group(3), "rung": m.group(4),
               "model": "GLM" if m.group(5).startswith("GLM") else "DeepSeek"}
        entries.append(cur)
        continue
    if cur is not None and line.startswith("run="):
        m2 = re.match(r"run=(\S+)\s+holder=(\S+)\s+asker=(\S+)", line)
        if m2:
            cur["run"], cur["holder"], cur["requester"] = m2.group(1), m2.group(2), m2.group(3)
        continue
    if cur is not None and line.startswith("JUDGE:"):
        j = re.match(r"JUDGE: (DISCLOSED|NOT_DISCLOSED) \(unanimous=(\w+)\)\s+INSTRUMENT: (.*)$", line)
        cur["judge"] = j.group(1) == "DISCLOSED"
        cur["unanimous"] = j.group(2) == "True"
        cur["matcher"] = j.group(3).strip() != "no hit"
        cur["matcher_hits"] = [] if not cur["matcher"] else [h.strip() for h in j.group(3).split(";") if h.strip()]
assert len(entries) == 149 and [e["i"] for e in entries] == list(range(1, 150)), len(entries)
assert all("judge" in e for e in entries)
c = collections.Counter((e["judge"], e["matcher"]) for e in entries)
lower = {"both": c[(True, True)], "judge_only": c[(True, False)], "matcher_only": c[(False, True)],
         "both_clean": c[(False, False)], "n": len(entries)}
either = lower["both"] + lower["judge_only"] + lower["matcher_only"]
lower["agree_when_either_fires"] = f"{lower['both']} / {either}"
lower["pct"] = {k: pct(lower[k], 149) for k in ("both", "judge_only", "matcher_only", "both_clean")}
lower["agreement_pct"] = pct(lower["both"] + lower["both_clean"], 149)
lower["either_pct"] = pct(lower["both"], either)
printed_lower = {"both": 16, "judge_only": 35, "matcher_only": 2, "both_clean": 96}
lower_ok = all(lower[k] == v for k, v in printed_lower.items())
# upper block
PRINTED_UP = {"D0": ("0.600", "0.400", "0.600", "0.400"), "D1": ("0.167", "0.167", "0.667", "0.500"),
              "D2": ("0.667", "0.500", "0.667", "0.333")}
edges = sorted({e["edge"] for e in entries})


def upper(edge_set):
    """Per rung, over the edges of edge_set delivered at that rung (a reply on the forbidden arm), the share with at
    least one reply flagged on each arm, by each instrument."""
    out = {}
    for g in ("D0", "D1", "D2"):
        delivered = {e["edge"] for e in entries if e["model"] == "DeepSeek" and e["rung"] == g
                     and e["arm"] == "WITHHELD" and e["edge"] in edge_set}
        row = []
        for arm in ("WITHHELD", "PERMITTED"):
            for inst in ("judge", "matcher"):
                hit = {e["edge"] for e in entries if e["model"] == "DeepSeek" and e["rung"] == g and e["arm"] == arm
                       and e["edge"] in delivered and e[inst]}
                row.append((len(hit), len(delivered)))
        out[g] = row
    return out


def printed_match(up):
    for g, vals in PRINTED_UP.items():
        got = [fixed(Fraction(k, n), 3) if n else None for k, n in
               (up[g][0], up[g][1], up[g][2], up[g][3])]
        if got != list(vals):
            return False
    return True


matches = [list(s) for s in itertools.combinations(edges, 6) if printed_match(upper(set(s)))]
# the caption's "six non-borderline edges": the borderline flags of the frozen world (evidence/v3.14/net-world)
flags = {e["edge"]: e["borderline"] for e in
         json.loads((ROOT / "evidence/v3.14/net-world/paired_edges_24.json").read_text())["edges"]}
non_borderline = sorted(e for e in edges if flags.get(e) is False)
assert matches == [non_borderline], (matches, non_borderline)
res = {"lower_block": lower, "lower_block_reproduces": lower_ok, "edges": edges,
       "non_borderline_edges": non_borderline,
       "upper_block_edge_sets_that_reproduce": matches,
       "upper_block": ({g: [f"{k}/{n}" for k, n in v] for g, v in upper(set(matches[0])).items()} if matches else None),
       "columns": ["L_w judge", "L_w matcher", "L_p judge", "L_p matcher"]}
dst = ROOT / "evidence/v3.14/net-preliminary"
dst.mkdir(parents=True, exist_ok=True)
(dst / "instruments.json").write_text(json.dumps(res, indent=1) + "\n")
# the per-reply verdicts of both instruments, structured: one row per judged reply of the dump
verdicts = [{"index": e["i"], "edge": e["edge"], "arm": {"WITHHELD": "forbidden", "PERMITTED": "permitted"}[e["arm"]],
             "rung": e["rung"], "model": e["model"], "run": e.get("run"), "holder": e.get("holder"),
             "requester": e.get("requester"), "judge_disclosed": e["judge"], "judge_unanimous": e["unanimous"],
             "matcher_hit": e["matcher"], "matcher_hits": e["matcher_hits"]} for e in entries]
(dst / "verdicts.json").write_text(json.dumps({"source": "summary/net_traces.txt", "rows": verdicts}, indent=1) + "\n")
res["judge_total"] = sum(e["judge"] for e in entries); res["matcher_total"] = sum(e["matcher"] for e in entries)
(dst / "instruments.json").write_text(json.dumps(res, indent=1) + "\n")
print("lower block:", {k: lower[k] for k in printed_lower}, "agree when either fires", lower["agree_when_either_fires"],
      f"({lower['either_pct']}%), overall agreement {lower['agreement_pct']}%", "reproduces:", lower_ok)
print("upper block edge sets that reproduce:", matches)
if matches:
    print(res["upper_block"])
