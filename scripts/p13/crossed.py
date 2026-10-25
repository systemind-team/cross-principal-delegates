#!/usr/bin/env python3
"""Pre-registration section 5: the crossed table. Each same-model PAIR I cell at D0, D1 and D2 scored under both label sets,
relationship (the original labels) and category (the total-leak files' `cat`), with total leak and false refusal.

Leak    total leak (decision leak or refusal-channel leak, echoes excluded) on the questions the label set
        protects for the requester, with recovery
FR      refused, on the questions and actions the label set entitles, with recovery; actions whose status is
        side_effect_before_failure are left out, as in Table 3

Before anything is written, the per-task rows must reproduce exactly (the script stops otherwise):
  relationship decision leak and FR, with recovery    evidence/v3.13/single-grid/cells.json, block "recovered"
  relationship and category total leak                 evidence/v3.14/total-disclosure/pair1_cells.json
  category decision leak and FR, strict                the rescore files' "category" block
                                                       (evidence/v3.13/single-grid/rescore-{openrouter-82,azure-28}.json)

Output: evidence/v3.14/p13-results/crossed.json and crossed.md
"""
import collections
import json
import lzma
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import pct  # noqa: E402

EV = ROOT / "evidence"
OUT = EV / "v3.14/p13-results"
MODELS = (("ds41", "DeepSeek V4.1"), ("glm", "GLM-5.3-Flash"), ("luna", "GPT-5.6"))
RUNGS = ("D0", "D1", "D2")
REQS = (("R0", "stranger"), ("R1", "colleague"), ("R2", "CEO's asst."), ("R3", "close friend"))
BODY = ("R3", "R1")


def load():
    status = {}
    with lzma.open(EV / "v3.14/single-grid-tasks/tasks.jsonl.xz", "rt") as f:
        for line in f:
            o = json.loads(line)
            status[(o["cell"], o["taskId"])] = o["status"]
    rows = collections.defaultdict(list)
    with lzma.open(EV / "v3.14/total-disclosure/pair1_tasks.jsonl.xz", "rt") as f:
        for line in f:
            o = json.loads(line)
            if o["family"] in dict(MODELS) and o["policy"] in RUNGS:
                o["status"] = status[(o["cell"], o["task"])]
                rows[o["cell"]].append(o)
    return rows


def tally(rows, lab, strict):
    """Counts for one cell under one label set ('rel' or 'cat')."""
    c = collections.Counter()
    for o in rows:
        if not o["scored"] or (strict and o["recovered"]):
            continue
        if o["kind"] == "question" and o[lab] == "protect":
            c["n"] += 1
            c["TL"] += bool(o["total_disclosure"])
            c["DL"] += bool(o["decision_leak"])
        elif o[lab] == "entitle":
            if o["kind"] == "action" and o["status"] == "side_effect_before_failure":
                continue
            c["n_entitled"] += 1
            c["FR"] += o["decision"] == "refuse"
    return dict(c)


def frac(block, metric):
    m = block[metric]
    return [m["numerator"], m["denominator"]]


def main():
    rows = load()
    cells_json = {c["cell"]: c for c in json.loads((EV / "v3.13/single-grid/cells.json").read_text())["cells"]}
    p11 = json.loads((EV / "v3.14/total-disclosure/pair1_cells.json").read_text())["cells"]
    rescore = {}
    for fn in ("rescore-openrouter-82.json", "rescore-azure-28.json"):
        rescore.update(json.loads((EV / "v3.13/single-grid" / fn).read_text())["cells"])
    out, checks = {}, {}
    for cell in sorted(rows):
        r = {lab: tally(rows[cell], lab, False) for lab in ("rel", "cat")}
        s = {lab: tally(rows[cell], lab, True) for lab in ("rel", "cat")}
        rec = cells_json[cell]["recovered"]
        checks[f"{cell} relationship DL = cells.json"] = [r["rel"]["DL"], r["rel"]["n"]] == frac(rec, "leakRate")
        checks[f"{cell} relationship FR = cells.json"] = [r["rel"]["FR"], r["rel"]["n_entitled"]] == frac(rec, "falseRefusalRate")
        checks[f"{cell} relationship TL = total-leak file"] = [r["rel"]["TL"], r["rel"]["n"]] == [p11[cell]["relationship"]["TD"], p11[cell]["relationship"]["n"]]
        checks[f"{cell} category TL = total-leak file"] = [r["cat"]["TL"], r["cat"]["n"]] == [p11[cell]["category"]["TD"], p11[cell]["category"]["n"]]
        cat = rescore[cell]["category"]
        checks[f"{cell} category DL strict = rescore"] = [s["cat"]["DL"], s["cat"]["n"]] == frac(cat, "leakRate")
        checks[f"{cell} category FR strict = rescore"] = [s["cat"]["FR"], s["cat"]["n_entitled"]] == frac(cat, "falseRefusalRate")
        out[cell] = {"relationship": r["rel"], "category": r["cat"]}
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise SystemExit("crossed table does not reproduce the frozen cells:\n  " + "\n  ".join(bad))
    table = {}
    for q, qname in REQS:
        for u in RUNGS:
            line = {}
            for lab, labname in (("relationship", "relationship labels"), ("category", "category labels")):
                for metric, num, den in (("leak", "TL", "n"), ("FR", "FR", "n_entitled")):
                    line[f"{labname} / {metric}"] = {
                        mname: [out[f"{m}-{u.lower()}-{q.lower()}"][lab].get(num, 0),
                                out[f"{m}-{u.lower()}-{q.lower()}"][lab].get(den, 0)] for m, mname in MODELS}
            table[f"{q} {qname} / {u}"] = line
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / "crossed.json").write_text(json.dumps({"checks_passed": len(checks), "cells": out, "table": table},
                                                 indent=1) + "\n")
    md = ["# Crossed table (PREREGISTRATION section 5)", "",
          "Total leak and false refusal per cell, with recovery, under the relationship labels (the original set) and "
          "the category labels. Each entry is DeepSeek V4.1 / GLM-5.3-Flash / GPT-5.6 as % (events/rows). "
          f"Reproduction checks passed: {len(checks)} of {len(checks)}. Body rows: close friend (R3) and colleague (R1).", "",
          "| Requester | Rung | Rel. leak | Rel. FR | Cat. leak | Cat. FR |", "|---|---|---|---|---|---|"]
    for q, qname in REQS:
        for u in RUNGS:
            line = table[f"{q} {qname} / {u}"]
            cellstr = []
            for key in ("relationship labels / leak", "relationship labels / FR", "category labels / leak",
                        "category labels / FR"):
                parts = []
                for _, mname in MODELS:
                    k, n = line[key][mname]
                    parts.append(f"{pct(k, n, 1)} ({k}/{n})" if n else "n/a (0 rows)")
                cellstr.append(" / ".join(parts))
            md.append(f"| {q} {qname} | {u} | " + " | ".join(cellstr) + " |")
    (OUT / "crossed.md").write_text("\n".join(md) + "\n")
    print(f"{len(checks)} reproduction checks passed; written {OUT / 'crossed.json'} and crossed.md")


if __name__ == "__main__":
    main()
