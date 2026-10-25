#!/usr/bin/env python3
"""P1-2: the sampling frame. Read-only over frozen inputs.

PAIR II, the probing grid: every protected reply (10,651: 2,396 first replies and 8,255 later ones), cut by
  position   first reply of the instance, or later;
  analyser   the acceptance analyser's matcher flag (targetDisclosure; the diagnostic matcher);
  runtime    the scoring matcher's refusal-channel hit (a gold fact in the reply that is not already in the
             conversation; runtime_hits.mjs);
  record     the requester's record of the reply: answered, refused (any other status), or no reply (no reply
             text: the contact failed, or the reply is empty).
An instance (run, question) is first-clean when its first contact has no analyser hit (numbers.py's rule for the
79 later exposures).

PAIR I, the single-request grid: every scored protected question (relationship labels), cut by responder model,
decision and the scoring matcher's hit on the reply (decision leak for answers, refusal channel for refusals;
the evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz).

Strata (what the draw takes from each cell) are defined here, before any count is posted, so the cell counts
and the strata sizes can be read together:
  S1L  PAIR II, the 79 later-exposure instances: every later reply with an analyser hit          census
  S1F  PAIR II, the first replies of those 79 instances (those with reply text)                 census
  S2   PAIR II, first replies with an analyser hit not recorded as answers                      census (261)
  S3P  PAIR II, replies recorded as answers with no analyser hit                                census
  S4P  PAIR II, replies recorded as answers with an analyser hit                                census (96)
  SR   PAIR II, replies with a runtime hit and no analyser hit, first replies and later replies
       of first-clean instances                                                                 census
  S5F  PAIR II, first replies recorded as refusals, clean by both matchers, not in S1F           240
  S5L  PAIR II, later replies recorded as refusals, clean by both matchers, of first-clean
       instances, not in S1L                                                                    240
  S3I  PAIR I, answered protected questions with no hit                                         40 per model
  S4I  PAIR I, answered protected questions with a hit                                          15 per model
  S6F  PAIR I, refused protected questions with a refusal-channel hit                           20 per model (all if fewer)
  S6C  PAIR I, refused protected questions, clean                                               30 per model
Not drawn: no-reply cells (nothing to read) and later replies of instances whose first contact had an analyser
hit (they enter no estimate; their count is printed).

Outputs (evidence/v3.14/adjudication/frame/): pair2_frame.jsonl.gz and pair1_frame.jsonl.gz (one row per unit,
with its cell and stratum), cells.json (every cell's count and every stratum's population and draw size), and
seeds.json (the draw seed and the author-check seed, both read off the sha256 of cells.json, so they are fixed
before anything is drawn and nobody chooses them).

Usage: python3 frame.py <runtime_hits.jsonl> <out dir>
"""
import collections
import gzip
import hashlib
import json
import lzma
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME, OUT = sys.argv[1], sys.argv[2]
SIZES = {"S5F": 240, "S5L": 240, "S3I": 40, "S4I": 15, "S6F": 20, "S6C": 30}
END_OK = tuple(".!?:;)]}\"'`*…”’>|")

contacts = {c["contactId"]: c for c in map(json.loads, gzip.open(ROOT / "evidence/v3.14/multi-probing-records/contacts.jsonl.gz", "rt"))}
hits = [json.loads(l) for l in open(RUNTIME)]
assert len(hits) == 10651, len(hits)


def record(c):
    resp = c.get("response")
    if not isinstance(resp, str) or not resp.strip():
        return "no reply"
    return "answered" if c.get("memoryStatus") == "answered" else "refused"


by_inst = collections.defaultdict(list)
for h in hits:
    by_inst[(h["runId"], h["taskId"])].append(h)
first_clean = {k: not contacts[v[0]["contactId"]]["targetDisclosure"]
               for k, v in by_inst.items() for _ in [v.sort(key=lambda x: x["index"])]}
later_exposure = {k for k, v in by_inst.items()
                  if first_clean[k] and any(contacts[h["contactId"]]["targetDisclosure"] for h in v[1:])}
assert len(by_inst) == 2396 and len(later_exposure) == 79, (len(by_inst), len(later_exposure))

rows2 = []
for h in hits:
    c = contacts[h["contactId"]]
    key = (h["runId"], h["taskId"])
    pos = "first" if h["index"] == 0 else "later"
    ana, rt, rec = bool(c["targetDisclosure"]), bool(h["runtimeHit"]), record(c)
    resp = c.get("response") if isinstance(c.get("response"), str) else ""
    if rec == "no reply":
        stratum = None
    elif key in later_exposure and pos == "later" and ana:
        stratum = "S1L"
    elif key in later_exposure and pos == "first":
        stratum = "S1F"
    elif pos == "first" and ana and rec != "answered":
        stratum = "S2"
    elif rec == "answered":
        stratum = "S4P" if ana else "S3P"
    elif rt and not ana and (pos == "first" or first_clean[key]):
        stratum = "SR"
    elif pos == "first" and rec == "refused" and not ana and not rt:
        stratum = "S5F"
    elif pos == "later" and first_clean[key] and rec == "refused" and not ana and not rt:
        stratum = "S5L"
    else:
        stratum = None                       # later replies of instances whose first contact was flagged
    rows2.append({
        "unit": f"{h['runId']}|{h['taskId']}|{h['index']}", "runId": h["runId"], "taskId": h["taskId"],
        "contactId": h["contactId"], "index": h["index"], "requester": c["requester"], "rep": c["rep"],
        "attempt": c["attempt"], "tick": c["tick"], "strategy": c.get("claimedStrategy"),
        "position": pos, "analyser_hit": ana, "runtime_hit": rt, "runtime_exposure": bool(h["runtimeExposure"]),
        "record": rec, "first_clean_instance": first_clean[key], "later_exposure_instance": key in later_exposure,
        "reply_chars": len(resp), "ends_mid_sentence": bool(resp.strip()) and not resp.rstrip().endswith(END_OK),
        "stratum": stratum})

pair1 = [json.loads(l) for l in lzma.open(ROOT / "evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz", "rt")]
tasks = {(t["cell"], t["taskId"]): t for t in map(json.loads, lzma.open(ROOT / "evidence/v3.14/single-grid-tasks/tasks.jsonl.xz", "rt"))}
rows1 = []
for p in pair1:
    if p["kind"] != "question" or p["rel"] != "protect" or not p["scored"]:
        continue
    t = tasks[(p["cell"], p["task"])]
    reply = t.get("replyText") if isinstance(t.get("replyText"), str) else ""
    dec = p["decision"]
    hit = bool(p["decision_leak"]) if dec == "answer" else bool(p["refusal_channel"])
    if not reply.strip():
        stratum = None
    elif dec == "answer":
        stratum = "S4I" if hit else "S3I"
    else:
        stratum = "S6F" if hit else "S6C"
    rows1.append({"unit": f"{p['cell']}|{p['task']}", "cell": p["cell"], "taskId": p["task"], "model": t["responderShort"],
                  "family": p["family"], "policy": p["policy"], "requester": p["requester"], "decision": dec,
                  "runtime_hit": hit, "recovered": bool(p["recovered"]), "reply_chars": len(reply),
                  "ends_mid_sentence": bool(reply.strip()) and not reply.rstrip().endswith(END_OK), "stratum": stratum})

os.makedirs(OUT, exist_ok=True)
for name, rows in (("pair2_frame.jsonl.gz", rows2), ("pair1_frame.jsonl.gz", rows1)):
    with open(os.path.join(OUT, name), "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as f:
        for r in rows:
            f.write((json.dumps(r, ensure_ascii=False) + "\n").encode())   # mtime 0: byte-identical on rerun

cells2 = collections.Counter((r["position"], r["analyser_hit"], r["runtime_hit"], r["record"]) for r in rows2)
strata2 = collections.Counter(r["stratum"] for r in rows2)
cells1 = collections.Counter((r["model"], r["decision"], r["runtime_hit"]) for r in rows1)
strata1 = collections.Counter((r["stratum"], r["model"]) for r in rows1)
out = {
    "pair2": {
        "replies": len(rows2), "instances": len(by_inst), "later_exposure_instances": len(later_exposure),
        "cells": [{"position": k[0], "analyser_hit": k[1], "runtime_hit": k[2], "record": k[3], "replies": v}
                  for k, v in sorted(cells2.items())],
        "first_replies": sum(1 for r in rows2 if r["position"] == "first"),
        "first_replies_with_text": sum(1 for r in rows2 if r["position"] == "first" and r["record"] != "no reply"),
        "first_no_reply": dict(collections.Counter(
            f"{contacts[r['contactId']].get('contactStatus')} / {contacts[r['contactId']].get('contactErrorCode')} / "
            f"requester recorded {contacts[r['contactId']].get('memoryStatus')} / reply "
            f"{'none' if contacts[r['contactId']].get('response') is None else 'empty'}"
            for r in rows2 if r["position"] == "first" and r["record"] == "no reply")),
        "answered_by_analyser_hit": dict(collections.Counter(
            f"{r['position']}, analyser {'hit' if r['analyser_hit'] else 'clean'}, stratum {r['stratum']}"
            for r in rows2 if r["record"] == "answered")),
        "later_replies_of_first_flagged_instances": sum(1 for r in rows2 if r["position"] == "later" and not r["first_clean_instance"]),
        "strata": {k: {"population": v, "draw": SIZES.get(k, "census")} for k, v in sorted(strata2.items(), key=str) if k},
        "not_drawn": strata2[None],
        "ends_mid_sentence": sum(1 for r in rows2 if r["ends_mid_sentence"]),
    },
    "pair1": {
        "protected_scored_questions": len(rows1),
        "cells": [{"model": k[0], "decision": k[1], "runtime_hit": k[2], "questions": v} for k, v in sorted(cells1.items())],
        "strata": {f"{k[0]} {k[1]}": {"population": v, "draw": min(v, SIZES[k[0]])}
                   for k, v in sorted(strata1.items(), key=str) if k[0]},
        "no_reply_text": strata1.get((None, "DeepSeek"), 0) + strata1.get((None, "GLM"), 0) + strata1.get((None, "GPT-5.6"), 0),
    },
    "sizes": SIZES,
}
json.dump(out, open(os.path.join(OUT, "cells.json"), "w"), indent=1)
# Seeds, fixed by the frame before anything is drawn: the sha256 of cells.json, digits 1-8 for the draw and the
# planted items' base replies, digits 9-16 for the author check.
digest = hashlib.sha256(open(os.path.join(OUT, "cells.json"), "rb").read()).hexdigest()
seeds = {"cells_json_sha256": digest, "draw_seed": int(digest[:8], 16), "author_check_seed": int(digest[8:16], 16)}
json.dump(seeds, open(os.path.join(OUT, "seeds.json"), "w"), indent=1)
print(json.dumps({**out, "seeds": seeds}, indent=1))
