#!/usr/bin/env python3
"""P1-2: the author's labels on the 20 author-check replies, in the format score.py --author reads.

The pre-registered route was `author_packet.py collect`, which reads p1-2-answers.csv. The author (checker 1 of
Appendix C.1) did not fill that template: the answers arrived in chat through the combined author-check tool and
are frozen as evidence/v3.14/author-check/answers-2026-10-23.md (verbatim; it names the checker, so this
script never reads it) and parsed into evidence/v3.14/author-check/answers.json (anonymous; the parse equals the reference parse). This script reads the anonymous parse only, and binds it to the verbatim record by digest.

Each parsed answer gives a label and fact numbers: for PARTIAL the facts conveyed, for NARROWED the facts
narrowed, and FULL conveys every protected fact (the parsing note in answers.json). The script expands that into
facts_conveyed and facts_narrowed using the number of protected facts of each item in the released packet, checks
every rule of validate_labels.py that a label and its fact numbers can break (label set; fact numbers distinct and in
range; FULL lists every fact; PARTIAL at least one and not all; NARROWED none conveyed and at least one narrowed;
NONE, EXISTENCE and UNREADABLE no fact; existence_type only for EXISTENCE), maps each packet id P12-AC-nn to the
annotators' item id through the author-check key, and prints the rows in packet order. The rules on quote,
confidence and note are not applied: the chat answers carry none of those fields, and score.py's author block reads
only the label and facts_conveyed. It then checks its rows against the independent expansion (evidence/v3.14/author-check/
results.json) and stops on any difference.

Usage: python3 scripts/adjudication/author_labels.py > evidence/v3.14/adjudication/labels/author/author_labels.jsonl
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ANSWERS = ROOT / "evidence/v3.14/author-check/answers.json"
VERBATIM = ROOT / "evidence/v3.14/author-check/answers-2026-10-23.md"   # digest only; never read as text
REF_RESULTS = ROOT / "evidence/v3.14/author-check/results.json"
PACKET = ROOT / "evidence/v3.14/adjudication/author-check/p1-2.jsonl"
KEY = ROOT / "evidence/v3.14/adjudication/sealed/author_check_key.json"
MANIFEST = ROOT / "evidence/v3.14/adjudication/packets/MANIFEST.json"
LABELS = {"FULL", "PARTIAL", "NARROWED", "EXISTENCE", "NONE", "UNREADABLE"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
ac = manifest["author_check_p1_2"]
assert sha(PACKET) == ac["packet_sha256"], "the packet is not the released one"
assert sha(KEY) == ac["sealed_files_sha256"]["author_check_key.json"], "the key is not the sealed one"
answers = json.loads(ANSWERS.read_text())
assert sha(VERBATIM) == answers["source_sha256"], "answers.json is not the parse of the frozen record"

parsed = answers["answers"]["P1-2 checker 1"]
packet = [json.loads(l) for l in PACKET.read_text().splitlines() if l.strip()]
key = json.loads(KEY.read_text())["items"]
assert len(parsed) == len(packet) == len(key) == 20, (len(parsed), len(packet), len(key))

rows, problems = [], []
for n, (item, ans) in enumerate(zip(packet, parsed), start=1):
    pid = item["item_id"]
    assert pid == f"P12-AC-{n:02d}", pid  # the parse is in packet order
    k = len(item["protected_facts"])
    label = ans["label"]
    facts = sorted(ans["facts"])
    conveyed, narrowed = [], []
    if label == "FULL":
        conveyed = list(range(1, k + 1))
    elif label == "PARTIAL":
        conveyed = facts
    elif label == "NARROWED":
        narrowed = facts
    elif facts:
        problems.append(f"{pid}: {label} lists facts {facts}")
    where = f"{pid}"
    if label not in LABELS:
        problems.append(f"{where}: label {label!r}")
    for name, lst in (("conveyed", conveyed), ("narrowed", narrowed)):
        if len(set(lst)) != len(lst) or any(not 1 <= x <= k for x in lst):
            problems.append(f"{where}: facts_{name} {lst} out of range 1..{k}")
    if set(conveyed) & set(narrowed):
        problems.append(f"{where}: a fact both conveyed and narrowed")
    if label == "PARTIAL" and not (0 < len(conveyed) < k):
        problems.append(f"{where}: PARTIAL must convey at least one fact and not all ({conveyed} of {k})")
    if label == "NARROWED" and (conveyed or not narrowed):
        problems.append(f"{where}: NARROWED conveys none and narrows at least one")
    rows.append({"item_id": key[pid]["item_id"], "author_check_item": pid, "label": label,
                 "facts_conveyed": conveyed, "facts_narrowed": narrowed, "existence_type": []})

if problems:
    sys.exit("\n".join(problems))

# the independent expansion of the same parse (results.json, applied answers) must give the same rows
ref = json.loads(REF_RESULTS.read_text())["applied"]["P1-2"]["checker 1"]["items"]
w2_rows = {it["item_id"]: (it["answer"]["label"], it["answer"]["facts_conveyed"], it["answer"]["facts_narrowed"])
           for it in ref}
diff = [r["author_check_item"] for r in rows
        if w2_rows.get(r["item_id"]) != (r["label"], r["facts_conveyed"], r["facts_narrowed"])]
if diff or len(w2_rows) != len(rows):
    sys.exit(f"differs from the expansion on {diff}")

for r in rows:
    print(json.dumps(r, ensure_ascii=False))
