#!/usr/bin/env python3
"""Ladder grid (Table 4 / Table 27): reproduce the frozen block tables from per-task records, then list the
D2 leaks by task and count the distinct questions behind them.

Inputs (frozen): evidence/v3.14/ladder-per-task/ladder.jsonl.xz (scripts/freeze/pair2_runs/extract.py ladder:
the run folder chosen per session slot, each task's publicEvaluation, every message) and
s4_rescore_blocks.json (the leak class of every scored protected question, written on the VM by
rescore_classify_s4.py on 2026-09-28 together with the frozen s4_rescore_table.json); the question set
(evidence/v3.14/pair-dataset/questions.json). Rules are analyze_s4.py's and rescore_table_s4.py's.
Output: evidence/v3.14/ladder-per-task/d2_leaks.json
"""
import collections
import json
import lzma
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
EV = ROOT / "evidence/v3.14/ladder-per-task"
T3 = json.loads((ROOT / "evidence/v3.13/multi-table3/table3s.json").read_text())
S4 = json.loads((ROOT / "evidence/v3.13/multi-table3/s4_rescore_table.json").read_text())
DS = json.loads((ROOT / "evidence/v3.14/pair-dataset/questions.json").read_text())
CAT = {c["id"]: c for c in DS["categories"]}
Q = {f"PAIR-Q{q['id']}": q for q in DS["questions"]}
A = {f"PAIR-A{a['id']}": a for a in DS["actions"]}
BUILDS, POLS, REQS = ("DS", "GLM", "GROK"), ("D0", "D1", "D2"), ("R1", "R2", "R3")


def kindof(t):
    if t in Q:
        return "qa_" + CAT[Q[t]["category"]]["expected_m2"]
    return "act_" + ("auth" if A[t]["category"].startswith("authorized") else "unauth")


recs = [json.loads(l) for l in lzma.open(EV / "ladder.jsonl.xz", "rt")]
recs = [r for r in recs if "arm" in r]
assert len(recs) == 1350
ev = {}
for r in recs:
    for t in r.get("tasks", []):
        pe = t["publicEvaluation"]
        if pe:
            ev[(r["arm"], r["rung"], r["requester"], r["group"], pe["taskId"])] = pe
groups = sorted({r["group"] for r in recs})
TASKS = {r["group"]: r["tasks_selected"] for r in recs}


def cell_items(b, p, r):
    return {(g, t) for g in groups for t in TASKS[g] if (b, p, r, g, t) in ev}


checks = {}
for b in BUILDS:
    for r in REQS:
        for p in POLS:
            checks[f"scored {b}-{p}-{r}"] = len(cell_items(b, p, r)) == T3["cells"][f"{b}-{p}-{r}"]["scored"]
        keep = cell_items(b, "D0", r) & cell_items(b, "D1", r) & cell_items(b, "D2", r)
        checks[f"block n {b}-{r}"] = len(keep) == T3["blocks"][f"{b}-{r}"]["n_tasks"]
assert all(checks.values()), [k for k, v in checks.items() if not v]

cls = {tuple(k.split("|")): v for k, v in json.loads((EV / "s4_rescore_blocks.json").read_text())["cls"].items()}
out = {"reproduces": {"table3s_scored_and_block_n": all(checks.values())}, "blocks": {}, "d2_decision_leaks": [],
       "d2_refusal_channel_leaks": []}
for b in BUILDS:
    for r in REQS:
        keep = cell_items(b, "D0", r) & cell_items(b, "D1", r) & cell_items(b, "D2", r)
        prot = sorted((g, t) for g, t in keep if kindof(t) == "qa_refuse")
        assert len(prot) == S4[f"{b}-{r}"]["n"]
        row = {}
        for p in POLS:
            c = collections.Counter(cls.get((b, p, r, g, t), "missing") for g, t in prot)
            assert [c["decision"], c["refusal-channel"]] == S4[f"{b}-{r}"]["counts"][p], (b, r, p, c)
            row[p] = {"decision": c["decision"], "refusal_channel": c["refusal-channel"], "echo": c["echo"],
                      "none": c["none"], "no_reply": c["no-reply"], "missing": c["missing"]}
        out["blocks"][f"{b}-{r}"] = {"n": len(prot), **row}
        for g, t in prot:
            k = cls.get((b, "D2", r, g, t))
            if k in ("decision", "refusal-channel"):
                (out["d2_decision_leaks"] if k == "decision" else out["d2_refusal_channel_leaks"]).append(
                    {"build": b, "requester": r, "group": g, "task": t, "category": Q[t]["category"],
                     "topic": Q[t].get("topic"), "question": Q[t]["question"]})
out["reproduces"]["s4_rescore_table_counts"] = True
dl = out["d2_decision_leaks"]
by_task = collections.Counter(x["task"] for x in dl)
out["d2_decision_leak_summary"] = {"leaks": len(dl), "distinct_questions": len(by_task),
                                    "by_task": dict(by_task.most_common()),
                                    "on_two_most_frequent": sum(v for _, v in by_task.most_common(2))}
rc = out["d2_refusal_channel_leaks"]
out["d2_refusal_channel_summary"] = {"leaks": len(rc), "distinct_questions": len({x["task"] for x in rc})}
(EV / "d2_leaks.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out["d2_decision_leak_summary"], indent=1))
for x in dl:
    print(x["build"], x["requester"], x["group"], x["task"], x["category"], "|", x["question"])
print("refusal channel at D2:", out["d2_refusal_channel_summary"], [(x["build"], x["requester"], x["task"]) for x in rc])
