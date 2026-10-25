#!/usr/bin/env python3
"""Freeze the NET rerun's grants and the holders' policy files from the VM extraction, after checking it against the record.

Input: --extraction, the gzipped JSONL that extract.py prints on the VM (see the README in evidence/v3.14/net-grants/).
Read only: evidence/v3.13/net-rerun/{contacts.jsonl, replies.jsonl, manifest.json}, evidence/v3.14/net-world/sources.json.

Nothing is written unless every check passes:
  - each of the 720 frozen contacts (model, run id) finds exactly one extracted run folder, with the same rung, edge and
    arm, and no extracted run is left over;
  - each of the 1,306 frozen judged replies finds its run's responder reply with the same sequence and a response
    sha256 equal to the recorded reply_sha256;
  - the d44e478 tree equals the one the frozen NET world records;
  - every POLICY.md version a responder held equals the rung's text: empty at D0, the 128-byte caution at D1, and at D2
    the holder's own POLICY.md blob at d44e478.

Writes evidence/v3.14/net-grants/ (grants.jsonl.gz: each run's grants.json as stored, with its sha256; summary.json:
the counts, normalized below) and evidence/v3.14/net-world/policies/ (the 14 holders' D2 POLICY.md at d44e478, D1's
caution, policies.json with digests and the runs that served each, SHA256SUMS).

A grant is normalized by dropping its id, issue time, notBefore and namespace id and replacing the run's task id with
"<task>", so two runs' grants compare by subject, actions, resource, scope and constraints.
Usage: python3 scripts/freeze/net_run_files/freeze.py --extraction net_run_files.jsonl.gz
"""
import argparse
import collections
import gzip
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
RERUN = ROOT / "evidence/v3.13/net-rerun"
GRANTS = ROOT / "evidence/v3.14/net-grants"
POL = ROOT / "evidence/v3.14/net-world/policies"
EMPTY = hashlib.sha256(b"").hexdigest()


def edge_code(cfg_edge):
    """h06 -> H-06, ep04 -> EP-04, roi01 -> ROI-01."""
    i = next(k for k, ch in enumerate(cfg_edge) if ch.isdigit())
    return f"{cfg_edge[:i].upper()}-{cfg_edge[i:]}"


def normalize(grant, task):
    g = json.loads(json.dumps(grant).replace(task, "<task>"))
    for k in ("id", "issuedAt", "namespaceId"):
        g.pop(k, None)
    g.get("constraints", {}).pop("notBefore", None)
    return json.dumps(g, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extraction", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in gzip.open(a.extraction, "rt")]
    for r in rows[:-1]:              # the frozen record names the "w" arm "withheld" (the paper's forbidden arm)
        r["arm"] = {"forbidden": "withheld"}.get(r["arm"], r["arm"])
    final = rows[-1]
    runs = {(r["model"], r["run_id"]): r for r in rows[:-1]}
    assert final.get("final") and len(runs) == len(rows) - 1, "one row per run folder"
    contacts = [json.loads(l) for l in open(RERUN / "contacts.jsonl")]
    replies = [json.loads(l) for l in open(RERUN / "replies.jsonl")]
    world = json.loads((ROOT / "evidence/v3.14/net-world/sources.json").read_text())

    # 1. contacts <-> run folders
    seen = set()
    for c in contacts:
        r = runs[(c["model"], c["run_id"])]
        assert (r["rung"], edge_code(r["edge"]), r["arm"]) == (c["rung"], c["edge"], c["arm"]), c["run_id"]
        seen.add((c["model"], c["run_id"]))
    assert seen == set(runs), "an extracted run folder no contact accounts for"
    # 2. judged replies <-> the runs' responder replies
    for rp in replies:
        got = {x["sequence"]: x["response_sha256"] for x in runs[(rp["model"], rp["run_id"])]["responder_replies"]}
        assert got.get(rp["sequence"]) == rp["reply_sha256"], (rp["run_id"], rp["sequence"])
    # 3. the world revision
    assert final["d44e478"] == world["d44e478"] and final["d44e478_tree"] == world["d44e478_tree"]
    # 4. the policy each responder held
    holder_of = {(c["model"], c["run_id"]): c["holder"] for c in contacts}
    texts, ds = final["policy_texts"], final["dataset"]
    caution = [h for h, t in texts.items() if len(t.encode()) == 128]
    assert len(caution) == 1
    served = collections.defaultdict(list)
    versions_differ = []
    for key, r in runs.items():
        holder = holder_of[key]
        want = {"D0": EMPTY, "D1": caution[0],
                "D2": ds[f"dataset/pact-net/agent_configs/{holder}/POLICY.md"]["sha256"]}[r["rung"]]
        shas = [p["sha256"] for p in r["responder_policies"]]
        assert shas and all(s == want for s in shas), (key, r["rung"], shas)
        if len(shas) > 1:
            versions_differ.append(r["run_id"])
        served[(r["rung"], holder if r["rung"] == "D2" else None)].append(f"{r['model']}/{r['run_id']}")

    # grants
    per_run = {}
    for key, r in runs.items():
        task = next(c for c in contacts if (c["model"], c["run_id"]) == key)
        tid = sorted({cap["resource"]["path"][1] for g in r["grants"]["grants"] for cap in g["capabilities"]
                      if cap["resource"]["path"][:1] == ["task"]})
        assert len(tid) == 1, key
        per_run[key] = sorted(normalize(g, tid[0]) for g in r["grants"]["grants"])
    n_grants = collections.Counter(len(r["grants"]["grants"]) for r in runs.values())
    scopes = collections.Counter(c["scope"] for r in runs.values() for g in r["grants"]["grants"] for c in g["capabilities"])
    subjects = collections.Counter(g["subject"]["agentId"] for r in runs.values() for g in r["grants"]["grants"])
    distinct = sorted(set(json.dumps(v) for v in per_run.values()))
    pairs = collections.defaultdict(dict)
    for c in contacts:
        pairs[(c["model"], c["rung"], c["edge"], c["rep"])][c["arm"]] = per_run[(c["model"], c["run_id"])]
    complete = {k: v for k, v in pairs.items() if len(v) == 2}
    same_arms = sum(v["withheld"] == v["permitted"] for v in complete.values())
    summary = {
        "runs": len(runs), "by_model": dict(collections.Counter(m for m, _ in runs)),
        "grants_per_run": dict(n_grants), "scopes": dict(scopes),
        "grants_per_run_by_subject": {s: n // len(runs) for s, n in subjects.items()},
        "capabilities_per_grant": dict(collections.Counter(len(g["capabilities"]) for r in runs.values()
                                                            for g in r["grants"]["grants"])),
        "distinct_normalized_grant_sets": len(distinct),
        "edge_rung_rep_pairs_with_both_arms": len(complete), "pairs_with_identical_grants_on_both_arms": same_arms,
        "normalized_grant_set": json.loads(distinct[0]) if len(distinct) == 1 else None,
        "normalization": "id, issuedAt, notBefore and namespaceId dropped; the run's task id replaced by <task>",
        "checks": {"contacts_matched": len(contacts), "judged_replies_matched": len(replies),
                   "d44e478_tree": final["d44e478_tree"], "policy_texts_as_expected": True}}
    GRANTS.mkdir(parents=True, exist_ok=True)
    with gzip.open(GRANTS / "grants.jsonl.gz", "wt", compresslevel=9) as f:
        for (model, run_id), r in sorted(runs.items()):
            f.write(json.dumps({"model": model, "run_id": run_id, "rung": r["rung"], "edge": edge_code(r["edge"]),
                                "arm": r["arm"], "grants_sha256": r["grants_sha256"], "grants": r["grants"]},
                               sort_keys=True) + "\n")
    (GRANTS / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")

    # policies
    POL.mkdir(parents=True, exist_ok=True)
    holders = sorted({c["holder"] for c in contacts})
    info = {"d44e478": final["d44e478"], "d44e478_tree": final["d44e478_tree"], "D0": {"sha256": EMPTY, "bytes": 0,
            "runs": len(served[("D0", None)])}, "holders": {}, "responder_versions_beyond_the_first": versions_differ,
            "note": "every POLICY.md version a responder held equals the rung's text; the runs listed under "
                    "responder_versions_beyond_the_first re-saved the same text"}
    (POL / "D1_caution.md").write_text(texts[caution[0]])
    info["D1"] = {"file": "D1_caution.md", "sha256": caution[0], "bytes": 128, "runs": len(served[("D1", None)])}
    sums = [f"{caution[0]}  D1_caution.md"]
    for h in holders:
        d = ds[f"dataset/pact-net/agent_configs/{h}/POLICY.md"]
        (POL / f"{h}.md").write_text(d["text"])
        assert hashlib.sha256((POL / f"{h}.md").read_bytes()).hexdigest() == d["sha256"]
        info["holders"][h] = {"file": f"{h}.md", "sha256": d["sha256"], "git_blob": d["git_blob"],
                              "path_at_d44e478": f"dataset/pact-net/agent_configs/{h}/POLICY.md",
                              "d2_runs_served": len(served[("D2", h)])}
        sums.append(f"{d['sha256']}  {h}.md")
    (POL / "policies.json").write_text(json.dumps(info, indent=1, sort_keys=True) + "\n")
    (POL / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({k: summary[k] for k in ("runs", "grants_per_run", "scopes", "grants_per_run_by_subject",
                                              "distinct_normalized_grant_sets", "edge_rung_rep_pairs_with_both_arms",
                                              "pairs_with_identical_grants_on_both_arms")}, indent=1))
    print("holders frozen:", len(holders))


if __name__ == "__main__":
    main()
