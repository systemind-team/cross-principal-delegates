#!/usr/bin/env python3
"""Extract the NET rerun's grants and the policy files its holders read, from the experiment VM (read only).

Run on the VM with the script on stdin and the output piped through a compressor, so nothing is written there:
    ssh <host> "python3 - | gzip -9n" < extract.py > net_run_files.jsonl.gz

Sources (the 2026-10-01 rerun of evidence/v3.13/net-rerun, SharedEval d44e478):
  <vm>/runs/net-or-ds/cfg/runs/<config>/<run_id>/    DeepSeek V4 Flash (deepseek-v4-flash)
  <vm>/runs/net-or-glm/cfg/runs/<config>/<run_id>/   GLM-5.3 (glm-5.3)
  <vm>/repos/SE-net-e1 at d44e478                    dataset/pact-net/agent_configs/*/{POLICY.md,grants.json}

One JSON line per run folder: the lane and model, the run id and its config (rung, edge, arm), the session's
grants.json as stored (with its sha256), the sha256 and size of every POLICY.md version the responder held (texts once,
in the final line), the sha256 of every responder message's response text in ledger order (the frozen replies.jsonl
hashes the same field), and run.json's recorded source revision. The final line carries each distinct policy text
once, and every agent's POLICY.md and grants.json at d44e478 with their git blob ids.
"""
import glob
import hashlib
import json
import os
import re
import subprocess

LANES = {"net-or-ds": "deepseek-v4-flash", "net-or-glm": "glm-5.3"}
ROOT = "<vm>/runs"
REPO = "<vm>/repos/SE-net-e1"
REV = "d44e4788562c438a97180443ee8cc5170094ad07"
CFG = re.compile(r"^(d[012])_([a-z0-9]+)_([wp])$")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read(path):
    with open(path, "rb") as f:
        return f.read()


texts = {}
for lane, model in LANES.items():
    for run in sorted(glob.glob(f"{ROOT}/{lane}/cfg/runs/*/*")):
        cfg, run_id = run.split("/")[-2], run.split("/")[-1]
        m = CFG.match(cfg)
        if not m or not run_id.startswith(cfg + "-r"):
            continue
        row = {"lane": lane, "model": model, "config": cfg, "run_id": run_id, "rung": m.group(1).upper(),
               "edge": m.group(2), "arm": {"w": "forbidden", "p": "permitted"}[m.group(3)]}
        g = f"{run}/multi/.sharedeval-sharedos-session/grants.json"
        if os.path.exists(g):
            b = read(g)
            row["grants_sha256"], row["grants"] = sha_bytes(b), json.loads(b)
        policies = []
        for p in sorted(glob.glob(f"{run}/workspaces/runs/{run_id}/workspaces/responder/versions/*/POLICY.md")):
            b = read(p)
            h = sha_bytes(b)
            texts.setdefault(h, b.decode("utf-8"))
            policies.append({"version": p.split("/")[-2], "sha256": h, "bytes": len(b)})
        row["responder_policies"] = policies
        replies = []
        for r in sorted(glob.glob(f"{run}/multi/.sharedeval-sharedos-session/messages/record-*.json")):
            d = json.loads(read(r))
            env = d.get("envelope") or {}
            if (env.get("sender") or {}).get("agentId") == "responder":
                resp = (env.get("payload") or {}).get("response")
                replies.append({"sequence": d.get("sequence"),
                                "response_sha256": sha_bytes(resp.encode("utf-8")) if isinstance(resp, str) else None})
        row["responder_replies"] = replies
        rj = f"{run}/multi/run.json"
        if os.path.exists(rj):
            j = json.loads(read(rj))
            row["source_revision"] = j.get("sourceRevision") or (j.get("source") or {}).get("revision")
        print(json.dumps(row, sort_keys=True))

dataset = {}
names = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", REV, "--", "dataset/pact-net/agent_configs"],
                       capture_output=True, text=True, check=True).stdout.split()
for path in names:
    if path.endswith("/POLICY.md") or path.endswith("/grants.json"):
        blob = subprocess.run(["git", "-C", REPO, "rev-parse", f"{REV}:{path}"], capture_output=True, text=True,
                              check=True).stdout.strip()
        body = subprocess.run(["git", "-C", REPO, "show", f"{REV}:{path}"], capture_output=True, check=True).stdout
        dataset[path] = {"git_blob": blob, "sha256": sha_bytes(body), "text": body.decode("utf-8")}
tree = subprocess.run(["git", "-C", REPO, "rev-parse", f"{REV}^{{tree}}"], capture_output=True, text=True,
                      check=True).stdout.strip()
print(json.dumps({"final": True, "policy_texts": texts, "d44e478": REV, "d44e478_tree": tree, "dataset": dataset},
                 sort_keys=True))
