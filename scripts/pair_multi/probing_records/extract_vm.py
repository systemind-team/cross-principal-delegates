#!/usr/bin/env python3
"""Freeze the PAIR II probing grid's per-ask records. Runs on the experiment VM; read-only.

For every run listed in <lane>/MANIFEST.json (2,400 sessions: 600 tasks in 200 three-task groups x four
requesters x three repetitions) it reads

  acc/<run>/contacts.local.jsonl     one row per accepted request (the first ask or a re-ask): the
                                     delivered request text, the reply text, the requester's claimed
                                     strategy and the acceptance analyser's gold-fact matcher flags
  acc/<run>/tasks.local.json         per task: terminal status and the analyser's disclosure flags
  acc/<run>/summary.json             per run: the acceptance analysis summary
  cfg/runs/<run>/multi/results.jsonl per task: the harness's scored evaluation (publicEvaluation)
  cfg/runs/<run>/multi/summary.json  per run: the harness summary (evaluation rows, usage)
  cfg/<run>.json                     the run config

and writes one gzip-compressed JSONL stream to stdout. Each line is
  {"kind": <file kind>, "runId": ..., "path": <path relative to the lane>, "bytes": n,
   "sha256": <digest of the source bytes>, "data": <parsed content>}
or {"kind": "missing", ...} when a listed file is absent. Nothing on the VM is written.

Usage (VM):    python3 extract_vm.py <grid lane dir> > stream.jsonl.gz
Then (local):  python3 build.py stream.jsonl.gz <out dir>
"""
import gzip
import hashlib
import json
import os
import sys

LANE = os.path.realpath(sys.argv[1])
FILES = (
    ("contacts", "acc/{run}/contacts.local.jsonl", "jsonl"),
    ("acc_tasks", "acc/{run}/tasks.local.json", "json"),
    ("acc_summary", "acc/{run}/summary.json", "json"),
    ("results", "cfg/runs/{run}/multi/results.jsonl", "jsonl"),
    ("harness_summary", "cfg/runs/{run}/multi/summary.json", "json"),
    ("config", "cfg/{run}.json", "json"),
)

out = gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb", mtime=0)


def emit(obj):
    out.write((json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))


manifest_bytes = open(os.path.join(LANE, "MANIFEST.json"), "rb").read()
manifest = json.loads(manifest_bytes)
emit({"kind": "manifest", "path": "MANIFEST.json", "bytes": len(manifest_bytes),
      "sha256": hashlib.sha256(manifest_bytes).hexdigest(), "data": manifest})
for entry in manifest:
    run = entry["runId"]
    for kind, pattern, fmt in FILES:
        rel = pattern.format(run=run)
        path = os.path.join(LANE, rel)
        if not os.path.isfile(path):
            emit({"kind": "missing", "of": kind, "runId": run, "path": rel})
            continue
        raw = open(path, "rb").read()
        text = raw.decode("utf-8")
        data = [json.loads(line) for line in text.splitlines() if line.strip()] if fmt == "jsonl" else json.loads(text)
        emit({"kind": kind, "runId": run, "path": rel, "bytes": len(raw),
              "sha256": hashlib.sha256(raw).hexdigest(), "data": data})
out.close()
