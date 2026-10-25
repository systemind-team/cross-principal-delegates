#!/usr/bin/env python3
"""Merge the two relationship-v2 rescore reports (82 OpenRouter/docker cells + 28 Azure luna cells)
into one 110-cell table and one task-level JSONL. Inputs are read-only rescore artifacts.

  cells.json   : one record per cell with metadata + strict and with-recovery rates (numerator/denominator/value)
  tasks.jsonl  : every task detail row of every cell, tagged with cell metadata
"""
import json, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = [
    ("rescore-v41-recovered", "OpenRouter grid rep1 (82 cells) rescored with --recover-quarantined-qa; strict block byte-identical to rescore-final-82.json"),
    ("rescore-luna", "Azure gpt-5.6-luna grid rep1 (28 cells) rescored with --recover-quarantined-qa"),
]
FAMILY = {
    # family: responder model, requester model, responder harness, transport, temperature
    "ds41":  dict(responder="DeepSeek V4.1 Flash", requester="DeepSeek V4.1 Flash", harness="standard", transport="OpenRouter", temperature=0),
    "glm":   dict(responder="GLM 5.3 Flash",       requester="GLM 5.3 Flash",       harness="standard", transport="OpenRouter", temperature=0),
    "xC":    dict(responder="DeepSeek V4.1 Flash", requester="GLM 5.3 Flash",       harness="standard", transport="OpenRouter", temperature=0),
    "xD":    dict(responder="GLM 5.3 Flash",       requester="DeepSeek V4.1 Flash", harness="standard", transport="OpenRouter", temperature=0),
    "codex": dict(responder="DeepSeek V4.1 Flash", requester="DeepSeek V4.1 Flash", harness="codex-cli", transport="OpenRouter", temperature=0),
    "luna":  dict(responder="gpt-5.6-luna",        requester="gpt-5.6-luna",        harness="standard", transport="Azure OpenAI", temperature=1),
}
SHORT = {"DeepSeek V4.1 Flash": "DeepSeek", "GLM 5.3 Flash": "GLM", "gpt-5.6-luna": "GPT-5.6"}
METRICS = ["informationUtility", "informationSecurity", "actionUtility", "actionSafety", "falseRefusalRate", "leakRate"]

def parse_label(label):
    m = re.fullmatch(r"([A-Za-z0-9]+)-d(\d)-r(\d)", label)
    if not m: raise SystemExit(f"bad label {label}")
    return m.group(1), f"D{m.group(2)}", f"R{m.group(3)}"

cells, provenance = [], {}
for src, note in SOURCES:
    rep = json.load(open(os.path.join(ROOT, src, "rescore.json")))
    provenance[src] = dict(note=note, labels=rep["relationshipLabelProvenance"], schema=rep["schema"])
    for label, c in rep["cells"].items():
        fam, policy, req = parse_label(label)
        meta = FAMILY[fam]
        tc = c["taskCounts"]
        rec = tc.get("recovery", {"recoveredQa": 0, "declined": {}})
        cells.append(dict(
            cell=label, family=fam, policy=policy, requester=req, source=src,
            responder=meta["responder"], requesterModel=meta["requester"], responderShort=SHORT[meta["responder"]],
            requesterShort=SHORT[meta["requester"]], harness=meta["harness"], transport=meta["transport"], temperature=meta["temperature"],
            runId=c["runId"], configModel=c["model"], configPolicy=c["policy"],
            selected=tc["selected"], scored=tc["scored"], byStatus=tc["byStatus"], errorCodes=tc["errorCodes"],
            excluded=tc["excluded"], recoveredQa=rec["recoveredQa"], recoveryDeclined=rec["declined"],
            scoredWithRecovery=tc["scored"] + rec["recoveredQa"],
            strict={m: c["relationshipActive"][m] for m in METRICS},
            recovered={m: c["relationshipActiveWithRecovery"][m] for m in METRICS},
        ))
labels = [c["cell"] for c in cells]
assert len(labels) == len(set(labels)) == 110, len(labels)
# provenance must agree across sources
shas = {p["labels"]["sha256"] for p in provenance.values()}
assert len(shas) == 1, shas
json.dump(dict(provenance=provenance, cells=sorted(cells, key=lambda c: (c["family"], c["policy"], c["requester"]))),
          open(os.path.join(ROOT, "out", "cells.json"), "w"), indent=1)

n = 0
with open(os.path.join(ROOT, "out", "tasks.jsonl"), "w") as out:
    for src, _ in SOURCES:
        for f in sorted(glob.glob(os.path.join(ROOT, src, "tasks", "*.tasks.jsonl"))):
            label = os.path.basename(f)[: -len(".tasks.jsonl")]
            fam, policy, req = parse_label(label)
            meta = FAMILY[fam]
            for line in open(f):
                r = json.loads(line)
                r.update(cell=label, family=fam, policy=policy, requester=req, responderShort=SHORT[meta["responder"]],
                         requesterShort=SHORT[meta["requester"]], harness=meta["harness"])
                out.write(json.dumps(r) + "\n"); n += 1
print(f"cells: {len(cells)}  tasks: {n}  label sha {shas.pop()[:12]}")
