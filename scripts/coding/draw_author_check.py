#!/usr/bin/env python3
"""Draw the lines an author checks, after coding, with a seed fixed before coding.

Seed: 20261004. Per task, 10 lines (the design target was 40: 10 each for the matcher adjudication's exposures, the
total-leak matcher's recall, the literal policy verdicts and the public/internal codes; the authors received the first
10 of the two coding tasks' draws). Planted lines are never drawn. The two tasks keep their data keys, p1-3 (literal
verdicts) and p1-4 (public or internal).

  p1-3: spread over D1 and D2 and over matched and mismatched lines (literal verdict of the annotators'
        consensus against the relationship label), contested lines included as their own stratum:
        stratum order D1-matched, D1-mismatched, D2-matched, D2-mismatched, contested; lines are drawn
        round-robin over the strata, each stratum in a seeded random order.
  p1-4: at least 5 lines that at least one annotator coded PUBLIC (all of them if fewer than 5), the rest
        from the other lines, each in a seeded random order.

The author sheet shows each drawn line exactly as the annotators saw it, without either annotator's code
(the author is blind to the agents' labels). The key sheet that maps the drawn codes to both codes is
withheld from the author until the author has answered.

Usage: draw_author_check.py p1-3|p1-4  ->  evidence/v3.14/coding-p1-x/author-check/{sheet.md,drawn.json}
"""
import csv
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED, N = 20261004, 10
LABELS = ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json"
SHARE = {"SHARE", "PERFORM", "PUBLIC"}


def answers(out, ann):
    res = {}
    for f in sorted((out / "answers" / ann).glob("*.csv")):
        for row in csv.DictReader(open(f, newline="")):
            res[row["code"].strip()] = (row.get("decision") or "").strip().upper()
    return res


def packet_lines(out):
    lines = {}
    for f in sorted((out / "packets" / "A").glob("*.md")):
        if f.name == "INSTRUCTIONS.md":
            continue
        text = f.read_text()
        head = text.split("## Lines", 1)[0]
        for l in text.splitlines():
            if l.startswith('{"code"'):
                d = json.loads(l)
                lines[d["code"]] = {"file": f.name, "head": head, "line": d}
    return lines


def main(task):
    out = ROOT / f"evidence/v3.14/coding-{task}"
    key = json.loads((out / "key" / f"key-{task.upper()}.json").read_text())["lines"]
    A, B = answers(out, "A"), answers(out, "B")
    rng = random.Random(SEED)
    real = sorted(c for c, k in key.items() if not k["planted"])
    if task == "p1-3":
        lab = json.loads(LABELS.read_text())
        L = {f"PAIR-Q{q['id']}": q for q in lab["questions"]}
        L.update({f"PAIR-A{a['id']}": a for a in lab["actions"]})
        strata = {s: [] for s in ("D1-matched", "D1-mismatched", "D2-matched", "D2-mismatched", "contested")}
        for c in real:
            k = key[c]
            if k["packet"] not in ("D1",) and not k["packet"].startswith("D2"):
                continue
            a, b = A[c] in SHARE, B[c] in SHARE
            if a != b:
                strata["contested"].append(c)
                continue
            r = k["requester"] or "R3"   # D1 lines are requester-independent; judge them against the friend
            t = k["task"]
            entitled = (L[t][r] == "L") if t.startswith("PAIR-Q") else (L[t][r] == "execute")
            pol = "D1" if k["packet"] == "D1" else "D2"
            strata[f"{pol}-{'matched' if a == entitled else 'mismatched'}"].append(c)
        for s in strata.values():
            rng.shuffle(s)
        drawn, i = [], 0
        while len(drawn) < N and any(strata.values()):
            s = list(strata)[i % len(strata)]
            if strata[s]:
                drawn.append((s, strata[s].pop(0)))
            i += 1
    else:
        pub = [c for c in real if A[c] == "PUBLIC" or B[c] == "PUBLIC"]
        rest = [c for c in real if c not in pub]
        rng.shuffle(pub)
        rng.shuffle(rest)
        take = pub[:5]
        drawn = [("coded public by at least one annotator", c) for c in take] + \
                [("other", c) for c in rest[:N - len(take)]]
    lines = packet_lines(out)
    dst = out / "author-check"
    dst.mkdir(exist_ok=True)
    sheet = ["# Author check", "", "For each line, read the policy text or sources and the line, and record the "
             "answer the instructions call for (INSTRUCTIONS.md in the same packet) and one sentence of reason. "
             "You do not see either annotator's answer.", ""]
    for n, (stratum, c) in enumerate(drawn, 1):
        sheet += [f"## Line {n} (code {c})", "", lines[c]["head"].strip(), "", "```json",
                  json.dumps(lines[c]["line"], ensure_ascii=False, indent=1), "```", "", "Your answer: ", ""]
    (dst / "sheet.md").write_text("\n".join(sheet) + "\n")
    (dst / "drawn.json").write_text(json.dumps({"seed": SEED, "drawn": [{"stratum": s, "code": c} for s, c in drawn]},
                                               indent=1) + "\n")
    print(f"drew {len(drawn)} lines for {task}")


if __name__ == "__main__":
    main(sys.argv[1])
