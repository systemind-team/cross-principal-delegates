#!/usr/bin/env python3
"""Freeze the five annotation passes behind the relationship labels, anonymized.

Reads SharedEval commit 49e043b (pact_pair/annotation/campaign_v2/) with `git show` from a local clone and
writes evidence/v3.14/labels/:
  annotation_passes.csv   one row per (true row, requester): kind, the five passes' labels, columns
                          A1-A4 and E. A1-A4 are the four annotator files other than E, in the alphabetical
                          order of their (unprinted) file names; E keeps its name because the authors are being
                          asked about it. Labels are normalized as acceptance_qc_v3.py does (questions P/L,
                          actions REFUSE/EXECUTE; the QC's lenient aliases E->L, R->P on questions).
                          Probe repeats are dropped (first occurrence of each true row, as the QC script does).
  qc_v3_majority.csv      the campaign's own majority file, copied unchanged (it carries no names)
  instructions_v2.md      INSTRUCTIONS.md as annotators received it, copied unchanged
  SOURCES.json            sha256 of every source blob read
Usage: freeze_annotations.py <SharedEval clone>
"""
import csv
import hashlib
import io
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/v3.14/labels"
REV = "49e043b"
BASE = "pact_pair/annotation/campaign_v2"
QA = {"P": "P", "L": "L", "E": "L", "EXECUTE": "L", "R": "P", "REFUSE": "P"}
ACT = {"REFUSE": "REFUSE", "R": "REFUSE", "P": "REFUSE", "EXECUTE": "EXECUTE", "E": "EXECUTE", "L": "EXECUTE"}


def show(clone, path):
    return subprocess.run(["git", "-C", clone, "show", f"{REV}:{path}"], check=True, capture_output=True).stdout


def main():
    clone = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(show(clone, f"{BASE}/assignment_manifest_v3.json"))
    names = sorted(manifest["annotators"])
    others = sorted(n for n in names if n != "E")
    alias = {n: f"A{i + 1}" for i, n in enumerate(others)}
    alias["E"] = "E"
    sources = {}
    passes = {}
    for n in names:
        filled = show(clone, f"{BASE}/filled_v3/{n}.csv")
        key = show(clone, f"{BASE}/keys_v3/{n}_key.csv")
        sources[f"filled_v3/<{alias[n]}>.csv"] = hashlib.sha256(filled).hexdigest()
        sources[f"keys_v3/<{alias[n]}>_key.csv"] = hashlib.sha256(key).hexdigest()
        true_row = {r["row_code"].strip(): r["true_row"].strip() for r in csv.DictReader(io.StringIO(key.decode()))}
        labels = {}
        for rec in csv.DictReader(io.StringIO(filled.decode())):
            t = true_row[rec["row_code"].strip()]
            if t in labels:
                continue
            kind = "qa" if t.startswith("Q") else "action"
            table = QA if kind == "qa" else ACT
            labels[t] = {r: table[rec[r].strip().upper()] for r in ("R0", "R1", "R2", "R3", "R4")}
        assert len(labels) == 401, (alias[n], len(labels))
        passes[alias[n]] = labels
    cols = ["A1", "A2", "A3", "A4", "E"]
    rows = sorted(passes["E"], key=lambda t: (t[0], int(t[1:])))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "kind", "requester"] + cols)
    for t in rows:
        for r in ("R0", "R1", "R2", "R3", "R4"):
            w.writerow([t, "qa" if t.startswith("Q") else "action", r] + [passes[c][t][r] for c in cols])
    (OUT / "annotation_passes.csv").write_text(buf.getvalue())
    maj = show(clone, f"{BASE}/qc_v3_majority.csv")
    (OUT / "qc_v3_majority.csv").write_bytes(maj)
    sources["qc_v3_majority.csv"] = hashlib.sha256(maj).hexdigest()
    ins = show(clone, f"{BASE}/INSTRUCTIONS.md")
    (OUT / "instructions_v2.md").write_bytes(ins)
    sources["INSTRUCTIONS.md"] = hashlib.sha256(ins).hexdigest()
    (OUT / "SOURCES.json").write_text(json.dumps({"sharedeval_commit": REV, "path": BASE, "sha256": sources},
                                                 indent=1, sort_keys=True) + "\n")
    print(f"froze {len(rows)} rows x 5 requesters x 5 passes")


if __name__ == "__main__":
    main()
