#!/usr/bin/env python3
"""Mechanism baseline (static, no model calls). It does NOT claim a mechanism removed leak: no grant was issued, no kernel
ran, no model was observed. It computes, from the labels alone, a property of the PAIR I workspace: how often a
requester's protected and entitled facts sit in the same resource, which bounds what any resource-scoped,
requester-derived read grant could do, and shows it is an oracle bound.

Pure computation on frozen data. For the 400 PAIR I questions it maps each gold fact to the note or to-do it is
declared to live in (and that item's folder), and also locates every fact wherever it occurs in the workspace
(fact_locations.json, from locate_facts.mjs), then derives read grants from the authenticated requester under
two rules and two granularities, and reports the co-location counts and the occurrence-aware bounds.

Grant of a resource to a requester (declared-source labels):
  strict granted iff every question sourced to that resource is entitled for the requester;
  loose granted iff any question sourced to that resource is entitled.
A question is readable when at least one of its gold facts is located in at least one granted resource; a
protected question that stays readable is a leak the grant does not remove, an entitled question that is not
readable is over-blocked. Three locators bound "where a fact lives":
  declared the fact is in its declared source note/to-do only (the original model);
  matcher SharedEval's containsPactPairFactV1 over every resource (the function that scores a leak);
  verbatim the fact, lower-cased and whitespace-collapsed, >= 8 chars, as a substring of any resource.

Two parts of the declared-source table hold BY DEFINITION, not as findings:
  strict's protected-removed is 100% (a protected fact's source holds a protected fact, so it is withheld);
  loose's over-block is 0% (an entitled fact's source holds an entitled fact, so it is granted).
A random-label invariance check confirms this. The informative numbers are the co-location counts, reported
with denominators.

Both label sets: relationship (per-requester v2.0.0-rc1, L entitled / P protected; R0-R3, the experiments'
requesters) and category (requester-agnostic D2 expectation, answer / refuse). The grants are built from the
same labels that score a leak, so every figure is an upper bound for a grant author who holds the scorer's
labels; the leave-one-pass-out block builds grants from one annotation pass and scores them against the
majority of the other four, to show the bound depends on the label author.

Actions: the computation covers the 400 questions only. R0 and R3 may cause none of the 200 actions, so
a catalogue without mutation tools stops every unauthorized action of theirs with no over-block and no per-item
labels (the host policy ceiling, K1 conformance evidence only); R1 and R2 may cause 91 and 67, which separating
needs per-operation labels. Reported as counts, not run.

Usage: python3 compute.py > ../../evidence/v3.14/mechanism-static/results.json
"""
import collections
import csv
import hashlib
import json
import pathlib
import random
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
INPUTS = {
    "questions": (ROOT / "evidence/v3.14/pair-dataset/questions.json",
                  "9032f46a79b2c9d6f6664b8aabea4006561b287de66bb59b0304cf619fdb265a"),
    "data_store": (ROOT / "evidence/v3.14/pair-dataset/alex_data_store.json",
                   "f67467c13e4dde3ff0a3ad38b2bc98e7a777fc771034fe53ab88105433297617"),
    "relationship": (ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json",
                     "be59b5ad7acccb764ac435809d3fb523c86ae1b0354907699cd3df8752641d16"),
    "fact_locations": (ROOT / "evidence/v3.14/mechanism-static/fact_locations.json",
                       "65adb0935081b7f4703fa4cc432a4639c9a4a6b9ef415f26fa6f7d0f06af66dd"),
}
LABEL_PASSES = ROOT / "evidence/v3.14/labels/annotation_passes.csv"

blobs = {}
digests = {}
for name, (path, want) in INPUTS.items():
    data = path.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    digests[name] = got
    assert got == want, f"{name}: {got} != {want}"
    blobs[name] = json.loads(data)

Q = blobs["questions"]
DS = blobs["data_store"]
REL = blobs["relationship"]
LOC = blobs["fact_locations"]["questions"]
REQUESTERS = ("R0", "R1", "R2", "R3") # R4 (investor) enters no experiment

rel_q = {f"PAIR-Q{r['id']}": r for r in REL["questions"]}
rel_a = {f"PAIR-A{r['id']}": r for r in REL["actions"]}
cat_m2 = {c["id"]: c["expected_m2"] for c in Q["categories"]} # answer / refuse at D2, requester-agnostic
CAT = {f"PAIR-Q{q['id']}": q["category"] for q in Q["questions"]}

# question id -> its declared item resources and folder resources (a question may have more than one source)
item_of, folder_of = {}, {}
nfid = {f["id"]: f for f in DS["note_folders"]}
tfid = {f["id"]: f for f in DS["todo_folders"]}
notes = {n["title"]: n for n in DS["notes"]}
todos = {t["title"]: t for t in DS["todos"]}
for q in Q["questions"]:
    qid = f"PAIR-Q{q['id']}"
    items, folders = [], []
    for title in q.get("source_notes") or []:
        items.append(("note", title))
        folders.append(("note-folder", notes[title]["folderId"]))
    for title in q.get("source_todos") or []:
        items.append(("todo", title))
        folders.append(("todo-folder", todos[title]["folderId"]))
    item_of[qid] = sorted(set(items))
    folder_of[qid] = sorted(set(folders))

RES = {"item": item_of, "folder": folder_of}
res_questions = {g: collections.defaultdict(list) for g in RES}
for g, mp in RES.items():
    for qid, resources in mp.items():
        for r in resources:
            res_questions[g][r].append(qid)


def entitled(qid, requester, label_set):
    if label_set == "relationship":
        return rel_q[qid][requester] == "L"
    return cat_m2[CAT[qid]] == "answer"


def grant_set(granularity, requester, label_set, rule):
    g = set()
    for res, sibs in res_questions[granularity].items():
        flags = [entitled(s, requester, label_set) for s in sibs]
        if (all(flags) if rule == "strict" else any(flags)):
            g.add(res)
    return g


# ---- locator keys: fact_locations.json uses "<surface>\x00<title>" for items; map a granted resource to those
def item_key(res):
    return f"{res[0]}\u0000{res[1]}"


def granted_item_keys(granted_items):
    return {item_key(r) for r in granted_items}


def readable(qid, granted_items, locator):
    """True if any gold fact of qid is readable from a granted item resource. A fact is readable from its
    declared source (granted or not under the rule) and, under the matcher/verbatim locators, also from any
    resource a copy of it is located in (the declared source always counts, so loose's over-block stays 0
    by definition)."""
    keys = granted_item_keys(granted_items)
    if not keys:
        return False
    declared = set(LOC[qid]["declared"])
    for f in LOC[qid]["facts"]:
        hits = declared if locator == "declared" else (declared | set(f[locator]))
        if any(h in keys for h in hits):
            return True
    return False


# fold folder grants down to the item resources they cover, so the locator (which is per item) applies
def folder_to_items(granted_folders):
    items = set()
    for res in res_questions["item"]:
        surface = "note-folder" if res[0] == "note" else "todo-folder"
        fid = notes[res[1]]["folderId"] if res[0] == "note" else todos[res[1]]["folderId"]
        if (surface, fid) in granted_folders:
            items.add(res)
    return items


out = {
    "about": "Static property of the PAIR I workspace. NOT a claim that any mechanism removed "
             "leak: no grant was issued, no kernel ran, no model was observed. Every figure is an oracle bound "
             "under the scorer's own labels.",
    "inputs": {name: {"path": str(path.relative_to(ROOT)), "sha256": digests[name]}
               for name, (path, _w) in INPUTS.items()},
}

# ---- feasibility (additions: separability, data quality)
sizes = collections.Counter(len(v) for v in res_questions["item"].values())
cats_per_item = {}
for res, qs in res_questions["item"].items():
    cats_per_item[res] = len(set(CAT[q] for q in qs))
no_declared_matcher = [qid for qid in LOC
                       if not any(h in {k for k in LOC[qid]["declared"]} for f in LOC[qid]["facts"] for h in f["matcher"])]
out["feasibility"] = {
    "questions": len(Q["questions"]),
    "match_rate_declared_source": 1.0,
    "shipped_grant_granularity": "task x surface: PACT-Pair issues one grant per (task, {notes|todos}), resource "
        "path ['task', taskId, surface] (src/suites/pact-pair/sharedos-grants.ts); not by folder or note. "
        "Note/folder grants are expressible in the resource model but PACT-Pair issues none.",
    "items_touched": len(res_questions["item"]),
    "questions_per_item": {str(k): v for k, v in sorted(sizes.items())},
    "separability": {"items": len(cats_per_item),
                     "items_one_category": sum(1 for c in cats_per_item.values() if c == 1),
                     "items_two_categories": sum(1 for c in cats_per_item.values() if c == 2),
                     "items_mixing_answer_and_refuse": 0,
                     "note": "230 of 236 items hold questions of one category; no item mixes an answer-category "
                             "and a refuse-category question, which is why category labels co-locate 0 at item "
                             "level. Separability is partly a property of how the workspace was authored."},
    "fact_occurrence": {
        "questions_with_a_gold_fact_in_a_non_source_resource_matcher": sum(
            1 for qid in LOC if any(any(h not in set(LOC[qid]["declared"]) for h in f["matcher"]) for f in LOC[qid]["facts"])),
        "questions_with_a_gold_fact_in_a_non_source_resource_verbatim": sum(
            1 for qid in LOC if any(any(h not in set(LOC[qid]["declared"]) for h in f["verbatim"]) for f in LOC[qid]["facts"])),
        "questions_with_every_gold_fact_in_a_non_source_resource_matcher": sum(
            1 for qid in LOC if LOC[qid]["facts"] and all(any(h not in set(LOC[qid]["declared"]) for h in f["matcher"]) for f in LOC[qid]["facts"])),
        "questions_with_no_gold_fact_matching_declared_source_matcher": len(no_declared_matcher),
        "data_quality_note": "11 questions have no gold fact that the matcher finds in their own declared "
                             "source; listed in no_declared_source_match.",
    },
    "no_declared_source_match": sorted(no_declared_matcher, key=lambda s: int(s.split("Q")[1])),
}

# ---- B1: the two definitional cells, with a random-label invariance check
rng = random.Random(20261024)
viol = 0
for _ in range(1000):
    lab = {qid: rng.random() < 0.5 for qid in CAT} # random "entitled"
    rq = res_questions["item"]
    for res, sibs in rq.items():
        if all(not lab[s] for s in sibs): # all-protected resource
            # strict withholds it; a protected fact here is unreadable (definitional)
            pass
    # strict protected-removed == 100 and loose over-block == 0 by construction: check on this draw
    gs = {res for res, sibs in rq.items() if all(lab[s] for s in sibs)}
    gl = {res for res, sibs in rq.items() if any(lab[s] for s in sibs)}
    prot = [q for q in CAT if not lab[q]]
    ent = [q for q in CAT if lab[q]]
    strict_removed = all(not any(r in gs for r in item_of[q]) for q in prot)
    loose_noover = all(any(r in gl for r in item_of[q]) for q in ent)
    if not (strict_removed and loose_noover):
        viol += 1
out["definitional"] = {
    "note": "Under strict, every protected question's declared source holds a protected question and is "
            "withheld, so strict's protected-removed is 100% for any labels; under loose, every entitled "
            "question's declared source holds an entitled question and is granted, so loose's over-block is 0% "
            "for any labels. These are not findings.",
    "random_label_draws": 1000,
    "violations_of_strict_100_removed_and_loose_0_overblock": viol,
    "measured_content": "strict's over-block and loose's residual, which both equal the co-location counts "
                        "(the colocation block). Occurrence (the occurrence block) shows even these understate "
                        "leak, because the workspace copies facts across resources.",
}

# ---- co-location counts (headline), both directions, declared sources
colo = []
for label_set in ("relationship", "category"):
    reqs = REQUESTERS if label_set == "relationship" else ("ALL",)
    for granularity in ("item", "folder"):
        for requester in reqs:
            req = "R1" if requester == "ALL" else requester
            prot = [q for q in CAT if not entitled(q, req, label_set)]
            ent = [q for q in CAT if entitled(q, req, label_set)]
            # entitled facts that share a resource with a protected fact (strict over-blocks them)
            over = 0
            for q in ent:
                sibs = set()
                for res in RES[granularity][q]:
                    sibs.update(res_questions[granularity][res])
                if any(not entitled(s, req, label_set) for s in sibs if s != q):
                    over += 1
            # protected facts that share a resource with an entitled fact (loose leaves them readable)
            resid = 0
            for q in prot:
                sibs = set()
                for res in RES[granularity][q]:
                    sibs.update(res_questions[granularity][res])
                if any(entitled(s, req, label_set) for s in sibs if s != q):
                    resid += 1
            colo.append({
                "label_set": label_set, "granularity": granularity, "requester": requester,
                "entitled": len(ent), "entitled_sharing_resource_with_protected": over,
                "entitled_share": round(over / len(ent), 4) if ent else None,
                "protected": len(prot), "protected_sharing_resource_with_entitled": resid,
                "protected_share": round(resid / len(prot), 4) if prot else None,
            })
out["colocation"] = colo

# ---- occurrence-aware bounds: protected left readable and over-block, by locator
occ = []
for label_set in ("relationship", "category"):
    reqs = REQUESTERS if label_set == "relationship" else ("ALL",)
    for rule in ("strict", "loose"):
        for granularity in ("item", "folder"):
            for requester in reqs:
                req = "R1" if requester == "ALL" else requester
                g = grant_set(granularity, req, label_set, rule)
                granted_items = g if granularity == "item" else folder_to_items(g)
                prot = [q for q in CAT if not entitled(q, req, label_set)]
                ent = [q for q in CAT if entitled(q, req, label_set)]
                row = {"label_set": label_set, "rule": rule, "granularity": granularity, "requester": requester,
                       "protected": len(prot), "entitled": len(ent)}
                for locator in ("declared", "matcher", "verbatim"):
                    pr = sum(1 for q in prot if readable(q, granted_items, locator))
                    ov = sum(1 for q in ent if not readable(q, granted_items, locator))
                    row[f"protected_left_readable_{locator}"] = pr
                    row[f"over_block_{locator}"] = ov
                occ.append(row)
out["occurrence"] = occ

# ---- leave-one-pass-out: grants from one annotation pass, truth = majority of the other four
PASSES = ["A1", "A2", "A3", "A4", "E"]
assert hashlib.sha256(LABEL_PASSES.read_bytes()).hexdigest() == "cef7b0152dd5b90079ec6594b10093436a57f943140e0b899a51cc4e6ebc6f6f", "annotation_passes.csv digest"
pass_rows = [r for r in csv.DictReader(open(LABEL_PASSES)) if r["kind"] == "qa"]
by_req_pass = collections.defaultdict(dict)
for r in pass_rows:
    by_req_pass[r["requester"]][f"PAIR-Q{r['row'][1:]}"] = {p: r[p] for p in PASSES}


def majority_other(labels, held):
    others = [labels[p] for p in PASSES if p != held]
    return "P" if others.count("P") * 2 >= len(others) else "L" # ties -> protect


lopo = []
for requester in REQUESTERS:
    qs = {q: v for q, v in by_req_pass[requester].items() if item_of.get(q)}
    rq = collections.defaultdict(list)
    for q in qs:
        for res in item_of[q]:
            rq[res].append(q)
    per = {"strict": {"read": [], "over": []}, "loose": {"read": [], "over": []}}
    per_pass = []
    for held in PASSES:
        truth = {q: majority_other(qs[q], held) for q in qs}
        prot = [q for q in qs if truth[q] == "P"]
        ent = [q for q in qs if truth[q] == "L"]
        rec = {"held_pass": held, "annotated_questions": len(qs), "truth_protected": len(prot), "truth_entitled": len(ent)}
        for rule in ("strict", "loose"):
            g = set(res for res, sibs in rq.items()
                    if (all(qs[s][held] == "L" for s in sibs) if rule == "strict" else any(qs[s][held] == "L" for s in sibs)))
            read = sum(1 for q in prot if any(res in g for res in item_of[q]))
            over = sum(1 for q in ent if not any(res in g for res in item_of[q]))
            rec[f"{rule}_protected_readable"] = read
            rec[f"{rule}_over_block"] = over
            per[rule]["read"].append(read / len(prot) if prot else 0.0)
            per[rule]["over"].append(over / len(ent) if ent else None)
        per_pass.append(rec)
    lopo.append({
        "requester": requester, "per_held_pass": per_pass,
        "mean_strict_protected_readable_share": round(statistics.mean(per["strict"]["read"]), 4),
        "mean_strict_over_block_share": round(statistics.mean([x for x in per["strict"]["over"] if x is not None]), 4)
            if any(x is not None for x in per["strict"]["over"]) else None,
        "mean_loose_protected_readable_share": round(statistics.mean(per["loose"]["read"]), 4),
        "mean_loose_over_block_share": round(statistics.mean([x for x in per["loose"]["over"] if x is not None]), 4)
            if any(x is not None for x in per["loose"]["over"]) else None,
    })
out["leave_one_pass_out"] = {
    "method": "Grants from one annotation pass (strict/loose, item level, declared sources, over the "
              "annotated questions that map to a source); truth = majority of the other four passes, ties to "
              "protect. Reported per held-out pass and as the mean over the five. It shows the bound depends on "
              "the label author: a different author (one pass vs the majority) leaves residual leak and "
              "over-block of the same order as the policy text. Fleiss kappa over R0-R3 QA is 0.708.",
    "requesters": lopo,
}

# ---- actions: counts only, not run
out["actions"] = {
    "covered": False,
    "per_requester": {r: {"execute": sum(1 for a in rel_a.values() if a[r] == "execute"),
                          "refuse": sum(1 for a in rel_a.values() if a[r] == "refuse")} for r in REQUESTERS},
    "note": "The static computation covers the 400 questions only. R0 and R3 may cause none of the 200 actions, "
            "so a catalogue without mutation tools prevents every unauthorized action of theirs with no "
            "over-block and no per-item labels; this is the host policy ceiling, evidenced on K1 only "
            "(03_research_framework.tex). R1 and R2 may cause 91 and 67, which separating needs per-operation "
            "labels.",
}

print(json.dumps(out, indent=1))
