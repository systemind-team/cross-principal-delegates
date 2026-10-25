#!/usr/bin/env python3
"""PAIR II ladder grid: total disclosure (total leak) per block and rung.

Input: evidence/v3.13/multi-table3/s4_rescore_table.json. Per block (build x requester) and rung it holds the
protected questions scored at all three rungs (n) and two counts: decision leaks (a reply the requester
recorded as an answer carries a gold fact) and refusal-channel leaks (a refusal, or an earlier reply of an
answered task, carries a gold fact not already in the conversation; echoes excluded). Total disclosure is
their sum over n. Rates are rounded half away from zero from the counts (scripts/common/halfup.py).

Output: evidence/v3.14/pair2-total-disclosure/td.json, and a printed table.
"""
import json
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import pct  # noqa: E402

S4 = json.loads((ROOT / "evidence/v3.13/multi-table3/s4_rescore_table.json").read_text())
BUILDS, REQS, RUNGS = ("DS", "GLM", "GROK"), ("R1", "R2", "R3"), ("D0", "D1", "D2")
out = {"blocks": {}, "ranges": {}}
by_rung = {g: [] for g in RUNGS}
for b in BUILDS:
    for r in REQS:
        x = S4[f"{b}-{r}"]
        n = x["n"]
        row = {"n": n}
        for g in RUNGS:
            dec, rc = x["counts"][g]
            td = dec + rc
            row[g] = {"decision": dec, "refusal_channel": rc, "total": td,
                      "decision_pct": pct(dec, n), "total_pct": pct(td, n)}
            by_rung[g].append((Fraction(100 * td, n), f"{b}-{r}", td, n))
        out["blocks"][f"{b}-{r}"] = row
for g in RUNGS:
    lo, hi = min(by_rung[g]), max(by_rung[g])
    out["ranges"][g] = {"min": {"block": lo[1], "count": f"{lo[2]}/{lo[3]}", "pct": pct(lo[2], lo[3])},
                        "max": {"block": hi[1], "count": f"{hi[2]}/{hi[3]}", "pct": pct(hi[2], hi[3])}}
dst = ROOT / "evidence/v3.14/pair2-total-disclosure"
dst.mkdir(parents=True, exist_ok=True)
(dst / "td.json").write_text(json.dumps(out, indent=1) + "\n")
print(f"{'block':8s} {'n':>3s}  " + "  ".join(f"{g}: DL+RC=TD (TD%)" for g in RUNGS))
for k, row in out["blocks"].items():
    print(f"{k:8s} {row['n']:3d}  " + "  ".join(
        f"{g}: {row[g]['decision']}+{row[g]['refusal_channel']}={row[g]['total']} ({row[g]['total_pct']})" for g in RUNGS))
for g in RUNGS:
    r = out["ranges"][g]
    print(f"{g} total disclosure range: {r['min']['pct']}% ({r['min']['block']}, {r['min']['count']}) to "
          f"{r['max']['pct']}% ({r['max']['block']}, {r['max']['count']})")
