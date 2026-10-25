#!/usr/bin/env python3
"""P2-3 acceptance tests on P1-6's frozen sessions: the O2 action contrast, the gate, and the fresh-fact
sensitivity. It runs classify_adaptive.mjs and analyze_adaptive.py and asserts:
  C1n vs A0n O2 is 44 pairs, 43 adaptive-only, 0 control-only (no dropped actions); O2 at k=1 and the 56
      rest actions are non-empty.
  with no manifest, and with a wrong sha, the gate fails, no top-level `primary` is emitted, every `counts`
      is null, and no "counts": true appears; with a matching sha the primary is emitted and P1 counts.
  question_task_writes is reported (0 on P1-6); the fresh-fact sensitivity gives C1n/C3c 93/96 while the
      primary classOf rule gives 95/98.
No model calls. Run from the worktree root.

Usage: python3 scripts/pair_multi/spoof/adaptive/test_analyze_p16.py
"""
import hashlib
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
ADIR = ROOT / "scripts/pair_multi/spoof/adaptive"
EVAL = ROOT / "evidence/v3.14/multi-spoof/inputs/evaluator.ts"
Q = ROOT / "evidence/v3.14/multi-spoof/inputs/questions.json"
SESS = ROOT / "evidence/v3.14/multi-spoof/sessions.jsonl.xz"


def classify(tmp):
    per = tmp / "perT.jsonl"
    with open(per, "w") as f:
        p1 = subprocess.Popen(["xz", "-dc", str(SESS)], stdout=subprocess.PIPE)
        subprocess.run(["node", str(ADIR / "classify_adaptive.mjs"), str(EVAL), str(Q)],
                       stdin=p1.stdout, stdout=f, check=True)
        p1.wait()
    return per


def analyze(per, manifest=None):
    cmd = ["python3", str(ADIR / "analyze_adaptive.py"), "--perreply", str(per),
           "--adaptive-arm", "C1n", "--control-arm", "A0n"]
    if manifest:
        cmd += ["--manifest", str(manifest)]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        per = classify(tmp)
        rows = [json.loads(l) for l in open(per)]

        # V7: fresh-fact differs from the primary classOf rule
        import collections
        REL = json.load(open(ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json"))
        G = json.load(open(ROOT / "evidence/v3.13/multi-table3/MANIFEST.json"))["groups"]
        QL = {f"PAIR-Q{r['id']}": r for r in REL["questions"]}
        O1 = {t for g in G for t in G[g] if t in QL and QL[t]["R1"] == "L" and QL[t]["R0"] == "P" and t != "PAIR-Q324"}
        prim, fresh = collections.Counter(), collections.Counter()
        for r in rows:
            if r["kind"] == "qa" and r["task"] in O1:
                if r.get("first_leak_turn") is not None:
                    prim[r["arm"]] += 1
                if r.get("first_leak_turn_newleak") is not None:
                    fresh[r["arm"]] += 1
        assert prim["C1n"] == 95 and prim["C3c"] == 98, ("primary", dict(prim))
        assert fresh["C1n"] == 93 and fresh["C3c"] == 96, ("fresh", dict(fresh))
        print(" ok: primary 95/98, fresh-fact 93/96")

        # passing gate
        self_sha = hashlib.sha256((ADIR / "analyze_adaptive.py").read_bytes()).hexdigest()
        man = tmp / "man.json"
        man.write_text(json.dumps({"full_run": {"go": "dry"}, "analysis": {"sha256": self_sha}}))
        d = analyze(per, man)
        assert d["preregistration_gate"]["pass"] is True
        o2 = d["o2_gated"]
        assert o2["pairs"] == 44 and o2["adaptive_only"] == 43 and o2["control_only"] == 0 and o2["dropped_missing"] == 0, o2
        assert d["o2_k1_matched"]["pairs"] == 44, d["o2_k1_matched"]
        assert d["rest_actions_descriptive"]["pairs"] == 56, d["rest_actions_descriptive"]
        assert d["question_task_writes"] == {"adaptive": 0, "control": 0}, d.get("question_task_writes")
        assert d["primary"]["P1 O1 total leak within K"]["counts"] is True
        print(" ok: O2 44 pairs 43:0; O2@k1 44; rest actions 56; passing gate emits P1 counts")

        # Question-task writes are 0 of 102 (all 102 writes name PAIR-A tasks); every executed action is
        # dated at turn 1 on P1-6 (one request per action, state changed).
        qrows = [r for r in rows if r["kind"] == "qa"]
        arows = [r for r in rows if r["kind"] == "action"]
        assert sum(r["question_task_writes"] for r in qrows) == 0, "question-task writes must be 0 of 102"
        dated = [r for r in arows if r.get("state_changed") and r.get("first_write_turn") == 1]
        assert len(dated) == 102, (len(dated), "state-changed actions dated at turn 1")
        print(f" ok: 0 question-task writes; {len(dated)} executed actions dated at turn 1")

        # A failed gate DROPS the primary/O2/missingness blocks — no pairs or p-values anywhere.
        for manifest in (None, "deadbeef"):
            if manifest is None:
                dd = analyze(per, None)
            else:
                bad = tmp / "bad.json"
                bad.write_text(json.dumps({"full_run": {"go": "dry"}, "analysis": {"sha256": manifest}}))
                dd = analyze(per, bad)
            assert dd["preregistration_gate"]["pass"] is False
            for k in ("primary", "o2_gated", "missingness_bounds_P1"):
                assert k not in dd, f"{k} must be dropped on a failed gate"
            assert "withheld_until_gate" not in dd, "the dropped blocks must not be relocated, with their numbers, under withheld_until_gate"
            assert dd.get("withheld") == ["primary", "o2_gated", "missingness_bounds_P1"]
            assert '"counts": true' not in json.dumps(dd), "no confirmatory counts on a failed gate"
        print(" ok: failed gate drops primary/O2/missingness entirely (names only, no pairs or p-values)")
    print("all P1-6 acceptance tests passed")


if __name__ == "__main__":
    main()
