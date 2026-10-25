#!/usr/bin/env python3
"""Freeze the NET world files that audience_edges.py reads. Read-only on sources.

    python3 scripts/freeze/net_edges/freeze_world.py \
        --sharedeval $SHAREDEVAL_CLONE --vm-hashes vm_hashes.json

Writes only under evidence/v3.14/net-world/ (run from the worktree root):

  world/dataset/pact-net/...   exact bytes of the NET world at SharedEval d44e478 (the NET rerun's revision,
                               VM clone <vm>/repos/SE-net-e1). d44e478 is not in the local clone,
                               but its root tree 00eecd0b... is (it is also the tree of 6773638 on
                               origin/net/register-missing-workspaces), so the blobs are read locally by tree id
                               and the VM's own sha256 of the same paths (vm_hashes.py) must agree.
  registry/channel_registry.json   SharedEval ab6bb51 (branch net/differential-disclosure), NOT part of d44e478:
                               the repository's own binding of the 38 audience labels to membership modes.
  paired_edges_24.json         the 24 edges the NET rerun paired, read from evidence/v3.13/net-rerun/contacts.jsonl.
  sources.json, SHA256SUMS     where every frozen file came from, and its sha256.

Which world files are frozen is decided from the world itself: the task file, the access matrix and the
contact graph; systems.json for every agent in the contact graph (organisation membership); data.json for
every holder of a forbidden entry (the sensitivity of the note holding the fact); contact_book.json for the
anchor of every kinship-mode audience in the registry.
"""
import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys

D44E478 = "d44e4788562c438a97180443ee8cc5170094ad07"
D44E478_TREE = "00eecd0bc16b37a170949afeb23f34bcedb8ad23"
REGISTRY_COMMIT = "ab6bb51"
REGISTRY_PATH = "dataset/pact-net/world_design/channel_registry.json"
NET = "dataset/pact-net"
OUT = "evidence/v3.14/net-world"
CONTACTS = "evidence/v3.13/net-rerun/contacts.jsonl"


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True).stdout


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sharedeval", default=os.environ.get("SHAREDEVAL_CLONE", "SharedEval"))   # a local SharedEval clone
    ap.add_argument("--vm-hashes", required=True, help="output of vm_hashes.py run on the VM")
    a = ap.parse_args()
    if not os.path.isdir(OUT):
        sys.exit(f"run from the worktree root ({OUT} not found)")
    se = a.sharedeval
    vm = json.load(open(a.vm_hashes))
    if vm["commit"] != D44E478 or vm["tree"] != D44E478_TREE:
        sys.exit(f"VM reports {vm['commit']} / tree {vm['tree']}, expected {D44E478} / {D44E478_TREE}")
    if git(se, "cat-file", "-t", D44E478_TREE).decode().strip() != "tree":
        sys.exit("tree 00eecd0b is not in the local SharedEval clone")

    def blob_of(path):
        return git(se, "rev-parse", f"{D44E478_TREE}:{path}").decode().strip()

    def read(path):
        return git(se, "cat-file", "blob", blob_of(path))

    tasks = json.loads(read(f"{NET}/tasks/pact_net_tasks_v2.json"))["tasks"]
    graph = json.loads(read(f"{NET}/world_design/contact_graph.json"))
    agents = sorted(graph["agents"])
    holders = sorted({f["holder"] for t in tasks for f in (t.get("forbidden") or [])})
    reg_blob = git(se, "rev-parse", f"{REGISTRY_COMMIT}:{REGISTRY_PATH}").decode().strip()
    registry_bytes = git(se, "cat-file", "blob", reg_blob)
    registry = json.loads(registry_bytes)
    anchors = set()
    for label, ch in registry["channels"].items():
        if ch["mode"] == "kinship":
            if ch.get("anchored_by") == "forbidden.holder":
                anchors |= {f["holder"] for t in tasks for f in (t.get("forbidden") or []) if f["forbidden_to"] == label}
            else:
                anchors.add(ch["anchor"])

    paths = [f"{NET}/tasks/pact_net_tasks_v2.json", f"{NET}/world_design/relational_access_matrix.json",
             f"{NET}/world_design/contact_graph.json"]
    paths += [f"{NET}/agent_configs/{x}/systems.json" for x in agents]
    tree_names = set(git(se, "ls-tree", "-r", "--name-only", D44E478_TREE, "--", f"{NET}/agent_configs").decode().split())
    no_store = [h for h in holders if f"{NET}/agent_configs/{h}/data.json" not in tree_names]
    paths += [f"{NET}/agent_configs/{h}/data.json" for h in holders if h not in no_store]
    paths += [f"{NET}/agent_configs/{x}/contact_book.json" for x in sorted(anchors)]

    sources = {}
    for p in paths:
        body = read(p)
        dest = os.path.join(OUT, "world", p)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(body)
        v = vm["files"].get(p)
        if v is None or v["sha256"] != sha256(body) or v["blob"] != blob_of(p) or v["bytes"] != len(body):
            sys.exit(f"VM hash disagrees for {p}: {v}")
        sources[f"world/{p}"] = {
            "source": f"SharedEval {D44E478} (VM clone {vm['repo']}), path {p}",
            "git_blob": blob_of(p), "bytes": len(body), "sha256": sha256(body),
            "vm_sha256_of_git_show": v["sha256"],
        }

    dest = os.path.join(OUT, "registry", "channel_registry.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(registry_bytes)
    reg_commit = git(se, "rev-parse", REGISTRY_COMMIT + "^{commit}").decode().strip()
    sources["registry/channel_registry.json"] = {
        "source": f"SharedEval {reg_commit} (local clone {se}, branch net/differential-disclosure), path {REGISTRY_PATH}",
        "git_blob": reg_blob, "bytes": len(registry_bytes), "sha256": sha256(registry_bytes),
        "in_d44e478": f"{NET}/world_design/channel_registry.json" in set(
            git(se, "ls-tree", "-r", "--name-only", D44E478_TREE, "--", f"{NET}/world_design").decode().split()),
        "note": "Used only for each audience label's membership mode and resolver parameters; members are "
                "recomputed from the frozen world files by audience_edges.py.",
    }

    # The 24 paired edges, as the rerun ran them.
    raw = open(CONTACTS, "rb").read()
    pairs = collections.defaultdict(lambda: collections.defaultdict(set))
    meta = {}
    for line in raw.decode().splitlines():
        r = json.loads(line)
        pairs[r["edge"]][r["arm"]].add(r["asker"])
        m = (r["holder"], r["fact_category"], r["borderline"])
        if meta.setdefault(r["edge"], m) != m:
            sys.exit(f"inconsistent holder/category/borderline for {r['edge']}")
    edges = []
    for e in sorted(pairs):
        w, p = pairs[e]["withheld"], pairs[e]["permitted"]
        if len(w) != 1 or len(p) != 1:
            sys.exit(f"{e}: expected one asker per arm, got {w} / {p}")
        h, cat, borderline = meta[e]
        edges.append({"edge": e, "holder": h, "fact_category": cat, "borderline": borderline,
                      "withheld_requester": next(iter(w)), "permitted_requester": next(iter(p))})
    doc = {"what": "The 24 forbidden edges the NET rerun paired: one forbidden (withheld-arm) and one permitted "
                   "requester asking the holder for the same fact.",
           "source": CONTACTS, "source_sha256": sha256(raw), "rows_read": len(raw.decode().splitlines()),
           "edges": edges}
    body = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    with open(os.path.join(OUT, "paired_edges_24.json"), "wb") as fh:
        fh.write(body)
    sources["paired_edges_24.json"] = {"source": f"derived from {CONTACTS} by freeze_world.py",
                                       "bytes": len(body), "sha256": sha256(body)}

    summary = {"d44e478": D44E478, "d44e478_tree": D44E478_TREE,
               "agents_in_contact_graph": len(agents), "forbidden_entries": sum(len(t.get("forbidden") or []) for t in tasks),
               "holders": len(holders), "holders_without_bundled_data_json": no_store,
               "kinship_anchors": sorted(anchors), "files": sources}
    with open(os.path.join(OUT, "sources.json"), "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    lines = []
    for root, _dirs, files in os.walk(OUT):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, OUT)
            if rel in ("SHA256SUMS", "README.md", "audience_edges.json"):
                continue
            lines.append(f"{sha256(open(full, 'rb').read())}  {rel}")
    with open(os.path.join(OUT, "SHA256SUMS"), "w") as fh:
        fh.write("\n".join(sorted(lines, key=lambda s: s.split("  ", 1)[1])) + "\n")
    print(f"froze {len(sources)} files ({len(paths)} world files, all equal to the VM's sha256); "
          f"holders without data.json: {no_store}; kinship anchors: {sorted(anchors)}")


if __name__ == "__main__":
    main()
