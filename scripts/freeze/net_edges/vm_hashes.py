#!/usr/bin/env python3
"""Hash, on the experiment VM, the NET world files that evidence/v3.14/net-world/ freezes. Read-only.

Run from the worktree root; the script is fed over stdin so nothing is written on the VM:

    ssh <host> python3 - < scripts/freeze/net_edges/vm_hashes.py > vm_hashes.json

It reads blobs of SharedEval commit d44e478 in the NET run's own clone
(<vm>/repos/SE-net-e1) with `git cat-file`, never the working tree, and prints one JSON
document: the commit, its tree, and for each file the blob id, size and sha256 of the blob bytes.
freeze_world.py compares these with the bytes it froze locally.

Files covered (paths under dataset/pact-net/):
  tasks/pact_net_tasks_v2.json, world_design/relational_access_matrix.json,
  world_design/contact_graph.json, every agent_configs/*/systems.json, every agent_configs/*/data.json,
  agent_configs/david_chen/contact_book.json.
No other file is opened; nothing is printed except paths, ids, sizes and hashes.
"""
import hashlib
import json
import os
import subprocess

REPO = "<vm>/repos/SE-net-e1"
REV = "d44e4788562c438a97180443ee8cc5170094ad07"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"   # never refresh the index: nothing is written


def git(*args, data=None):
    return subprocess.run(["git", "-C", REPO, *args], input=data, capture_output=True, check=True).stdout


def wanted(path):
    rel = path[len("dataset/pact-net/"):]
    if rel in ("tasks/pact_net_tasks_v2.json", "world_design/relational_access_matrix.json",
               "world_design/contact_graph.json", "agent_configs/david_chen/contact_book.json"):
        return True
    parts = rel.split("/")
    return len(parts) == 3 and parts[0] == "agent_configs" and parts[2] in ("systems.json", "data.json")


commit = git("rev-parse", REV + "^{commit}").decode().strip()
tree = git("rev-parse", REV + "^{tree}").decode().strip()
entries = []
for line in git("ls-tree", "-r", REV, "--", "dataset/pact-net").decode().splitlines():
    meta, path = line.split("\t", 1)
    _mode, kind, blob = meta.split()
    if kind == "blob" and wanted(path):
        entries.append((path, blob))
files = {}
for path, blob in entries:
    body = git("cat-file", "blob", blob)
    files[path] = {"blob": blob, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
print(json.dumps({"repo": REPO, "commit": commit, "tree": tree, "files": files}, indent=1, sort_keys=True))
