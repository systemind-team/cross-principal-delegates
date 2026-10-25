#!/usr/bin/env python3
"""The public/internal coding task after the codes arrive: run exactly what evidence/v3.14/coding-p1-4/PREREGISTRATION.md specifies.

Written and committed before the coders' answers were opened (2026-10-05). Steps:
 1. read both annotators' answers (code,decision,reason) and the hidden key; every code once, decisions in
    {PUBLIC, INTERNAL}; a reason starting "unclear:" flags an unclear line (coded INTERNAL by the rule);
 2. planted-line accuracy per annotator (12 lines; never used in any outcome);
 3. on the 200 real lines: the 2x2 table, raw agreement, each annotator's PUBLIC prevalence, Cohen's kappa with an
    item-bootstrap 95% interval (B = 2,000, seed 0);
 4. the anchor check of section 2 (the anchors and the further checks), reported before the split is used;
 5. the public relabel, run twice:
      S3 (primary)  public = consensus PUBLIC (both annotators); contested and unclear lines internal;
      S3-bound      public = PUBLIC by either annotator or flagged unclear by either (unclear -> public);
    each public question is relabelled L (entitled) for R0-R3, then the consistency pass of section 3
    (scripts/p14/consistency.py; pooled five-pass votes where every member has them, else the more protective
    label; a member coded public keeps L);
 6. S4 = S1 + S2 + S3: S3's labels with the cells S1 or S2 remove set to missing, except the questions S3 makes
    public, whose labels come from the public rule rather than from the votes S1 and S2 question (clarification
    logged in the pre-registration's section 8 before the answers were opened);
 7. the author-check draw (seed 20261004, ten lines, no planted line): five from the lines at least one annotator
    coded PUBLIC (all of them if fewer), up to three from the lines either annotator flagged unclear, the rest from
    the lines both coded INTERNAL; a blind packet (no agent label) and a key kept outside <internal>
Outputs: evidence/v3.14/coding-p1-4/results.json; evidence/v3.14/labels/{S3,S3-bound,S4}.json;
<internal>/annotation/author-check/p1-4.jsonl (with --author-packet) and
evidence/v3.14/coding-p1-4/author_check/key.json (untracked; its sha256 goes into results.json).
Usage: p14_run.py [--answers DIR] [--author-packet PATH] [--dry-run]
"""
import argparse
import collections
import csv
import hashlib
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p14"))
import consistency  # noqa: E402

C4 = ROOT / "evidence/v3.14/coding-p1-4"
LAB = ROOT / "evidence/v3.14/labels"
REQS = ("R0", "R1", "R2", "R3")
ANCHORS = {"PAIR-Q97": "INTERNAL", "PAIR-Q70": "INTERNAL", "PAIR-Q14": "INTERNAL", "PAIR-Q12": "PUBLIC",
           "PAIR-Q217": "PUBLIC", "PAIR-Q34": "PUBLIC", "PAIR-Q47": "PUBLIC", "PAIR-Q231": "PUBLIC"}
FURTHER_CHECKS = {"PAIR-Q322": "PUBLIC", "PAIR-Q88": "INTERNAL", "PAIR-Q326": "INTERNAL", "PAIR-Q90": "INTERNAL",
             "PAIR-Q235": "INTERNAL"}   # the last four: expected internal under the adopted wording (section 2)


def read_answers(d):
    out = {}
    with open(d / "WP.csv", newline="") as f:
        for row in csv.DictReader(f):
            code = row["code"].strip()
            dec = (row.get("decision") or "").strip().upper()
            if code in out:
                raise SystemExit(f"{d}: code {code} answered twice")
            if dec not in ("PUBLIC", "INTERNAL"):
                raise SystemExit(f"{d}: code {code} has decision {dec!r}")
            reason = (row.get("reason") or "").strip().strip('"').strip()
            out[code] = (dec, reason.lower().startswith("unclear:"))
    return out


def kappa(pairs):
    n = len(pairs)
    a = sum(1 for x, y in pairs if x and y)
    d = sum(1 for x, y in pairs if not x and not y)
    po = (a + d) / n
    pa, pb = sum(x for x, _ in pairs) / n, sum(y for _, y in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default=str(C4 / "answers"))
    ap.add_argument("--author-packet", default=None)
    ap.add_argument("--dry-run", action="store_true", help="write nothing under evidence/ (pipeline test)")
    args = ap.parse_args()
    key = json.loads((C4 / "key" / "key-P1-4.json").read_text())["lines"]
    A = read_answers(pathlib.Path(args.answers) / "A")
    B = read_answers(pathlib.Path(args.answers) / "B")
    if set(A) != set(key) or set(B) != set(key):
        raise SystemExit("answer codes differ from the key")
    res = {"planted": {}, "agreement": {}, "anchors": {}, "relabel": {}, "variants": {}}
    planted = {c: v for c, v in key.items() if v["planted"]}
    real = {c: v for c, v in key.items() if not v["planted"]}
    for name, ans in (("A", A), ("B", B)):
        ok = sum(ans[c][0] == v["answer"] for c, v in planted.items())
        res["planted"][name] = {"correct": ok, "of": len(planted),
                                "missed": sorted(v["task"] for c, v in planted.items() if ans[c][0] != v["answer"])}
    pairs = [(A[c][0] == "PUBLIC", B[c][0] == "PUBLIC") for c in sorted(real)]
    tab = collections.Counter((x, y) for x, y in pairs)
    rng = random.Random(0)
    boots = []
    for _ in range(2000):
        s = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        k = kappa(s)
        if k == k:
            boots.append(k)
    boots.sort()
    res["agreement"] = {
        "lines": len(pairs),
        "table": {"both_public": tab[(True, True)], "A_public_B_internal": tab[(True, False)],
                  "A_internal_B_public": tab[(False, True)], "both_internal": tab[(False, False)]},
        "raw_agreement": (tab[(True, True)] + tab[(False, False)]) / len(pairs),
        "prevalence_public": {"A": sum(x for x, _ in pairs) / len(pairs), "B": sum(y for _, y in pairs) / len(pairs)},
        "unclear": {"A": sum(A[c][1] for c in real), "B": sum(B[c][1] for c in real)},
        "kappa": kappa(pairs), "kappa_bootstrap_95": [boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]],
    }
    task_code = {v["task"]: c for c, v in real.items()}
    for name, table in (("anchors", ANCHORS), ("further_checks", FURTHER_CHECKS)):
        res["anchors"][name] = {t: {"expected": e, "A": A[task_code[t]][0] if t in task_code else None,
                                    "B": B[task_code[t]][0] if t in task_code else None} for t, e in table.items()}
        res["anchors"][name + "_agree_with_expected"] = {
            ann: sum(1 for t, e in table.items() if t in task_code and ans[task_code[t]][0] == e)
            for ann, ans in (("A", A), ("B", B))}
    consensus = {v["task"] for c, v in real.items() if A[c][0] == "PUBLIC" and B[c][0] == "PUBLIC"}
    bound = {v["task"] for c, v in real.items() if A[c][0] == "PUBLIC" or B[c][0] == "PUBLIC" or A[c][1] or B[c][1]}
    res["relabel"] = {"public_S3": len(consensus), "public_S3_bound": len(bound),
                      "contested": sum(1 for x, y in pairs if x != y),
                      "public_S3_tasks": sorted(consensus, key=lambda t: int(t[6:])),
                      "public_S3_bound_tasks": sorted(bound, key=lambda t: int(t[6:]))}
    # labels
    lab = json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/"
                             "relationship_label_matrix_v2.json").read_text())
    QL = {f"PAIR-Q{q['id']}": {r: q[r] for r in REQS} for q in lab["questions"]}
    AL = {f"PAIR-A{a['id']}": {r: a[r] for r in REQS} for a in lab["actions"]}
    votes = {}
    with open(LAB / "annotation_passes.csv") as f:
        for row in csv.DictReader(f):
            if row["kind"] != "qa" or row["requester"] not in REQS:
                continue
            t = f"PAIR-Q{row['row'][1:]}"
            vals = [row[p] for p in ("A1", "A2", "A3", "A4", "E")]
            votes[(t, row["requester"])] = (vals.count("L"), vals.count("P"))
    qs = json.loads((ROOT / "evidence/v3.14/pair-dataset/questions.json").read_text())["questions"]
    grps = consistency.groups(consistency.same_fact_pairs(qs))

    def build(public):
        q = {t: dict(v) for t, v in QL.items()}
        relabelled = 0
        for t in public:
            for r in REQS:
                if q[t][r] != "L":
                    relabelled += 1
                q[t][r] = "L"
        q, changed = consistency.apply(q, votes, grps, public=frozenset(public))
        labels = {t: {r: ("protect" if v[r] == "P" else "entitle") for r in REQS} for t, v in q.items()}
        labels.update({t: {r: ("protect" if v[r] == "refuse" else "entitle") for r in REQS} for t, v in AL.items()})
        return labels, relabelled, changed
    s3, n3, ch3 = build(consensus)
    s3b, n3b, ch3b = build(bound)
    s1 = json.loads((LAB / "S1.json").read_text())["labels"]
    s2 = json.loads((LAB / "S2.json").read_text())["labels"]
    s4 = {t: dict(v) for t, v in s3.items()}
    removed = kept_public = 0
    for t, v in s4.items():
        for r in REQS:
            if s1[t][r] is None or s2[t][r] is None:
                if t in consensus:
                    kept_public += 1
                else:
                    v[r] = None
                    removed += 1
    res["variants"] = {
        "S3": {"cells_relabelled_to_entitled": n3, "consistency_changes": len(ch3), "consistency_changed_cells": ch3},
        "S3-bound": {"cells_relabelled_to_entitled": n3b, "consistency_changes": len(ch3b)},
        "S4": {"cells_removed_by_S1_or_S2": removed, "public_cells_kept_from_S1_S2_removal": kept_public},
    }
    # author-check draw (seed fixed in the pre-registration)
    arng = random.Random(20261004)
    codes = sorted(real)
    pub = [c for c in codes if A[c][0] == "PUBLIC" or B[c][0] == "PUBLIC"]
    unc = [c for c in codes if c not in pub and (A[c][1] or B[c][1])]
    internal = [c for c in codes if c not in pub and c not in unc]
    draw = arng.sample(pub, min(5, len(pub)))
    draw += arng.sample(unc, min(3, len(unc)))
    draw += arng.sample(internal, 10 - len(draw))
    arng.shuffle(draw)
    lines = {}
    for l in (C4 / "packets" / "A" / "WP.md").read_text().splitlines():
        if l.startswith("{"):
            o = json.loads(l)
            lines[o["code"]] = o
    packet = [{"item": f"P14-AC-{i + 1:02d}", **{k: lines[c][k] for k in ("question", "reveals", "sources")}}
              for i, c in enumerate(draw)]
    ac_key = {f"P14-AC-{i + 1:02d}": {"code": c, "task": key[c]["task"], "A": A[c][0], "A_unclear": A[c][1],
                                       "B": B[c][0], "B_unclear": B[c][1],
                                       "stratum": "public" if c in pub else "unclear" if c in unc else "internal"}
              for i, c in enumerate(draw)}
    akb = (json.dumps(ac_key, indent=1, sort_keys=True) + "\n").encode()
    res["author_check"] = {"seed": 20261004, "items": len(draw),
                           "by_stratum": dict(collections.Counter(v["stratum"] for v in ac_key.values())),
                           "key_sha256": hashlib.sha256(akb).hexdigest()}
    if args.dry_run:
        print(json.dumps({k: res[k] for k in ("planted", "agreement", "relabel")}, indent=1)[:2000])
        print(json.dumps(res["variants"]["S4"]), res["author_check"])
        return
    (C4 / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    for name, labels in (("S3", s3), ("S3-bound", s3b), ("S4", s4)):
        (LAB / f"{name}.json").write_text(json.dumps({"variant": name, "labels": labels}, indent=0, sort_keys=True) + "\n")
    (C4 / "author_check").mkdir(exist_ok=True)
    (C4 / "author_check" / "key.json").write_bytes(akb)
    if args.author_packet:
        out = pathlib.Path(args.author_packet)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in packet))
        res["author_check"]["packet_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
        (C4 / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("planted", "agreement")}, indent=1))
    print(json.dumps({k: v for k, v in res["relabel"].items() if not k.endswith("tasks")}))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "consistency_changed_cells"} for k, v in res["variants"].items()}))
    print(json.dumps(res["author_check"]))


if __name__ == "__main__":
    main()
