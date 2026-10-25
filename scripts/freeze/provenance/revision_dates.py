#!/usr/bin/env python3
"""The commit dates of every evaluator and kernel revision of Table 9 (E2's three merges: how far apart).

Reads evidence/v3.14/provenance/revision_labels.json (label -> full commit ids) and looks each commit up, read only, in
the local clones (`git log -1`, author and committer dates in ISO 8601 with the committer's offset). Records no commit
subject or author. Writes evidence/v3.14/provenance/revision_dates.json: per label, each commit's dates, and for a
label with several commits the span from the first committer date to the last.
Usage: python3 scripts/freeze/provenance/revision_dates.py [--sharedeval PATH] [--sharedos PATH]
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROV = ROOT / "evidence/v3.14/provenance"


def dates(repo, rev):
    out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%H%x00%ad%x00%cd", "--date=iso-strict", rev],
                         capture_output=True, text=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if out.returncode:
        return None
    h, ad, cd = out.stdout.strip().split("\x00")
    return {"commit": h, "author_date": ad, "committer_date": cd}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sharedeval", default=os.environ.get("SHAREDEVAL_CLONE", str(pathlib.Path.home() / "SharedEval")))
    ap.add_argument("--sharedos", default=os.environ.get("SHAREDOS_CLONE", str(pathlib.Path.home() / "SharedOS")))
    a = ap.parse_args()
    labels = json.loads((PROV / "revision_labels.json").read_text())
    out = {"source": "git log -1 in the local SharedEval (E*) and SharedOS (K*) clones, read only; no subject or author "
                     "is recorded", "labels": {}}
    for label, revs in labels.items():
        repo = a.sharedos if label.startswith("K") else a.sharedeval
        revs = revs if isinstance(revs, list) else [revs]
        got = []
        for r in revs:
            d = dates(repo, r)
            got.append(d if d else {"commit": r, "missing_from_clone": True})
        entry = {"commits": got}
        cds = [datetime.datetime.fromisoformat(g["committer_date"]) for g in got if "committer_date" in g]
        if len(cds) > 1 and len(cds) == len(got):
            span = max(cds) - min(cds)
            entry["span_first_to_last_committer_date"] = str(span)
            entry["span_hours"] = round(span.total_seconds() / 3600, 2)
        out["labels"][label] = entry
    (PROV / "revision_dates.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v.get("span_first_to_last_committer_date") for k, v in out["labels"].items()}, indent=1))


if __name__ == "__main__":
    main()
