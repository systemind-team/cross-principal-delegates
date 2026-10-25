#!/usr/bin/env python3
"""P1-2: build the annotation packets for two annotators, and the hidden key (protocol v2).

Inputs: the committed frame (evidence/v3.14/adjudication/frame/), and in the sealed folder draw.py's drawn.jsonl and
planted.py's planted_items.jsonl and planted_answers.jsonl.

Each item is one reply, whole, as the requester received it (the text comes from the SharedOS record the
acceptance analyser read, identical to the message store; the key flags replies that end mid-sentence). A packet line
holds only: item_id, question, earlier_requests, request, protected_facts, reply.

Both annotators get the same 1,412 items (1,372 drawn, 40 planted), each in its own random order, split into 15 files
(14 of 95 items and one of 82), under <internal>/annotation/p1-2/annotator-A/ and annotator-B/, each folder with its own copy of
the guidelines. Annotator B is either a Gemini model run by gemini_runner.py or a second Claude model seated as an
agent: the packets are the same for both.

The key (sealed folder, never in <internal>, committed after both annotators return) maps every item_id
to: real or planted (slot), study, stratum, frame cell and flags, inclusion probability, run, task, requester, model,
reply length and the mid-sentence flag, and for the 79 later-exposure instances the old LLM reviewer's case number,
verdict and what it was shown (README of multi-probing-records: cases 1-8 cut at 1,800 characters; 9-64 cut at
900-1,300 and only the first flagged reply unless it asked for the rest; 65-79 only the sentences with gold words).
"Full view" here means every flagged reply of the case fits the smallest limit documented for its range (1,800 or
900 characters) and all were shown; the transcript's per-call limits are not frozen, so this is the conservative
reading.

Usage: python3 make_packets.py <sealed dir> <annotation p1-2 dir> <guidelines.md> > manifest.json
"""
import collections
import gzip
import hashlib
import json
import lzma
import math
import os
import pathlib
import random
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEALED, ANN, GUIDE = sys.argv[1], sys.argv[2], sys.argv[3]
FR = ROOT / "evidence/v3.14/adjudication/frame"
REC = ROOT / "evidence/v3.14/multi-probing-records"
seeds = json.load(open(FR / "seeds.json"))
FILES = 15
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


qs = json.load(open(ROOT / "evidence/v3.14/multi-spoof/inputs/questions.json"))
GOLD = {f"PAIR-Q{q['id']}": q for q in qs["questions"]}
contacts = {c["contactId"]: c for c in map(json.loads, gzip.open(REC / "contacts.jsonl.gz", "rt"))}
f2 = {r["unit"]: r for r in map(json.loads, gzip.open(FR / "pair2_frame.jsonl.gz", "rt"))}
f1 = {r["unit"]: r for r in map(json.loads, gzip.open(FR / "pair1_frame.jsonl.gz", "rt"))}
tasks1 = {(t["cell"], t["taskId"]): t for t in map(json.loads, lzma.open(ROOT / "evidence/v3.14/single-grid-tasks/tasks.jsonl.xz", "rt"))}
inst = collections.defaultdict(list)
for r in f2.values():
    inst[(r["runId"], r["taskId"])].append(r)
for v in inst.values():
    v.sort(key=lambda r: r["index"])

cases = json.load(open(REC / "later_exposures/cases.json"))["cases"]
ONLY_FIRST = {10, 14, 29, 31, 35, 38, 47, 49, 57}
ASKED_REST = {13, 17, 37, 41, 44, 56, 58, 61, 62}
old = {}
for c in cases:
    k = c["case"]
    flagged = c["flaggedLaterReplies"]
    if k >= 65:
        view = "gold-word sentences only"
    elif k in ONLY_FIRST:
        view = "first of several flagged replies only"
    else:
        shown = flagged if (k <= 8 or k in ASKED_REST) else flagged[:1]
        limit = 1800 if k <= 8 else 900
        view = "full" if all(len(r["response"] or "") <= limit for r in shown) else "cut by the display limit"
    old[(c["runId"], c["taskId"])] = {"case": k, "verdict": c["reviewer"]["verdict"], "strength": c["reviewer"].get("strength"),
                                      "channel": c["reviewer"].get("channel"), "view": view}

drawn = [json.loads(l) for l in open(os.path.join(SEALED, "drawn.jsonl"))]
planted = [json.loads(l) for l in open(os.path.join(SEALED, "planted_items.jsonl"))]
rng_id = random.Random(seeds["draw_seed"] + 1)
ids = set()


def new_id():
    while True:
        x = "".join(rng_id.choice(ALPHABET) for _ in range(6))
        if x not in ids:
            ids.add(x)
            return x


items, key = [], []
for d in drawn:
    if d["study"] == "PAIR II":
        r = f2[d["unit"]]
        c = contacts[r["contactId"]]
        chain = inst[(r["runId"], r["taskId"])]
        item = {"question": GOLD[r["taskId"]]["question"],
                "earlier_requests": [contacts[x["contactId"]]["requestText"] for x in chain[: r["index"]]],
                "request": c["requestText"], "protected_facts": GOLD[r["taskId"]]["gold_key_facts"], "reply": c["response"]}
        k = {"kind": "real", "study": "PAIR II", "stratum": d["stratum"], "unit": d["unit"], "inclusion": d["inclusion"],
             "population": d["population"], "drawn": d["drawn"], "runId": r["runId"], "taskId": r["taskId"],
             "requester": r["requester"], "rep": r["rep"], "index": r["index"], "strategy": r["strategy"],
             "position": r["position"], "analyser_hit": r["analyser_hit"], "runtime_hit": r["runtime_hit"],
             "runtime_exposure": r["runtime_exposure"], "record": r["record"],
             "first_clean_instance": r["first_clean_instance"], "later_exposure_instance": r["later_exposure_instance"],
             "reply_chars": r["reply_chars"], "ends_mid_sentence": r["ends_mid_sentence"],
             "old_reviewer": old.get((r["runId"], r["taskId"])) if r["later_exposure_instance"] else None}
    else:
        r = f1[d["unit"]]
        t = tasks1[(r["cell"], r["taskId"])]
        item = {"question": GOLD[r["taskId"]]["question"], "earlier_requests": [], "request": t["requestText"],
                "protected_facts": GOLD[r["taskId"]]["gold_key_facts"], "reply": t["replyText"]}
        k = {"kind": "real", "study": "PAIR I", "stratum": d["stratum"], "unit": d["unit"], "inclusion": d["inclusion"],
             "population": d["population"], "drawn": d["drawn"], "cell": r["cell"], "taskId": r["taskId"], "model": r["model"],
             "family": r["family"], "policy": r["policy"], "requester": r["requester"], "decision": r["decision"],
             "runtime_hit": r["runtime_hit"], "recovered": r["recovered"], "reply_chars": r["reply_chars"],
             "ends_mid_sentence": r["ends_mid_sentence"]}
    iid = new_id()
    items.append({"item_id": iid, **item})
    key.append({"item_id": iid, **k})
for p in planted:
    iid = new_id()
    items.append({"item_id": iid, **{f: p[f] for f in ("question", "earlier_requests", "request", "protected_facts", "reply")}})
    key.append({"item_id": iid, "kind": "planted", "slot": p["slot"]})
assert len(items) == 1412 and all(isinstance(i["reply"], str) and i["reply"].strip() for i in items)

with open(os.path.join(SEALED, "key.jsonl"), "w") as f:
    for k in key:
        f.write(json.dumps(k, ensure_ascii=False) + "\n")

manifest = {"items": len(items), "real": len(drawn), "planted": len(planted), "files_per_annotator": FILES,
            "key_sha256": sha(os.path.join(SEALED, "key.jsonl")),
            "planted_answers_sha256": sha(os.path.join(SEALED, "planted_answers.jsonl")),
            "planted_items_sha256": sha(os.path.join(SEALED, "planted_items.jsonl")),
            "drawn_sha256": sha(os.path.join(SEALED, "drawn.jsonl")),
            "guidelines_sha256": sha(GUIDE), "seeds": seeds, "annotators": {}}
for who, offset in (("annotator-A", 2), ("annotator-B", 3)):
    order = items[:]
    random.Random(seeds["draw_seed"] + offset).shuffle(order)
    folder = os.path.join(ANN, who)
    os.makedirs(os.path.join(folder, "packets"), exist_ok=True)
    os.makedirs(os.path.join(folder, "labels"), exist_ok=True)
    shutil.copyfile(GUIDE, os.path.join(folder, "GUIDELINES.md"))
    per = math.ceil(len(order) / FILES)
    files = {}
    for i in range(FILES):
        chunk = order[i * per:(i + 1) * per]
        if not chunk:
            continue
        name = f"part-{i + 1:02d}.jsonl"
        path = os.path.join(folder, "packets", name)
        with open(path, "w") as f:
            for it in chunk:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        files[name] = {"items": len(chunk), "sha256": sha(path)}
    manifest["annotators"][who] = files
json.dump(manifest, sys.stdout, indent=1)
print()
