#!/usr/bin/env python3
"""Write the frozen probing-grid records from the stream that extract_vm.py produces.

Usage:  python3 build.py <stream.jsonl.gz> <out dir>
        (out dir = evidence/v3.14/multi-probing-records)

Output files (gzip with a zero timestamp, so the bytes are reproducible from the same stream):
  contacts.jsonl.gz  one row per accepted request (first ask or re-ask), in run order then contact order:
                     the analyser's row plus runId, requester, rep, group; sourceRecord made lane-relative
  tasks.jsonl.gz     one row per (run, task): the analyser's per-task row
  results.jsonl.gz   one row per (run, task): the harness's result row (publicEvaluation)
  runs.jsonl.gz      one row per run: requester, rep, group, tasks, the analyser's summary, the harness
                     summary and the run config (the provider endpoint replaced by a placeholder)
  sources.tsv.gz     every source file read on the VM: kind, lane-relative path, bytes, sha256 of the
                     original bytes (before any rewrite)
  SHA256SUMS         digests of the files above

Two rewrites, both of metadata and never of model text: absolute paths in contacts' sourceRecord become
paths relative to the grid's lane directory, and config.model.endpoint becomes "<azure-endpoint>". The
digests in sources.tsv.gz are of the original bytes, so a holder of the VM files can verify them.
"""
import gzip
import hashlib
import io
import json
import os
import re
import sys

STREAM, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
LANE_PREFIX = re.compile(r"^/[^ ]*?/runs/grid600/")


def gz_writer(name):
    raw = open(os.path.join(OUT, name), "wb")
    return raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0)


def line(fh, obj):
    fh.write((json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))


names = ("contacts.jsonl.gz", "tasks.jsonl.gz", "results.jsonl.gz", "runs.jsonl.gz", "sources.tsv.gz")
handles = {n: gz_writer(n) for n in names}
meta = {}
runs = {}
counts = {"contacts": 0, "tasks": 0, "results": 0, "runs": 0, "sources": 0, "missing": 0}

with gzip.open(STREAM, "rt", encoding="utf-8") as stream:
    records = [json.loads(l) for l in stream]

manifest = next(r for r in records if r["kind"] == "manifest")
for entry in manifest["data"]:
    meta[entry["runId"]] = {"requester": entry["requester"], "rep": entry["rep"], "group": entry["group"],
                            "tasks": entry["tasks"]}
src = handles["sources.tsv.gz"][1]
src.write(b"kind\tpath\tbytes\tsha256\n")
src.write(f"manifest\t{manifest['path']}\t{manifest['bytes']}\t{manifest['sha256']}\n".encode())
counts["sources"] += 1

by_run = {}
for r in records:
    if r["kind"] == "manifest":
        continue
    if r["kind"] == "missing":
        counts["missing"] += 1
        continue
    by_run.setdefault(r["runId"], {})[r["kind"]] = r
    src.write(f"{r['kind']}\t{r['path']}\t{r['bytes']}\t{r['sha256']}\n".encode())
    counts["sources"] += 1

for entry in manifest["data"]:
    run = entry["runId"]
    m = meta[run]
    base = {"runId": run, "requester": m["requester"], "rep": m["rep"], "group": m["group"]}
    files = by_run.get(run, {})
    for row in (files.get("contacts") or {}).get("data", []):
        row = dict(row)
        if isinstance(row.get("sourceRecord"), str):
            row["sourceRecord"] = LANE_PREFIX.sub("", row["sourceRecord"])
        line(handles["contacts.jsonl.gz"][1], {**base, **row})
        counts["contacts"] += 1
    for row in (files.get("acc_tasks") or {}).get("data", []):
        line(handles["tasks.jsonl.gz"][1], {**base, **row})
        counts["tasks"] += 1
    for row in (files.get("results") or {}).get("data", []):
        line(handles["results.jsonl.gz"][1], {**base, **row})
        counts["results"] += 1
    config = (files.get("config") or {}).get("data")
    if config is not None:
        config = json.loads(json.dumps(config))
        if "endpoint" in config.get("model", {}):
            config["model"]["endpoint"] = "<azure-endpoint>"
    line(handles["runs.jsonl.gz"][1], {**base, "tasks": m["tasks"],
                                       "acceptanceSummary": (files.get("acc_summary") or {}).get("data"),
                                       "harnessSummary": (files.get("harness_summary") or {}).get("data"),
                                       "config": config})
    counts["runs"] += 1

for raw, fh in handles.values():
    fh.close()
    raw.close()

with open(os.path.join(OUT, "SHA256SUMS"), "w") as fh:
    for n in names:
        digest = hashlib.sha256(open(os.path.join(OUT, n), "rb").read()).hexdigest()
        fh.write(f"{digest}  {n}\n")
print(json.dumps(counts))
