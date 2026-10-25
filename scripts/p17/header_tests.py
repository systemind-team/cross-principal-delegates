#!/usr/bin/env python3
"""The corrected inference for the header comparison and the header ladder: task-level McNemar and group-level sign-flip tests.

The design gives the identity comparison (Table 30) and the told ladder (Table 31) the PAIR II treatment:
tasks sit three to a session and the same 50 groups are asked by every requester, so each test is also run with the
session group as the unit (exact sign-flip over groups of each group's improved - worsened count, with its floor
2/2^m and m, the number of non-zero groups; scripts/p17/inference.py's signflip). The pooled tests sum each group's
count over the requesters.

Header comparison (relationship labels; `evidence/v3.14/identity-per-task/identity.jsonl.xz` and the leak classes
`evidence/v3.14/total-disclosure/pair2_classes_identity.jsonl.xz`), without (PR) against with (ID) the header, on
tasks both arms scored:
  TL  protected questions with a total leak (decision or refusal-channel class);
  WTE protected questions with a whole-trajectory exposure (the harness's `leaked` flag, Table 30's old "Leak");
  FR  entitled questions and authorized actions refused;   AS  protected actions that changed state;
  U   entitled questions not answered with the gold facts; AU  authorized actions not completed correctly.
Header ladder (category labels; `pair2_classes_told.jsonl.xz`, `pair2_classes_ladder.jsonl.xz` and the frozen pairs of
`evidence/v3.13/multi-told/pairs.json`): the total-leak contrasts of pair2_td.json.
Output: evidence/v3.14/p17/header_tests.json
"""
import collections
import json
import lzma
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
sys.path.insert(0, str(ROOT / "scripts" / "p17"))
from halfup import mcnemar_p  # noqa: E402
from inference import signflip  # noqa: E402

TDIR = ROOT / "evidence/v3.14/total-disclosure"
LAB = json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/"
                         "relationship_label_matrix_v2.json").read_text())
QL = {f"PAIR-Q{q['id']}": q for q in LAB["questions"]}
AL = {f"PAIR-A{a['id']}": a for a in LAB["actions"]}


def test(pairs):
    """pairs: list of (group, x, y) failure indicators at a and b. Returns McNemar and group sign-flip."""
    n10 = sum(1 for g, x, y in pairs if x and not y)
    n01 = sum(1 for g, x, y in pairs if y and not x)
    per = collections.Counter()
    for g, x, y in pairs:
        per[g] += (x and not y) - (y and not x)
    p, floor, m = signflip([per[g] for g in sorted(per)])
    n = len(pairs)
    return {"n": n, "a": sum(x for _, x, _ in pairs), "b": sum(y for _, _, y in pairs),
            "improved_worsened": [n10, n01], "mcnemar_p": float(mcnemar_p(n10, n01)),
            "signflip_p": p, "floor": floor, "nonzero_groups": m, "groups": len(per)}


def identity():
    cls = {(c["arm"], c["requester"], c["task"]): c
           for c in map(json.loads, lzma.open(TDIR / "pair2_classes_identity.jsonl.xz", "rt"))}
    pe, grp = {}, {}
    for l in lzma.open(ROOT / "evidence/v3.14/identity-per-task/identity.jsonl.xz", "rt"):
        rec = json.loads(l)
        if "arm" not in rec:
            continue
        for t in rec.get("tasks", []):
            if t["publicEvaluation"]:
                k = (rec["arm"], rec["requester"], t["publicEvaluation"]["taskId"])
                pe[k] = t["publicEvaluation"]
                grp[k] = rec["group"]

    def outcome(arm, req, t, metric):
        e = pe.get((arm, req, t))
        if e is None:
            return None
        if t.startswith("PAIR-Q"):
            prot = QL[t][req] == "P"
            if metric == "TL" and prot:
                return cls[(arm, req, t)]["cls"] in ("decision", "refusal-channel")
            if metric == "WTE" and prot:
                return bool(e.get("leaked"))
            if metric == "FR" and not prot:
                return e.get("actualDecision") == "refuse"
            if metric == "U" and not prot:
                return not bool(e.get("factMatch"))
            return None
        prot = AL[t][req] == "refuse"
        if metric == "AS" and prot:
            return bool(e.get("stateChanged"))
        if metric == "FR" and not prot:
            return e.get("actualDecision") == "refuse"
        if metric == "AU" and not prot:
            return not bool(e.get("stateCorrect"))
        return None

    out = {}
    for metric in ("TL", "WTE", "FR", "AS", "U", "AU"):
        pooled = []
        for req in ("R0", "R1", "R2", "R3"):
            pairs = []
            for t in sorted({t for (a, r, t) in pe if r == req}):
                x, y = outcome("PR", req, t, metric), outcome("ID", req, t, metric)
                if x is None or y is None:
                    continue
                assert grp[("PR", req, t)] == grp[("ID", req, t)]
                pairs.append((grp[("PR", req, t)], x, y))
            if pairs:
                out[f"{req}/{metric}"] = test(pairs)
                pooled += pairs
        out[f"pooled/{metric}"] = test(pooled)
    # checks against the frozen summaries (scripts/p11/pair2_td.py; evidence/v3.13/multi-identity/summary.json)
    td = json.loads((TDIR / "pair2_td.json").read_text())["identity"]
    for req in ("R0", "R1", "R2", "R3", "pooled"):
        v = out[f"{req}/TL"]
        assert (v["a"], v["b"], v["n"], *v["improved_worsened"]) == (
            td[req]["TD_without"], td[req]["TD_with"], td[req]["n"], td[req]["only_without"], td[req]["only_with"]), req
    s = json.loads((ROOT / "evidence/v3.13/multi-identity/summary.json").read_text())
    for key in ("FR", "AS"):   # the summary counts FR as failures and AS as successes (actions left unchanged)
        m = s["pooled"][key]
        v = out[f"pooled/{key}"]
        want = (m["only_PR"], m["only_ID"]) if key == "FR" else (m["only_ID"], m["only_PR"])
        assert tuple(v["improved_worsened"]) == want, (key, v["improved_worsened"], m)
    return out


def header_ladder():
    told = [json.loads(l) for l in lzma.open(TDIR / "pair2_classes_told.jsonl.xz", "rt")]
    ladder = [json.loads(l) for l in lzma.open(TDIR / "pair2_classes_ladder.jsonl.xz", "rt")]
    cls = {}
    for r in told:
        cls[(f"{r['arm']}-{r['rung']}", r["requester"], r["group"], r["task"])] = r["cls"]
    for r in ladder:
        if r["arm"] == "DS":
            cls[(f"AZ-{r['rung']}", r["requester"], r["group"], r["task"])] = r["cls"]
    pairs = [p for p in json.loads((ROOT / "evidence/v3.13/multi-told/pairs.json").read_text()) if "DL" in p["AZ-D0"]]
    out = {}
    for a, b in (("CTRL-D2", "TOLD-D2"), ("AZ-D2", "CTRL-D2"), ("TOLD-D0", "TOLD-D2"), ("AZ-D0", "TOLD-D0"),
                 ("AZ-D1", "TOLD-D1"), ("AZ-D2", "TOLD-D2")):
        pr = []
        for p in pairs:
            x = cls[(a, p["requester"], p["group"], p["task"])] in ("decision", "refusal-channel")
            y = cls[(b, p["requester"], p["group"], p["task"])] in ("decision", "refusal-channel")
            pr.append((p["group"], x, y))
        out[f"{a} vs {b}/TL"] = test(pr)
    td = json.loads((TDIR / "pair2_td.json").read_text())["header_ladder"]["tests"]
    for k, v in out.items():
        a, b = k[:-3].split(" vs ")
        assert tuple(v["improved_worsened"]) == (td[f"{a} vs {b}"][f"only_{a}"], td[f"{a} vs {b}"][f"only_{b}"]), k
    # FR, AS, U and AU from the frozen per-task outcomes (failure indicators: FR refused, AS changed state, U and AU not
    # correct), checked against the discordant counts of evidence/v3.13/multi-told/summary.json
    allp = json.loads((ROOT / "evidence/v3.13/multi-told/pairs.json").read_text())
    S = json.loads((ROOT / "evidence/v3.13/multi-told/summary.json").read_text())["pooled"]["tests"]
    for metric in ("FR", "AS", "U"):
        for a, b in (("CTRL-D2", "TOLD-D2"), ("AZ-D2", "CTRL-D2"), ("TOLD-D0", "TOLD-D2"), ("AZ-D0", "TOLD-D0"),
                     ("AZ-D1", "TOLD-D1"), ("AZ-D2", "TOLD-D2")):
            pr = []
            for p in allp:
                if metric not in p[a]:
                    continue
                x, y = p[a][metric], p[b][metric]
                if metric in ("AS", "U"):   # the summary stores successes (unchanged, correct); test failures
                    x, y = not x, not y
                pr.append((p["group"], bool(x), bool(y)))
            v = test(pr)
            ref = S.get(metric, {}).get(f"{a} vs {b}")
            if ref is not None:
                got = tuple(v["improved_worsened"])
                want = (ref["only_" + a], ref["only_" + b]) if metric == "FR" else (ref["only_" + b], ref["only_" + a])
                assert got == want, (metric, a, b, got, want)
            out[f"{a} vs {b}/{metric}"] = v
    return out


if __name__ == "__main__":
    res = {"header_comparison": identity(), "header_ladder": header_ladder()}
    (ROOT / "evidence/v3.14/p17/header_tests.json").write_text(json.dumps(res, indent=1) + "\n")
    for part, tests in res.items():
        for k, v in tests.items():
            print(f"{part:17s} {k:24s} {v['a']}/{v['n']} -> {v['b']}/{v['n']}  {v['improved_worsened'][0]}:{v['improved_worsened'][1]}"
                  f"  McNemar {v['mcnemar_p']:.3g}  sign-flip {v['signflip_p']:.3g} (m = {v['nonzero_groups']}, floor {v['floor']:.2g})")
