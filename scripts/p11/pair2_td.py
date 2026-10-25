#!/usr/bin/env python3
"""The identity comparison and the header ladder under total disclosure (total leak).

Inputs: the leak classes written by scripts/p11/classify_pair2.mjs for the ladder grid, the identity comparison
and the header ladder (frozen as evidence/v3.14/total-disclosure/pair2_classes_<lane>.jsonl.xz), the
relationship label file, the question set, and the frozen summaries the classes must reproduce:
  - the ladder grid: every class in evidence/v3.14/ladder-per-task/s4_rescore_blocks.json (checked when frozen);
  - the header ladder: every cell's DL count in evidence/v3.13/multi-told/summary.json;
  - the identity comparison: the summary's Leak (trajectory exposure) counts, through each task's leaked flag.
Total disclosure (TD) = decision class or refusal-channel class. Paired exact McNemar on tasks both arms scored.
Output: evidence/v3.14/total-disclosure/pair2_td.json
"""
import collections
import json
import lzma
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import pct  # noqa: E402

TD = ROOT / "evidence/v3.14/total-disclosure"
LAB = json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/"
                         "relationship_label_matrix_v2.json").read_text())
QL = {f"PAIR-Q{q['id']}": q for q in LAB["questions"]}
DS = json.loads((ROOT / "evidence/v3.14/pair-dataset/questions.json").read_text())
CATS = {c["id"]: c for c in DS["categories"]}
CATP = {f"PAIR-Q{q['id']}": CATS[q["category"]]["expected_m2"] == "refuse" for q in DS["questions"]}


def load(lane):
    return [json.loads(l) for l in lzma.open(TD / f"pair2_classes_{lane}.jsonl.xz", "rt")]


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def identity():
    rows = load("identity")
    by = {(r["arm"], r["requester"], r["task"]): r for r in rows}
    out = {}
    pooled = collections.Counter()
    for req in ("R0", "R1", "R2", "R3"):
        tasks = sorted({t for (a, r, t) in by if r == req})
        prot = [t for t in tasks if QL[t][req] == "P" and ("PR", req, t) in by and ("ID", req, t) in by]
        c = collections.Counter()
        for t in prot:
            pr, idd = by[("PR", req, t)], by[("ID", req, t)]
            x = pr["cls"] in ("decision", "refusal-channel")
            y = idd["cls"] in ("decision", "refusal-channel")
            c["n"] += 1
            c["TD_without"] += x
            c["TD_with"] += y
            c["only_without"] += x and not y
            c["only_with"] += y and not x
            c["DL_without"] += pr["cls"] == "decision"
            c["DL_with"] += idd["cls"] == "decision"
            c["RC_without"] += pr["cls"] == "refusal-channel"
            c["RC_with"] += idd["cls"] == "refusal-channel"
            c["trajectory_without"] += pr["leaked"]
            c["trajectory_with"] += idd["leaked"]
        out[req] = dict(c, p=mcnemar(c["only_without"], c["only_with"]))
        pooled.update(c)
    out["pooled"] = dict(pooled, p=mcnemar(pooled["only_without"], pooled["only_with"]))
    s = json.loads((ROOT / "evidence/v3.13/multi-identity/summary.json").read_text())
    for req in ("R0", "R1", "R2", "R3"):
        m = s["requesters"][req]["metrics"]["Leak"]
        assert (out[req]["trajectory_without"], out[req]["trajectory_with"], out[req]["n"]) == \
               (m["PR"]["count"], m["ID"]["count"], m["PR"]["n"]), req
    return out


def header_ladder():
    told = load("told")
    ladder = [r for r in load("ladder") if r["arm"] == "DS"]
    cls = {}
    for r in told:
        cell = f"{r['arm']}-{r['rung']}"
        cls[(cell, r["requester"], r["group"], r["task"])] = r
    for r in ladder:
        cls[(f"AZ-{r['rung']}", r["requester"], r["group"], r["task"])] = r
    pairs = json.loads((ROOT / "evidence/v3.13/multi-told/pairs.json").read_text())
    S = json.loads((ROOT / "evidence/v3.13/multi-told/summary.json").read_text())["pooled"]
    cells = ("AZ-D0", "AZ-D1", "AZ-D2", "CTRL-D2", "TOLD-D0", "TOLD-D1", "TOLD-D2")
    counts = {c: collections.Counter() for c in cells}
    vec = {c: [] for c in cells}
    for p in pairs:
        if "DL" not in p[cells[0]]:
            continue
        for c in cells:
            r = cls[(c, p["requester"], p["group"], p["task"])]
            assert int(r["cls"] == "decision") == p[c]["DL"], (c, p["task"])
            td = r["cls"] in ("decision", "refusal-channel")
            counts[c]["n"] += 1
            counts[c]["DL"] += r["cls"] == "decision"
            counts[c]["RC"] += r["cls"] == "refusal-channel"
            counts[c]["TD"] += td
            vec[c].append(td)
    for c in cells:
        assert (counts[c]["DL"], counts[c]["n"]) == (S["rates"][c]["DL"]["count"], S["rates"][c]["DL"]["n"]), c
    tests = {}
    for a, b in (("CTRL-D2", "TOLD-D2"), ("AZ-D2", "CTRL-D2"), ("TOLD-D0", "TOLD-D2"), ("AZ-D0", "TOLD-D0"),
                 ("AZ-D1", "TOLD-D1"), ("AZ-D2", "TOLD-D2")):
        x = sum(u and not v for u, v in zip(vec[a], vec[b]))
        y = sum(v and not u for u, v in zip(vec[a], vec[b]))
        tests[f"{a} vs {b}"] = {f"only_{a}": x, f"only_{b}": y, "p": mcnemar(x, y)}
    return {"cells": {c: dict(v, TD_pct=pct(v["TD"], v["n"]), DL_pct=pct(v["DL"], v["n"])) for c, v in counts.items()},
            "tests": tests}


if __name__ == "__main__":
    res = {"identity": identity(), "header_ladder": header_ladder()}
    (TD / "pair2_td.json").write_text(json.dumps(res, indent=1) + "\n")
    i = res["identity"]
    for k, v in i.items():
        print(f"identity {k}: TD without {v['TD_without']}/{v['n']} ({pct(v['TD_without'], v['n'])}%), with "
              f"{v['TD_with']}/{v['n']} ({pct(v['TD_with'], v['n'])}%), discordant {v['only_without']}:{v['only_with']}, "
              f"p {v['p']:.3g}; RC {v['RC_without']}/{v['RC_with']}; trajectory {v['trajectory_without']}/{v['trajectory_with']}")
    for c, v in res["header_ladder"]["cells"].items():
        print(f"header ladder {c}: TD {v['TD']}/{v['n']} = {v['TD_pct']}% (DL {v['DL']}, RC {v['RC']})")
    for k, v in res["header_ladder"]["tests"].items():
        print(" ", k, v)
