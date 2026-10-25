#!/usr/bin/env python3
"""P1-6: extract per-session records of the impersonation lane on the experiment VM (read only).

Run on the VM with the script on stdin and the output piped through a compressor, so nothing is written
there:
    ssh <host> "python3 - <vm>/runs/pair2spoof jobs optional | xz -9" < extract_vm.py > sessions.jsonl.xz

The fields follow the header comparison's extraction (scripts/freeze/pair2_runs/extract.py on the branch),
so the same leak classifier reads both. One JSON line per session slot (arm, replicate, group) of the named
lists (jobs.txt, optional.txt; a list file that does not exist is skipped):
  attempts   for the first attempt and its "-x2" retry: whether the run folder exists, whether it is valid
             (evaluationRows == selectedTasks, contactCalls > 0, and every provider call served by Relace: the
             scheduler's rule), its exit code and times (times.tsv), and its provider-reported cost;
  run        the folder used: the first attempt if valid, else the retry if valid, else none;
  tasks      each task's status, contactStatus and publicEvaluation;
  messages   every message of the session in ledger order: [sequence, sender, taskId, text, createdAt],
             text being the requester's stored `message` (with the prefix, in the impersonation arms) or the
             responder's `response`;
  writes     the responder's successful write operations in SharedOS's audit log: [at, action, path];
  policy_sha256, persona, responder_policy, digests (from run.json).
A final line {"policies": {sha256: text}} carries each POLICY.md text once.
"""
import glob
import hashlib
import json
import os
import sys

L = sys.argv[1]
LISTS = sys.argv[2:] or ["jobs"]
READS = {"invoke", "read", "send", "list", "search", "stat"}


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return None


def valid(m):
    """The scheduler's rule (sched.sh is_valid): every task evaluated, at least one contact, and every provider
    call served by the pinned upstream."""
    s = load(m + "/summary.json") or {}
    u = s.get("usage") or {}
    if not (s.get("evaluationRows") == s.get("selectedTasks") and (u.get("contactCalls") or 0) > 0):
        return False
    for f in glob.glob(m + "/.sharedeval-file-workflow/records/record-*.json"):
        tel = (((load(f) or {}).get("payload") or {}).get("privateEvidence") or {}).get("providerTelemetry") or {}
        for v in tel.values():
            if any(q.get("provider") != "Relace" for q in (v or {}).get("requests") or []):
                return False
    return True


times = {}
if os.path.exists(L + "/times.tsv"):
    for line in open(L + "/times.tsv"):
        f = line.rstrip("\n").split("\t")
        if len(f) == 4:
            times[f[0]] = {"start": float(f[1]), "end": float(f[2]), "rc": int(f[3])}

policies = {}
seen = set()
for name in LISTS:
    if not os.path.exists(f"{L}/{name}.txt"):
        continue
    for rid in [x.strip() for x in open(f"{L}/{name}.txt") if x.strip()]:
        if rid in seen:
            continue
        seen.add(rid)
        _, arm, rep, g = rid.split("-")
        rec = {"lane": "spoof", "list": name, "slot": rid, "arm": arm, "replicate": int(rep[1:]), "group": g,
               "attempts": {}}
        chosen = None
        for att in (rid, rid + "-x2"):
            folder = f"{L}/cfg/runs/{att}"
            m = folder + "/multi"
            s = load(m + "/summary.json") or {}
            info = {"folder": os.path.isdir(folder), "valid": os.path.isdir(m) and valid(m),
                    "cost_usd": (s.get("usage") or {}).get("costUsd"), "times": times.get(att)}
            rec["attempts"][att] = info
            if chosen is None and info["valid"]:
                chosen = m
        rec["run"] = None if chosen is None else os.path.relpath(chosen, L)
        if chosen is not None:
            rows = [json.loads(x) for x in open(chosen + "/results.jsonl")]
            rec["tasks"] = [{"task": x.get("taskId"), "status": x.get("status"), "contactStatus": x.get("contactStatus"),
                             "publicEvaluation": x.get("publicEvaluation")} for x in rows]
            msgs = []
            for f in glob.glob(chosen + "/.sharedeval-sharedos-session/messages/record-*.json"):
                e = load(f)
                env = e["envelope"]
                pl = env["payload"]
                who = env["sender"]["agentId"]
                msgs.append([e["sequence"], who, pl.get("taskId"),
                             pl.get("message") if who == "requester" else pl.get("response"), env.get("createdAt")])
            rec["messages"] = sorted(msgs, key=lambda x: x[0])
            writes = []
            for f in glob.glob(chosen + "/.sharedeval-sharedos-session/audit/record-*.json"):
                ev = (load(f) or {}).get("event") or {}
                if ((ev.get("actor") or {}).get("agentId") == "responder" and ev.get("outcome") == "succeeded"
                        and ev.get("action") and ev["action"] not in READS):
                    writes.append([ev.get("at"), ev["action"], (ev.get("resource") or {}).get("path")])
            rec["writes"] = sorted(writes, key=lambda x: str(x[0]))
            ps = glob.glob(chosen[:-len("/multi")] + "/workspaces/runs/*/workspaces/responder/versions/*/POLICY.md")
            shas = []
            for t in sorted({open(p).read() for p in ps}):
                h = hashlib.sha256(t.encode()).hexdigest()
                policies[h] = t
                shas.append(h)
            rec["policy_sha256"] = shas
            run = load(chosen + "/run.json") or {}
            req = (run.get("actors") or {}).get("requester") or {}
            rec["persona"] = ((req.get("references") or {}).get("agent") or {}).get("id")
            pol = (run.get("policies") or {}).get("responder") or {}
            rec["responder_policy"] = [pol.get("id"), pol.get("sha256")]
            rec["kernel"] = (run.get("backend") or {}).get("kernelRevision")
            rec["selected_task_digest"] = run.get("selectedTaskDigest")
        print(json.dumps(rec, ensure_ascii=False))
print(json.dumps({"policies": policies}, ensure_ascii=False))
