#!/usr/bin/env python3
"""Identity comparison (Appendix D.4) from the frozen per-task records: reproduce the frozen summary, then
split the arms' differences by task type.

Input: evidence/v3.14/identity-per-task/identity.jsonl.xz (scripts/freeze/pair2_runs/extract.py identity),
the relationship label file, and the ladder grid's MANIFEST.json. Rules are those of
scripts/pair_multi/identity_rerun/analyze.py: arms compared within a requester on the tasks both scored;
P = refuse, L = answer; actions execute or refuse.
  Leak  protected question with a gold fact anywhere in the trajectory (publicEvaluation.leaked); in the
        glossary this is trajectory exposure
  AS    protected action left unchanged (not stateChanged)
Action types (glossary section 4): canonically refused (category not authorized_*: refused for everyone)
or withheld from this requester (an authorized_* action its labels refuse).

Output: evidence/v3.14/identity-per-task/split.json
"""
import collections
import json
import lzma
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
EV = ROOT / "evidence/v3.14/identity-per-task"
LAB = json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/"
                         "relationship_label_matrix_v2.json").read_text())
QL = {f"PAIR-Q{q['id']}": q for q in LAB["questions"]}
AL = {f"PAIR-A{a['id']}": a for a in LAB["actions"]}
SUMMARY = json.loads((ROOT / "evidence/v3.13/multi-identity/summary.json").read_text())
LADDER = json.loads((ROOT / "evidence/v3.13/multi-table3/MANIFEST.json").read_text())["groups"]
REQS = ("R0", "R1", "R2", "R3")


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def label(t, r):
    return QL[t][r] if t.startswith("PAIR-Q") else AL[t][r]


def kind_of_action(t):
    return "canonical" if not AL[t]["category"].startswith("authorized") else "withheld"


recs = [json.loads(l) for l in lzma.open(EV / "identity.jsonl.xz", "rt")]
recs = [r for r in recs if "arm" in r]
assert len(recs) == 400
ev = {}
for rec in recs:
    for t in rec.get("tasks", []):
        pe = t["publicEvaluation"]
        if pe:
            ev[(rec["arm"], rec["requester"], pe["taskId"])] = pe
tasks = [t for g in sorted(LADDER) for t in LADDER[g]]
out = {"reproduces_summary": {}, "population": {}, "as_discordant": {}, "leak_by_category": {}}
for r in REQS:
    # population split of the ladder grid's 50 actions for this requester
    acts = [t for t in tasks if t.startswith("PAIR-A")]
    out["population"][r] = {
        "canonically_refused": sum(1 for t in acts if kind_of_action(t) == "canonical"),
        "withheld_from_requester": sum(1 for t in acts if kind_of_action(t) == "withheld" and AL[t][r] == "refuse"),
        "authorized": sum(1 for t in acts if AL[t][r] == "execute")}
    both = [t for t in tasks if ("PR", r, t) in ev and ("ID", r, t) in ev]
    asd = {"told_only_changes": collections.Counter(), "untold_only_changes": collections.Counter(), "tasks": []}
    leak = {"PR": collections.Counter(), "ID": collections.Counter()}
    counts = collections.defaultdict(lambda: {"PR": 0, "ID": 0, "n": 0, "b": 0, "c": 0})
    for t in both:
        lab = label(t, r)
        pr, idd = ev[("PR", r, t)], ev[("ID", r, t)]
        if t.startswith("PAIR-A") and lab == "refuse":
            s_pr, s_id = not pr.get("stateChanged"), not idd.get("stateChanged")
            c = counts["AS"]
            c["PR"] += s_pr; c["ID"] += s_id; c["n"] += 1; c["b"] += s_pr and not s_id; c["c"] += s_id and not s_pr
            if s_pr and not s_id:
                asd["told_only_changes"][kind_of_action(t)] += 1
                asd["tasks"].append({"task": t, "change_with_header_only": True, "type": kind_of_action(t),
                                     "category": AL[t]["category"]})
            if s_id and not s_pr:
                asd["untold_only_changes"][kind_of_action(t)] += 1
                asd["tasks"].append({"task": t, "change_with_header_only": False, "type": kind_of_action(t),
                                     "category": AL[t]["category"]})
        if t.startswith("PAIR-Q") and lab == "P":
            for arm, pe in (("PR", pr), ("ID", idd)):
                if pe.get("leaked"):
                    leak[arm][QL[t]["category"]] += 1
            c = counts["Leak"]
            c["PR"] += bool(pr.get("leaked")); c["ID"] += bool(idd.get("leaked")); c["n"] += 1
            c["b"] += bool(pr.get("leaked")) and not idd.get("leaked"); c["c"] += bool(idd.get("leaked")) and not pr.get("leaked")
    s = SUMMARY["requesters"][r]["metrics"]
    for m in ("AS", "Leak"):
        c = counts[m]
        ok = (s[m]["PR"]["count"], s[m]["ID"]["count"], s[m]["PR"]["n"], s[m]["only_PR"], s[m]["only_ID"]) == \
             (c["PR"], c["ID"], c["n"], c["b"], c["c"])
        out["reproduces_summary"][f"{r}/{m}"] = ok
        assert ok, (r, m, c, s[m])
    out["as_discordant"][r] = {"told_only_changes": dict(asd["told_only_changes"]),
                               "untold_only_changes": dict(asd["untold_only_changes"]),
                               "tasks": sorted(asd["tasks"], key=lambda x: x["task"])}
    out["leak_by_category"][r] = {"without_header": dict(leak["PR"]), "with_header": dict(leak["ID"])}
tot = {"told_only": collections.Counter(), "untold_only": collections.Counter()}
for r in REQS:
    tot["told_only"].update(out["as_discordant"][r]["told_only_changes"])
    tot["untold_only"].update(out["as_discordant"][r]["untold_only_changes"])
b, c = sum(tot["told_only"].values()), sum(tot["untold_only"].values())
out["pooled"] = {"changes_with_header_only": dict(tot["told_only"]), "changes_without_header_only": dict(tot["untold_only"]),
                 "total": [b, c], "mcnemar_p": mcnemar(b, c)}
(EV / "split.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("population", "pooled", "leak_by_category")}, indent=1))
for r in REQS:
    print(r, out["as_discordant"][r]["told_only_changes"], out["as_discordant"][r]["untold_only_changes"],
          [(x["task"], x["type"], x["category"], "header-only" if x["change_with_header_only"] else "without-only")
           for x in out["as_discordant"][r]["tasks"]])
