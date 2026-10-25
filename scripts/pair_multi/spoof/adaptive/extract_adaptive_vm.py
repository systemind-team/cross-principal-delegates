#!/usr/bin/env python3
"""P2-3 adaptive extractor. Extracts per-session records of the adaptive lane on the VM (read
only), like P1-6's extract_vm.py, but:
  - validity uses the PER-ACTOR route pin, not P1-6's Relace-only rule, so the attacker's Gemini calls do not
    make every session invalid. The pin defaults to responder=Relace, attacker=Relace, so on P1-6 the
    rule is identical to extract_vm.py and the valid/run set matches sessions.jsonl.xz; for the adaptive lane
    pass --responder-pin / --attacker-pin from frozen/model_config.json;
  - it adds two fields the adaptive classifier needs:
      tactics {taskId: [tactic per requester turn]} parsed from the requester's own MEMORY.md `tactic=`
                     note as it evolves (the private channel; absent/empty on P1-6, which declares no tactic);
      writes_by_task {taskId: [[at, action, surface], ...]} grouped from the responder write log, so a
                     question-task write is counted and an action is dated by its first write.
Request times are already in `messages` (each row's 5th element is createdAt).

Run on the VM with the script on stdin so nothing is written there:
    ssh <host> "python3 - <vm>/runs/pair2spoof jobs optional | xz -9" < extract_adaptive_vm.py > sessions.jsonl.xz
The output schema is a superset of extract_vm.py's, so classify_adaptive.mjs reads either.
"""
import base64
import glob
import hashlib
import json
import os
import re
import sys

ARGS = [a for a in sys.argv[1:]]
RESP_PIN = "Relace"
ATT_PIN = "Relace"
for flag, default in (("--responder-pin", None), ("--attacker-pin", None)):
    if flag in ARGS:
        i = ARGS.index(flag)
        val = ARGS[i + 1]
        if flag == "--responder-pin":
            RESP_PIN = val
        else:
            ATT_PIN = val
        del ARGS[i:i + 2]
L = ARGS[0]
LISTS = ARGS[1:] or ["jobs"]
READS = {"invoke", "read", "send", "list", "search", "stat"}
PINS = {"responder": RESP_PIN, "requester": ATT_PIN}
ROW = re.compile(r"^(PAIR-[A-Za-z0-9._:-]+)\s+\[(answered|pending|refused|error)\]\s+—\s*(.*)$")
TACTIC = re.compile(r"\btactic=([^\s;]+)")


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return None


# Served-upstream name normalization: identical to delivery_adaptive.PROVIDER_ALIASES (test_route_names.py
# asserts the two tables match). The pin is a slug; SharedEval records OpenRouter's display name.
PROVIDER_ALIASES = {
    "relace": {"relace"},
    "google-ai-studio": {"google-ai-studio", "google ai studio"},
    "google-vertex": {"google-vertex", "google vertex", "google"},
}


def norm_provider(name):
    if not isinstance(name, str):
        return None
    s = name.strip().lower()
    if "/" in s and " " not in s:
        s = s.split("/", 1)[0]
    return s


def on_pin(recorded, pin):
    if pin is None:
        return True
    r, p = norm_provider(recorded), norm_provider(pin)
    if r is None:
        return False
    return r in PROVIDER_ALIASES.get(p, {p})


def valid(m):
    """Every task evaluated, at least one contact, and every provider call served by the actor's pinned
    upstream (the per-actor generalization of sched.sh is_valid), names normalized as above."""
    s = load(m + "/summary.json") or {}
    u = s.get("usage") or {}
    if not (s.get("evaluationRows") == s.get("selectedTasks") and (u.get("contactCalls") or 0) > 0):
        return False
    for f in glob.glob(m + "/.sharedeval-file-workflow/records/record-*.json"):
        tel = (((load(f) or {}).get("payload") or {}).get("privateEvidence") or {}).get("providerTelemetry") or {}
        for actor, block in tel.items():
            pin = PINS.get(actor)
            for q in (block or {}).get("requests") or []:
                if not on_pin(q.get("provider"), pin):
                    return False
    return True


def tactics_by_task(m):
    """Per requester turn, the task it updated and the `tactic=` value then recorded, in sequence order."""
    out = {}
    recs = []
    for f in glob.glob(m + "/.sharedeval-file-workflow/records/record-*.json"):
        d = load(f)
        if d is None:
            continue
        recs.append(d)
    for d in sorted(recs, key=lambda d: d.get("sequence", 0)):
        p = d.get("payload") or {}
        ca = p.get("contactAuthority") or {}
        task = ca.get("taskId")
        if not task:
            continue
        # the MEMORY bytes the requester wrote this turn
        text = None
        for op in (((p.get("privateEvidence") or {}).get("sourceEvidence") or {}).get("requesterFileOperations") or []):
            if op.get("actorId") == "requester" and op.get("path") == "MEMORY.md" and op.get("newBytesBase64"):
                try:
                    text = base64.b64decode(op["newBytesBase64"]).decode("utf-8", "replace")
                except ValueError:
                    text = None
        tactic = "undeclared"
        if text:
            for line in text.splitlines():
                mo = ROW.match(line.strip())
                if mo and mo.group(1) == task:
                    t = TACTIC.search(mo.group(3))
                    tactic = t.group(1) if t else "undeclared"
                    break
        out.setdefault(task, []).append(tactic)
    return out


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
        parts = rid.split("-")
        arm, rep, g = parts[0], parts[-2], parts[-1]
        rec = {"lane": "adaptive", "list": name, "slot": rid, "arm": arm,
               "replicate": int(rep[1:]) if rep[1:].isdigit() else rep, "group": g,
               "pins": PINS, "attempts": {}}
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
            # Group writes by the task they name ([ "task", taskId, surface ]); others under "_other"
            wbt = {}
            for at, action, path in rec["writes"]:
                task = path[1] if isinstance(path, list) and len(path) >= 2 and path[0] == "task" else "_other"
                wbt.setdefault(task, []).append([at, action, path[2] if isinstance(path, list) and len(path) >= 3 else None])
            rec["writes_by_task"] = wbt
            rec["tactics"] = tactics_by_task(chosen)
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
