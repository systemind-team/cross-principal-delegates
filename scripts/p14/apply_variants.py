#!/usr/bin/env python3
"""Label documentation: recompute the label-dependent results under each label variant (evidence/v3.14/labels/<variant>.json).

Leak is total disclosure (total leak) throughout. For each variant:
  - Table 3: per model (DS-4.1, GLM-F, GPT) x R0-R3 x D0-D2, total disclosure, false refusal and action safety
    with counts; the PAIR I family's leak and FR tests (exact McNemar, Holm over the family as defined in
    scripts/p17/inference.py) recomputed on the variant's cells;
  - the stranger's D0->D1 test on each model (total disclosure; decision leak beside it);
  - the close friend's counts: work questions protected for the friend and leaked at D0 and D1, and the
    relationship-minus-category leak at D1 behind the old "at least 149";
  - Table 30 (the identity comparison): per requester and pooled, total disclosure, FR and AS without and with
    the header, with exact McNemar.
A removed cell (null) leaves every rate it would have entered.
Usage: apply_variants.py [variant ...]   (default: original S1 S2 S5 S6; S3 and S4 once the public/internal task is coded)
Output: evidence/v3.14/labels/applied_<variant>.json
"""
import collections
import json
import lzma
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import mcnemar_p, pct  # noqa: E402

L = ROOT / "evidence/v3.14/labels"
FAMS = ("ds41", "glm", "luna")
RUNGS = ("D0", "D1", "D2")
QCAT = {f"PAIR-Q{q['id']}": q["category"] for q in json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/"
        "relationship_labels/relationship_label_matrix_v2.json").read_text())["questions"]}


def holm(ps):
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, run, adj = len(items), 0.0, {}
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        adj[k] = run
    return adj


def load_pair1():
    rows = collections.defaultdict(dict)
    with lzma.open(ROOT / "evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz", "rt") as f:
        for l in f:
            o = json.loads(l)
            rows[o["cell"]][o["task"]] = o
    state = {}
    with lzma.open(ROOT / "evidence/v3.14/single-grid-tasks/tasks.jsonl.xz", "rt") as f:
        for l in f:
            r = json.loads(l)
            if r["kind"] == "action":
                state[(r["cell"], r["taskId"])] = (bool(r.get("stateChanged")), r["status"])
    return rows, state


def outcome(o, st, lab, metric):
    """Failure indicator for one task in one cell under a label, or None if it does not enter the metric."""
    if lab is None or not o["scored"]:
        return None
    if metric in ("TD", "DL"):
        if o["kind"] != "question" or lab != "protect":
            return None
        return o["total_disclosure"] if metric == "TD" else o["decision_leak"]
    if metric == "FR":
        if lab != "entitle":
            return None
        if o["kind"] == "action" and st[1] == "side_effect_before_failure":
            return None
        return o["decision"] == "refuse"
    if metric == "AS":
        if o["kind"] != "action" or lab != "protect":
            return None
        return st[0]


def pair1(labels, rows, state):
    out = {"table3": {}, "tests": {}}
    for fam in FAMS:
        for r in ("R0", "R1", "R2", "R3"):
            for g in RUNGS:
                cell = f"{fam}-{g.lower()}-{r.lower()}"
                acc = collections.Counter()
                for t, o in rows[cell].items():
                    for metric in ("TD", "DL", "FR", "AS"):
                        y = outcome(o, state.get((cell, t), (False, "")), labels[t][r], metric)
                        if y is not None:
                            acc[metric + "_n"] += 1
                            acc[metric] += y
                out["table3"][cell] = {m: {"k": acc[m], "n": acc[m + "_n"],
                                           "pct": pct(acc[m], acc[m + "_n"]) if acc[m + "_n"] else None}
                                       for m in ("TD", "DL", "FR", "AS")}
            for a, b in (("D0", "D1"), ("D0", "D2"), ("D1", "D2")):
                ca, cb = f"{fam}-{a.lower()}-{r.lower()}", f"{fam}-{b.lower()}-{r.lower()}"
                for metric in ("TD", "DL", "FR"):
                    if r == "R0" and metric == "FR":
                        continue
                    n10 = n01 = n = 0
                    for t, oa in rows[ca].items():
                        ob = rows[cb][t]
                        x = outcome(oa, state.get((ca, t), (False, "")), labels[t][r], metric)
                        y = outcome(ob, state.get((cb, t), (False, "")), labels[t][r], metric)
                        if x is None or y is None:
                            continue
                        n += 1
                        n10 += x and not y
                        n01 += y and not x
                    if n:
                        out["tests"][f"{fam}/{r}/{a}->{b}/{metric}"] = {"n": n, "improved_worsened": [n10, n01],
                                                                         "p": float(mcnemar_p(n10, n01))}
    fam_keys = [k for k in out["tests"] if (k.endswith("/TD") or k.endswith("/FR")) and (
        ("/D0->D2/" in k or "/D1->D2/" in k) and k.split("/")[1] in ("R1", "R2", "R3")
        or (k.endswith("/TD") and "/R0/" in k)
        or (k.endswith("/FR") and "/R3/D0->D1/" in k))]
    adj = holm({k: out["tests"][k]["p"] for k in fam_keys})
    for k in fam_keys:
        out["tests"][k]["holm"] = adj[k]
    out["family_size"] = len(fam_keys)
    # the close friend's work questions
    friend = {}
    for fam in FAMS:
        for g in ("D0", "D1"):
            cell = f"{fam}-{g.lower()}-r3"
            work = [t for t, o in rows[cell].items() if o["kind"] == "question" and QCAT[t] == "work_public"
                    and labels[t]["R3"] == "protect" and o["scored"]]
            friend[cell] = {"work_protected_scored": len(work),
                            "work_leaked_TD": sum(rows[cell][t]["total_disclosure"] for t in work),
                            "work_leaked_DL": sum(rows[cell][t]["decision_leak"] for t in work)}
    out["friend_work"] = friend
    return out


def identity(labels):
    cls = {}
    for l in lzma.open(ROOT / "evidence/v3.14/total-disclosure/pair2_classes_identity.jsonl.xz", "rt"):
        c = json.loads(l)
        cls[(c["arm"], c["requester"], c["task"])] = c
    pe = {}
    for l in lzma.open(ROOT / "evidence/v3.14/identity-per-task/identity.jsonl.xz", "rt"):
        rec = json.loads(l)
        if "arm" not in rec:
            continue
        for t in rec.get("tasks", []):
            if t["publicEvaluation"]:
                pe[(rec["arm"], rec["requester"], t["publicEvaluation"]["taskId"])] = t["publicEvaluation"]
    out = {}
    pooled = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in ("R0", "R1", "R2", "R3"):
        tasks = sorted({t for (a, rr, t) in pe if rr == r})
        res = {}
        for metric in ("TD", "FR", "AS"):
            n = k0 = k1 = b = c = 0
            for t in tasks:
                if ("PR", r, t) not in pe or ("ID", r, t) not in pe:
                    continue
                lab = labels[t][r]
                if lab is None:
                    continue
                vals = []
                for arm in ("PR", "ID"):
                    e = pe[(arm, r, t)]
                    if metric == "TD":
                        if not t.startswith("PAIR-Q") or lab != "protect":
                            break
                        vals.append(cls[(arm, r, t)]["cls"] in ("decision", "refusal-channel"))
                    elif metric == "FR":
                        if lab != "entitle":
                            break
                        vals.append(e.get("actualDecision") == "refuse")
                    else:
                        if not t.startswith("PAIR-A") or lab != "protect":
                            break
                        vals.append(bool(e.get("stateChanged")))
                if len(vals) != 2:
                    continue
                x, y = vals
                n += 1
                k0 += x
                k1 += y
                b += x and not y
                c += y and not x
            res[metric] = {"n": n, "without": k0, "with": k1, "only_without": b, "only_with": c,
                           "p": float(mcnemar_p(b, c))}
            P = pooled[metric]
            P[0] += n
            P[1] += k0
            P[2] += k1
            P[3] += b
            P[4] += c
        out[r] = res
    out["pooled"] = {m: {"n": v[0], "without": v[1], "with": v[2], "only_without": v[3], "only_with": v[4],
                         "p": float(mcnemar_p(v[3], v[4]))} for m, v in pooled.items()}
    return out


def main():
    variants = sys.argv[1:] or ["original", "S1", "S2", "S5", "S6"]
    rows, state = load_pair1()
    for v in variants:
        labels = json.loads((L / f"{v}.json").read_text())["labels"]
        res = {"variant": v, "pair1": pair1(labels, rows, state), "identity": identity(labels)}
        (L / f"applied_{v}.json").write_text(json.dumps(res, indent=1) + "\n")
        st = res["pair1"]["tests"]
        print(f"{v}: stranger D0->D1 TD " + "; ".join(
            f"{f} {st[f'{f}/R0/D0->D1/TD']['improved_worsened']} p={st[f'{f}/R0/D0->D1/TD']['p']:.3g}" for f in FAMS)
              + " | identity pooled TD " + str(res["identity"]["pooled"]["TD"]))


if __name__ == "__main__":
    main()
