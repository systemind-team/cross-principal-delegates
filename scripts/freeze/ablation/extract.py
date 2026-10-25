#!/usr/bin/env python3
"""Extract the records behind Appendix D.6 (Table 33, the 60-task ladder) from the experiment VM (read only).

Run on the VM with the script on stdin and the output piped through a compressor, so nothing is written there:
    ssh <host> "python3 - | xz -9" < extract.py > ablation.jsonl.xz

Sources (2026-09-23/24 runs, DeepSeek-V4-Flash-0731 on Azure, category grading):
  <vm>/runs/ablation   960 sessions: AB-D0T (D0, strict), AB-D1T (D1, strict), AB-D0S (D0, simple),
                                    AB-D2S (D2, simple); 20 three-task groups x R0-R3 x three repetitions each
  <vm>/runs/grid600    the probing grid (D2, strict); only the sessions that contain one of the 60
                                    tasks of SAMPLE60.json["all"]

One JSON line per session: the lane, the manifest entry (runId, policy, profile, requester, rep, group, tasks),
the run folder's validity by the analyses' rule (evaluationRows == selectedTasks and contactCalls > 0), the run
status and stop reason, each task's status, contactStatus, errorCode and publicEvaluation, every message of the
session in ledger order (sequence, sender, task, text), the sha256 of every POLICY.md version the responder held and the
run's sourceRevision when recorded. A final line carries each policy text once, SAMPLE60.json and both manifests'
sha256.
"""
import glob
import hashlib
import json
import os

LANES = {"ablation": "<vm>/runs/ablation", "grid600": "<vm>/runs/grid600"}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def valid(m):
    try:
        s = json.load(open(m + "/summary.json"))
        u = s.get("usage") or {}
        return s.get("evaluationRows") == s.get("selectedTasks") and (u.get("contactCalls") or 0) > 0
    except (OSError, ValueError):
        return False


def record(lane, L, entry, policies):
    rid = entry["runId"]
    m = f"{L}/cfg/runs/{rid}/multi"
    rec = {"lane": lane, **entry, "valid": valid(m), "exists": os.path.isdir(m)}
    if not rec["exists"]:
        return rec
    try:
        run = json.load(open(m + "/run.json"))
        rec["status"], rec["stopReason"] = run.get("status"), run.get("stopReason")
        rec["sourceRevision"] = (run.get("backend") or {}).get("sourceRevision") or run.get("sourceRevision")
    except (OSError, ValueError):
        pass
    try:
        rows = [json.loads(l) for l in open(m + "/results.jsonl")]
    except OSError:
        rows = []
    rec["tasks_out"] = [{"task": x.get("taskId"), "status": x.get("status"), "contactStatus": x.get("contactStatus"),
                         "errorCode": x.get("errorCode"), "publicEvaluation": x.get("publicEvaluation")} for x in rows]
    msgs = []
    for f in glob.glob(m + "/.sharedeval-sharedos-session/messages/record-*.json"):
        e = json.load(open(f))
        env = e["envelope"]
        pl = env["payload"]
        who = env["sender"]["agentId"]
        text = pl.get("message") if who == "requester" else pl.get("response")
        msgs.append([e["sequence"], who, pl.get("taskId"), text])
    rec["messages"] = sorted(msgs, key=lambda x: x[0])
    shas = []
    for t in sorted({open(p, encoding="utf-8").read() for p in
                     glob.glob(m[:-len("/multi")] + "/workspaces/runs/*/workspaces/responder/versions/*/POLICY.md")}):
        h = hashlib.sha256(t.encode()).hexdigest()
        policies[h] = t
        shas.append(h)
    rec["policy_sha256"] = shas
    return rec


def main():
    policies = {}
    sample = json.load(open(LANES["grid600"] + "/SAMPLE60.json"))
    want = set(sample["all"])
    for lane, L in LANES.items():
        manifest = json.load(open(L + "/MANIFEST.json"))
        for entry in manifest:
            if lane == "grid600" and not want & set(entry.get("tasks", [])):
                continue
            print(json.dumps(record(lane, L, entry, policies), ensure_ascii=False))
    print(json.dumps({"policies": policies, "sample60": sample,
                      "manifest_sha256": {lane: sha(L + "/MANIFEST.json") for lane, L in LANES.items()},
                      "sample60_sha256": sha(LANES["grid600"] + "/SAMPLE60.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
