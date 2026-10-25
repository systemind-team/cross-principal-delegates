#!/usr/bin/env python3
"""Document the relationship labels and build the label variants that need no new codes.

Inputs (frozen): the label file (evidence/v3.1/.../relationship_label_matrix_v2.json), the five annotation passes
and the campaign's majority file (evidence/v3.14/labels/annotation_passes.csv, qc_v3_majority.csv), and matrix
v1.1 (evidence/v3.14/pair-dataset/relationship_label_matrix_v1.1.json).

Checks (the script stops on a mismatch): the five-pass majority with the campaign's conservative tie rule equals
qc_v3_majority.csv and the label file on every annotated cell; Fleiss kappa reproduces 0.587 (questions) and
0.764 (actions).

Outputs, evidence/v3.14/labels/:
  documentation.json   Fleiss kappa overall, by requester and by category; vote splits by requester and category;
                       each pass's agreement with the majority; the tie-resolved (B -> P) cells; kappa without E
  original.json, S1.json, S2.json, S5.json, S6.json
                       {"labels": {task: {R0..R3: "protect" | "entitle" | null}}}; null = cell removed
    S1  without the 39 cells matrix v1.1 marked B (tie-resolved to P)
    S2  without the cells whose five-pass vote split 3-2
    S5  the four-pass majority without E on the annotated cells, 2-2 ties to P / REFUSE (counted)
    S6  without the 99 rows transcribed from v1.1 (Q101-Q200 except Q125)
"""
import collections
import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
L = ROOT / "evidence/v3.14/labels"
LAB = json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/"
                         "relationship_label_matrix_v2.json").read_text())
V11 = json.loads((ROOT / "evidence/v3.14/pair-dataset/relationship_label_matrix_v1.1.json").read_text())
REQS5 = ("R0", "R1", "R2", "R3", "R4")
REQS = ("R0", "R1", "R2", "R3")
PASSES = ("A1", "A2", "A3", "A4", "E")
CONSERVATIVE = {"qa": "P", "action": "REFUSE"}


def task_id(row):
    return f"PAIR-Q{row[1:]}" if row.startswith("Q") else f"PAIR-A{row[1:]}"


def fleiss(cells):
    """cells: list of label lists (same number of raters)."""
    n = len(cells[0])
    cats = sorted({x for c in cells for x in c})
    N = len(cells)
    p_j = {k: sum(c.count(k) for c in cells) / (N * n) for k in cats}
    P_i = [(sum(c.count(k) ** 2 for k in cats) - n) / (n * (n - 1)) for c in cells]
    Pbar = sum(P_i) / N
    Pe = sum(v * v for v in p_j.values())
    return (Pbar - Pe) / (1 - Pe) if Pe < 1 else float("nan")


def majority(labels, kind):
    c = collections.Counter(labels)
    top = c.most_common()
    tie = len(top) > 1 and top[0][1] == top[1][1]
    return (CONSERVATIVE[kind] if tie else top[0][0]), tie, c


def main():
    QL = {f"PAIR-Q{q['id']}": q for q in LAB["questions"]}
    AL = {f"PAIR-A{a['id']}": a for a in LAB["actions"]}
    cat = {**{t: q["category"] for t, q in QL.items()}, **{t: a["category"] for t, a in AL.items()}}
    passes = {}
    for rec in csv.DictReader(open(L / "annotation_passes.csv")):
        passes[(task_id(rec["row"]), rec["requester"])] = (rec["kind"], [rec[p] for p in PASSES])
    qc = {(task_id(r["row"]), r["requester"]): r for r in csv.DictReader(open(L / "qc_v3_majority.csv"))}
    # checks
    bad = []
    for (t, r), (kind, labs) in passes.items():
        m, tie, _ = majority(labs, kind)
        if qc[(t, r)]["label"] != m:
            bad.append(("qc", t, r))
        lab = (QL[t][r] if t in QL else {"execute": "EXECUTE", "refuse": "REFUSE"}[AL[t][r]])
        if lab != m:
            bad.append(("label file", t, r, lab, m))
    if bad:
        raise SystemExit(f"{len(bad)} majority mismatches: {bad[:8]}")
    k_qa = fleiss([labs for (t, r), (k, labs) in passes.items() if k == "qa"])
    k_act = fleiss([labs for (t, r), (k, labs) in passes.items() if k == "action"])
    assert round(k_qa, 3) == 0.587 and round(k_act, 3) == 0.764, (k_qa, k_act)
    doc = {"annotated_rows": len({t for t, _ in passes}), "annotated_cells": len(passes),
           "fleiss_kappa": {"questions": k_qa, "actions": k_act}, "by_requester": {}, "by_category": {},
           "vote_splits": {}, "agreement_with_majority": {}, "fleiss_kappa_without_E": {}}
    for kind in ("qa", "action"):
        for r in REQS5:
            cells = [labs for (t, rr), (k, labs) in passes.items() if k == kind and rr == r]
            doc["by_requester"][f"{kind}/{r}"] = {"kappa": fleiss(cells), "cells": len(cells)}
        for c in sorted({cat[t] for (t, _), (k, _) in passes.items() if k == kind}):
            cells = [labs for (t, rr), (k, labs) in passes.items() if k == kind and cat[t] == c and rr in REQS]
            doc["by_category"][f"{kind}/{c}"] = {"kappa_R0_R3": fleiss(cells), "cells": len(cells)}
        no_e = [labs[:4] for (t, r), (k, labs) in passes.items() if k == kind]
        doc["fleiss_kappa_without_E"][kind] = fleiss(no_e)
    for (t, r), (kind, labs) in passes.items():
        top = collections.Counter(labs).most_common(1)[0][1]
        doc["vote_splits"].setdefault(f"{r}/{cat[t]}", collections.Counter())[f"{top}-{5 - top}"] += 1
    doc["vote_splits"] = {k: dict(v) for k, v in sorted(doc["vote_splits"].items())}
    for i, p in enumerate(PASSES):
        agree = sum(labs[i] == majority(labs, kind)[0] for (kind, labs) in passes.values())
        doc["agreement_with_majority"][p] = agree / len(passes)
    # tie-resolved cells of v1.1
    b_cells = [(f"PAIR-Q{row['id']}", r) for row in V11["labels"] for r in REQS5 if row.get(r) == "B"]
    doc["tie_resolved_B_cells"] = {"total": len(b_cells),
                                   "by_requester": dict(collections.Counter(r for _, r in b_cells))}
    transcribed = [f"PAIR-Q{i}" for i in range(101, 201) if i != 125]
    # variants
    def base():
        out = {}
        for t, q in QL.items():
            out[t] = {r: ("protect" if q[r] == "P" else "entitle") for r in REQS}
        for t, a in AL.items():
            out[t] = {r: ("protect" if a[r] == "refuse" else "entitle") for r in REQS}
        return out
    variants = {"original": base()}
    s1 = base()
    for t, r in b_cells:
        if r in REQS:
            assert s1[t][r] == "protect"
            s1[t][r] = None
    variants["S1"] = s1
    s2 = base()
    n32 = collections.Counter()
    for (t, r), (kind, labs) in passes.items():
        if r in REQS and collections.Counter(labs).most_common(1)[0][1] == 3:
            s2[t][r] = None
            n32[r] += 1
    variants["S2"] = s2
    s5 = base()
    ties5, changed5 = collections.Counter(), collections.Counter()
    for (t, r), (kind, labs) in passes.items():
        if r not in REQS:
            continue
        m, tie, _ = majority(labs[:4], kind)
        ties5[r] += tie
        new = "protect" if m in ("P", "REFUSE") else "entitle"
        changed5[r] += new != s5[t][r]
        s5[t][r] = new
    variants["S5"] = s5
    s6 = base()
    for t in transcribed:
        for r in REQS:
            s6[t][r] = None
    variants["S6"] = s6
    doc["variant_counts"] = {"S1_removed": sum(1 for t, r in b_cells if r in REQS),
                             "S2_removed_3_2_cells": dict(n32), "S5_ties_to_protect": dict(ties5),
                             "S5_cells_changed": dict(changed5), "S6_removed_rows": len(transcribed)}
    for name, labs in variants.items():
        (L / f"{name}.json").write_text(json.dumps({"variant": name, "labels": labs}, indent=0, sort_keys=True) + "\n")
    (L / "documentation.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("fleiss_kappa", "fleiss_kappa_without_E", "agreement_with_majority",
                                          "tie_resolved_B_cells", "variant_counts")}, indent=1))


if __name__ == "__main__":
    main()
