#!/usr/bin/env python3
"""The public/internal codes x the 529-trace review: how the category-public leaks of Appendix C's "The labels and the policy disagree in
three named places" paragraph (appendix/instruments_full.tex) fall across the two LLM coders' work_public split.

The leaks are those of the review's stratum S1 (90 sampled leaks scored under the D2 family) on questions whose
category is work_public and whose category label answers them for everyone: scripts/single_grid/review_summary.py's
"label_public" rule, counted in evidence/v3.13/single-grid/review/summary.json (52; by model 19, 15, 18). The split
is the public/internal task's (evidence/v3.14/coding-p1-4): two LLM coders coded each of the 200 work_public questions PUBLIC or INTERNAL,
an "unclear:" line being INTERNAL by the rule.

Checks before any count: the coding key matches the sha256 in packets/MANIFEST.json; the frozen answers reproduce
results.json's agreement table, unclear counts and both public lists (S3, S3-bound); the review packets reproduce
summary.json's S1 n, label_public and its split by model; every one of these leaks is on one of the 200 coded questions.
Counts: the leaks and their distinct questions by the coders' reading (both PUBLIC, both INTERNAL, contested), the
INTERNAL ones split by whether either coder flagged the line "unclear:" (the S3-bound set), and each class by
responder model, requester and rung.
Output: evidence/v3.14/coding-p1-4/work_public_leaks.json.
"""
import collections
import csv
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
C4 = ROOT / "evidence/v3.14/coding-p1-4"
REV = ROOT / "evidence/v3.13/single-grid/review"
MODELS = ("DeepSeek", "GLM", "GPT-5.6")


def read_answers(path):
    """As scripts/p14/p14_run.py reads them: code -> (decision, flagged unclear)."""
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            code = row["code"].strip()
            dec = (row.get("decision") or "").strip().upper()
            assert code not in out and dec in ("PUBLIC", "INTERNAL"), (path, code, dec)
            reason = (row.get("reason") or "").strip().strip('"').strip()
            out[code] = (dec, reason.lower().startswith("unclear:"))
    return out


def qnum(t):
    return int(t.split("Q", 1)[1])


def main():
    manifest = json.loads((C4 / "packets" / "MANIFEST.json").read_text())
    kp = C4 / manifest["key"]["path"]
    assert hashlib.sha256(kp.read_bytes()).hexdigest() == manifest["key"]["sha256"], "the coding key differs from MANIFEST"
    key = json.loads(kp.read_text())["lines"]
    A, B = read_answers(C4 / "answers" / "A" / "WP.csv"), read_answers(C4 / "answers" / "B" / "WP.csv")
    assert set(A) == set(B) == set(key)
    real = {c: v for c, v in key.items() if not v["planted"]}
    split = {}
    for c, v in real.items():
        a, b = A[c][0] == "PUBLIC", B[c][0] == "PUBLIC"
        split[v["task"]] = {"reading": "both PUBLIC" if a and b else "both INTERNAL" if not (a or b) else "contested",
                            "unclear": A[c][1] or B[c][1]}
    assert len(split) == len(real) == 200
    res = json.loads((C4 / "results.json").read_text())
    tab = collections.Counter(s["reading"] for s in split.values())
    ag = res["agreement"]["table"]
    assert tab["both PUBLIC"] == ag["both_public"] and tab["both INTERNAL"] == ag["both_internal"]
    assert tab["contested"] == ag["A_public_B_internal"] + ag["A_internal_B_public"]
    assert res["agreement"]["unclear"] == {"A": sum(A[c][1] for c in real), "B": sum(B[c][1] for c in real)}
    public = sorted((t for t, s in split.items() if s["reading"] == "both PUBLIC"), key=qnum)
    bound = sorted((t for t, s in split.items() if s["reading"] != "both INTERNAL" or s["unclear"]), key=qnum)
    assert public == res["relabel"]["public_S3_tasks"] and bound == res["relabel"]["public_S3_bound_tasks"]

    packets = [json.loads(l) for l in open(REV / "packets.jsonl")]
    summary = json.loads((REV / "summary.json").read_text())
    s1 = [p for p in packets if p["stratum"] == "S1_explicit_leak"]
    pub = [p for p in s1 if p.get("category") == "work_public" and p.get("category_expected") == "answer"]
    assert len(s1) == summary["S1_explicit_leak"]["n"] and len(pub) == summary["S1_explicit_leak"]["label_public"]
    for m in MODELS:
        assert sum(p["responder_model"] == m for p in pub) == summary["by_model"][f"S1_explicit_leak|{m}"]["label_public"]
    assert all(p["task_id"] in split for p in pub), "a leak outside the 200 coded work_public questions"

    def block(rows):
        return {"leaks": len(rows), "questions": len({p["task_id"] for p in rows}),
                "by_model": {m: sum(p["responder_model"] == m for p in rows) for m in MODELS},
                "by_requester": dict(sorted(collections.Counter(p["requester"] for p in rows).items())),
                "by_rung": dict(sorted(collections.Counter(p["policy"] for p in rows).items())),
                "question_ids": sorted({p["task_id"] for p in rows}, key=qnum)}
    classes = {r: [p for p in pub if split[p["task_id"]]["reading"] == r]
               for r in ("both PUBLIC", "both INTERNAL", "contested")}
    out = {
        "split": {"questions": len(split), "both_PUBLIC": tab["both PUBLIC"], "both_INTERNAL": tab["both INTERNAL"],
                  "contested": tab["contested"], "unclear_either": sum(s["unclear"] for s in split.values()),
                  "S3_public_tasks": public, "S3_bound_tasks": bound,
                  "reproduces": "results.json agreement table, unclear counts, public_S3_tasks, public_S3_bound_tasks"},
        "review": {"traces": len(packets), "S1_sampled_leaks": len(s1),
                   "S1_rungs": dict(sorted(collections.Counter(p["policy"] for p in s1).items())),
                   "category_public_leaks": len(pub),
                   "category_public_by_model": {m: sum(p["responder_model"] == m for p in pub) for m in MODELS},
                   "category_public_relationship_label": dict(collections.Counter(p["relationship_expected"] for p in pub)),
                   "reproduces": "summary.json S1 n, label_public and label_public by model"},
        "leaks_by_reading": {r: block(rows) for r, rows in classes.items()},
        "internal_by_unclear": {
            "flagged unclear by either coder": block([p for p in classes["both INTERNAL"] if split[p["task_id"]]["unclear"]]),
            "not flagged": block([p for p in classes["both INTERNAL"] if not split[p["task_id"]]["unclear"]])},
        "all": block(pub),
    }
    (C4 / "work_public_leaks.json").write_text(json.dumps(out, indent=1) + "\n")
    brief = {r: {k: v for k, v in b.items() if k != "question_ids"} for r, b in out["leaks_by_reading"].items()}
    print(json.dumps({"split": {k: v for k, v in out["split"].items() if not k.endswith("tasks")},
                      "review": out["review"], "leaks_by_reading": brief,
                      "internal_by_unclear": {k: {kk: vv for kk, vv in v.items() if kk != "question_ids"}
                                              for k, v in out["internal_by_unclear"].items()}}, indent=1))


if __name__ == "__main__":
    main()
