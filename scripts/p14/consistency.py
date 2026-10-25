#!/usr/bin/env python3
"""Label consistency pass: one label per requester for questions that ask for the same fact.

Pre-registered in evidence/v3.14/coding-p1-4/PREREGISTRATION.md section 3. Two questions ask for the same
fact when
  (a) their question texts are identical after normalization, or
  (b) they share a normalized gold fact of at least three words, or
  (c) they share a normalized gold fact or minimum-correct string and their question words (stop words
      removed) overlap with Jaccard >= 0.5.
Groups are connected components. Within a group, for a requester whose labels differ: if every member has
five-pass votes, all members take the majority of the pooled votes (ties -> P); otherwise all take the
more protective label (P). Members in `public` (coded PUBLIC in the public/internal task) keep L.

Run directly, it lists the groups and the conflicts on the original labels.
"""
import itertools
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
DS = ROOT / "evidence/v3.14/pair-dataset"
STOP = set("what's what is are the a an of for to in on at does do did how when where who which alex alex's "
           "techflow's techflow s".split())


def norm(s):
    return re.sub(r"[^a-z0-9$%#+/]+", " ", s.lower()).strip()


def qwords(s):
    return {t for t in norm(s).split() if t not in STOP}


def jaccard(a, b):
    A, B = qwords(a), qwords(b)
    return len(A & B) / max(1, len(A | B))


def same_fact_pairs(questions):
    Q = {f"PAIR-Q{q['id']}": q for q in questions}
    pairs = []
    for i, j in itertools.combinations(sorted(Q, key=lambda t: int(t[6:])), 2):
        qi, qj = Q[i], Q[j]
        fi = {norm(f) for f in qi["gold_key_facts"]}
        fj = {norm(f) for f in qj["gold_key_facts"]}
        shared = fi & fj
        mc = norm(qi.get("minimum_correct", "")) == norm(qj.get("minimum_correct", "")) != ""
        jq = jaccard(qi["question"], qj["question"])
        if (norm(qi["question"]) == norm(qj["question"]) or any(len(f.split()) >= 3 for f in shared)
                or ((shared or mc) and jq >= 0.5)):
            pairs.append((i, j))
    return pairs


def groups(pairs):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in pairs:
        parent[find(a)] = find(b)
    comp = {}
    for x in list(parent):
        comp.setdefault(find(x), []).append(x)
    return [sorted(v, key=lambda t: int(t[6:])) for v in comp.values()]


def apply(labels, votes, grps, requesters=("R0", "R1", "R2", "R3"), public=frozenset()):
    """labels: task -> {R: 'P'|'L'|None}; votes: (task, R) -> (#L, #P) or absent. Returns new labels and
    the list of changed cells."""
    out = {t: dict(v) for t, v in labels.items()}
    changed = []
    for g in grps:
        for r in requesters:
            members = [t for t in g if t not in public and out[t].get(r) is not None]
            labs = {out[t][r] for t in members}
            if len(labs) < 2:
                continue
            if all((t, r) in votes for t in members):
                nl = sum(votes[(t, r)][0] for t in members)
                np_ = sum(votes[(t, r)][1] for t in members)
                new = "L" if nl > np_ else "P"
                how = "pooled votes"
            else:
                new, how = "P", "more protective"
            for t in members:
                if out[t][r] != new:
                    changed.append({"task": t, "requester": r, "from": out[t][r], "to": new, "group": g, "rule": how})
                    out[t][r] = new
    return out, changed


if __name__ == "__main__":
    qs = json.loads((DS / "questions.json").read_text())["questions"]
    lab = json.loads((ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/"
                              "relationship_label_matrix_v2.json").read_text())
    L = {f"PAIR-Q{q['id']}": {r: q[r] for r in ("R0", "R1", "R2", "R3")} for q in lab["questions"]}
    pairs = same_fact_pairs(qs)
    grps = groups(pairs)
    conflicts = [(a, b, [r for r in ("R0", "R1", "R2", "R3") if L[a][r] != L[b][r]]) for a, b in pairs]
    conflicts = [c for c in conflicts if c[2]]
    print(f"{len(pairs)} same-fact pairs in {len(grps)} groups; {len(conflicts)} pairs with conflicting labels")
    for a, b, rs in conflicts:
        print(f"  {a} / {b}: {', '.join(rs)}")
