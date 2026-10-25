#!/usr/bin/env python3
"""Extract the packing and delivery records behind Tables 5(c), 28 and 32. Read-only.

Runs ON THE VM, fed over stdin so nothing is written there:

    ssh <host> 'nice -n 19 python3 -' < scripts/freeze/packing_delivery/extract_vm.py > raw.jsonl.gz

and writes one gzip-compressed JSON-lines stream to stdout; split_local.py turns it into the frozen
files under evidence/v3.14/packing-delivery/.

Sources (all under <vm>
  runs/pack1/cfg/PK1-r{1,2,3}-g###.json      one task per session   (+ cfg/runs/<RID>/multi/)
  runs/pack10/cfg/PK10-r{1,2,3}-g###.json    ten tasks per session
  runs/grid600/cfg/G6-R{0..3}-r{1,2,3}-g###.json  three per session (its R1 runs are the 3-per-session arm)
  runs/ablation/cfg/runs/AB-D2S-*/multi/run.json  selectedTaskIds -> the 60-task set
  repos/SharedEval-a1/dataset/pact-pair/tasks/questions.json  task kinds (category expected_m2)

What it reads and what it never reads:
  * configs: ONLY the named fields in CONFIG_FIELDS (never model.endpoint, model.apiKeyEnv or anything else);
  * run.json, summary.json, results.jsonl, ticks.jsonl, final.json, the failure-directory listing;
  * each run's launch logs (logs/<RID>.*.log): only the "sourceRevision" the CLI prints, plus name and mtime;
  * grid600/attic/ (earlier attempts that were moved aside before a rerun): only summary.json counts and mtimes;
  * file-workflow records: ONLY the model names in providerTelemetry (requested/resolved/served), for the
    three packing arms;
  * the legacy analysis scripts listed in LEGACY, copied verbatim after a check that they hold no credential.
  No env file, key file or gateway folder is opened. No text of any request or reply is emitted.
"""
import collections
import datetime
import glob
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = "<vm>"
R = f"{ROOT}/runs"
SE = f"{ROOT}/repos/SharedEval-a1"
QUESTIONS = f"{SE}/dataset/pact-pair/tasks/questions.json"

STUDIES = (  # study, config glob, run-id pattern -> (requester or None, rep, group)
    ("pack1", f"{R}/pack1/cfg/PK1-*.json", re.compile(r"^PK1-(r\d)-(g\d+)$")),
    ("pack10", f"{R}/pack10/cfg/PK10-*.json", re.compile(r"^PK10-(r\d)-(g\d+)$")),
    ("grid600", f"{R}/grid600/cfg/G6-*.json", re.compile(r"^G6-(R\d)-(r\d)-(g\d+)$")),
)
CONFIG_FIELDS = (
    ("model", "provider"), ("model", "deployment"), ("model", "temperature"), ("model", "maxOutputTokens"),
    ("workflow", "mode"), ("workflow", "protocol"), ("workflow", "maxTicks"), ("workflow", "stopWhen"),
    ("workflow", "pairProfile"), ("workflow", "elideUnchangedReads"),
    ("workflow", "multiTurn", "phase2StartTick"), ("workflow", "multiTurn", "finalizeTick"),
    ("workflow", "world", "protocol"), ("workflow", "world", "maxContextBytes"),
    ("benchmark", "dataset"), ("benchmark", "policy"), ("benchmark", "requester"),
    ("benchmark", "gradingMode"), ("benchmark", "tasks", "kind"), ("benchmark", "tasks", "ids"),
    ("budget", "maxRuntimeMs"),
)
PE_FIELDS = ("kind", "actualDecision", "correct", "scorable", "factMatch", "benchmarkNoLeak", "benchmarkLeaked",
             "leaked", "noLeak", "stateChanged", "stateCorrect", "noUnexpectedMutations")
LEGACY = ("runs/fix356.py", "runs/recompute.py", "runs/grid600/agg_rel.py", "runs/pack1/sched.sh",
          "runs/pack10/sched.sh", "runs/grid600/sched2.sh")
PROVENANCE = LEGACY + ("runs/grid600/probing_outcomes.py", "runs/grid600/self_intro.py", "runs/grid600/MANIFEST.json")
SECRETISH = re.compile(r"(api[_-]?key\s*[=:]|bearer\s+[a-z0-9]|sk-[a-z0-9]{8}|secret\s*[=:]|password\s*[=:])", re.I)

out = gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb", mtime=0)


def emit(obj):
    out.write((json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode())


def get(o, path):
    for p in path:
        if not isinstance(o, dict) or p not in o:
            return None
        o = o[p]
    return o


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def jsonl(path):
    try:
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        return None


def mtime(path):
    try:
        t = os.path.getmtime(path)
    except OSError:
        return None
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


REV = re.compile(r'"sourceRevision":\s*"([0-9a-f]{40})"')


def launch_logs(study, rid):
    """[[log name, mtime, sourceRevision or None], ...] sorted by mtime; the last one launched the surviving run."""
    logs = []
    for lg in glob.glob(f"{R}/{study}/logs/{rid}.*.log"):
        with open(lg, errors="replace") as fh:
            m = REV.search(fh.read(4096))
        logs.append([os.path.basename(lg), mtime(lg), m.group(1) if m else None])
    return sorted(logs, key=lambda x: (x[1], x[0]))


# ---- provenance -------------------------------------------------------------------------------------
rev = subprocess.run(["git", "-C", SE, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "--no-optional-locks", "-C", SE, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True).stdout.strip()   # no index refresh: nothing is written
emit({"type": "meta", "sharedeval_checkout": SE, "sharedeval_head": rev, "sharedeval_tracked_dirty": bool(dirty),
      "questions_path": QUESTIONS, "questions_sha256": sha256(QUESTIONS),
      "provenance": {p: {"sha256": sha256(f"{ROOT}/{p}"), "bytes": os.path.getsize(f"{ROOT}/{p}"),
                         "mtime": mtime(f"{ROOT}/{p}")} for p in PROVENANCE if os.path.exists(f"{ROOT}/{p}")}})
for p in LEGACY:
    text = open(f"{ROOT}/{p}").read()
    if SECRETISH.search(text):
        raise SystemExit(f"refusing to copy {p}: credential-like text")
    emit({"type": "legacy", "path": p, "content": text})

# ---- task kinds ---------------------------------------------------------------------------------------
data = load(QUESTIONS)
category = {c["id"]: c for c in data["categories"]}
KIND = {}
for q in data["questions"]:
    KIND[f"PAIR-Q{q['id']}"] = ("qa_" + category[q["category"]]["expected_m2"], q["category"])
for a in data["actions"]:
    KIND[f"PAIR-A{a['id']}"] = ("act_" + ("auth" if a["category"].startswith("authorized") else "unauth"),
                                a["category"])
for t in sorted(KIND, key=lambda x: (x[5], int(x[6:]))):
    emit({"type": "task_kind", "task": t, "kind": KIND[t][0], "category": KIND[t][1]})

# ---- the 60-task set -----------------------------------------------------------------------------------
ab = sorted(glob.glob(f"{R}/ablation/cfg/runs/AB-D2S-*/multi/run.json"))
sets = collections.Counter()
t60 = set()
unreadable = 0
for f in ab:
    rj = load(f)
    if not rj or "selectedTaskIds" not in rj:
        unreadable += 1
        continue
    t60 |= set(rj["selectedTaskIds"])
    sets[tuple(sorted(rj["selectedTaskIds"]))] += 1
sample60 = load(f"{R}/grid600/SAMPLE60.json") or {}
emit({"type": "t60", "source_glob": f"{R}/ablation/cfg/runs/AB-D2S-*/multi/run.json", "run_json_files": len(ab),
      "unreadable": unreadable, "distinct_groups": len(sets), "tasks": sorted(t60),
      "grid600_SAMPLE60_all": sorted(sample60.get("all") or [])})

# ---- sessions, task rows, configs ------------------------------------------------------------------------
served = collections.Counter()
for study, pattern, rx in STUDIES:
    for cpath in sorted(glob.glob(pattern)):
        rid = os.path.basename(cpath)[:-5]
        m = rx.match(rid)
        if not m:
            continue
        parts = m.groups()
        cfg = load(cpath)
        cfields = {".".join(p): get(cfg, p) for p in CONFIG_FIELDS}
        requester = cfields["benchmark.requester"]
        rep, group = parts[-2], parts[-1]
        if study == "grid600" and parts[0] != requester:
            raise SystemExit(f"{rid}: run id says {parts[0]}, config says {requester}")
        emit({"type": "config", "study": study, "run_id": rid, **cfields})

        mdir = f"{R}/{study}/cfg/runs/{rid}/multi"
        rj = load(f"{mdir}/run.json")
        sm = load(f"{mdir}/summary.json")
        fj = load(f"{mdir}/.sharedeval-file-workflow/final.json")
        fdir = f"{mdir}/.sharedeval-file-failures"
        failures = sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []
        results = jsonl(f"{mdir}/results.jsonl")
        ticks = jsonl(f"{mdir}/ticks.jsonl")
        res_by_task = collections.defaultdict(list)
        for r in results or []:
            res_by_task[r.get("taskId")].append(r)
        ticks_by_task = collections.defaultdict(list)
        tick_status = collections.Counter()
        for t in ticks or []:
            tick_status[f"{t.get('status')}/{t.get('contactStatus')}"] += 1
            ticks_by_task[t.get("selectedTaskId")].append(t)
        cfg_ids = cfields["benchmark.tasks.ids"] or []
        emit({
            "type": "session", "study": study, "run_id": rid, "requester": requester, "rep": rep, "group": group,
            "config_task_ids": cfg_ids,
            "run_dir": os.path.isdir(mdir),
            "run_json": None if rj is None else {
                "selectedTaskIds": rj.get("selectedTaskIds"), "status": rj.get("status"),
                "stopReason": rj.get("stopReason"), "evaluationRows": rj.get("evaluationRows"),
                "resultRows": rj.get("resultRows"), "recordCount": rj.get("recordCount"),
                "requester_model": get(rj, ("actors", "requester", "model")),
                "responder_model": get(rj, ("actors", "responder", "model")),
                "kernelRevision": get(rj, ("backend", "kernelRevision")),
                "responder_policy": get(rj, ("policies", "responder")),
                "requester_policy_id": get(rj, ("policies", "requester", "id")),
                "dataset": get(rj, ("dataset",)), "goldSet": get(rj, ("goldSet",))},
            "summary": None if sm is None else {
                "selectedTasks": sm.get("selectedTasks"), "evaluationRows": sm.get("evaluationRows"),
                "resultRows": sm.get("resultRows"), "statuses": sm.get("statuses"), "usage": sm.get("usage"),
                "metrics": [[x.get("metric"), x.get("numerator"), x.get("denominator")]
                            for x in sm.get("metrics") or []]},
            "final_json": None if fj is None else {"stopReason": fj.get("stopReason"),
                                                   "recordCount": fj.get("recordCount")},
            "failures": len(failures),
            "results_rows": None if results is None else len(results),
            "results_task_ids_not_selected": sorted(set(res_by_task) - set(cfg_ids)),
            "ticks": None if ticks is None else len(ticks),
            "max_tick": max((t.get("tick") or 0 for t in ticks or []), default=None),
            "tick_status": dict(tick_status),
            "idle_ticks": len(ticks_by_task.get(None, [])),
            "mtime": {"run.json": mtime(f"{mdir}/run.json"), "summary.json": mtime(f"{mdir}/summary.json"),
                      "ticks.jsonl": mtime(f"{mdir}/ticks.jsonl")},
            "launch_logs": launch_logs(study, rid),
        })
        packing_arm = study in ("pack1", "pack10") or (study == "grid600" and requester == "R1")
        for tid in cfg_ids:
            rows = res_by_task.get(tid, [])
            r = rows[0] if rows else {}
            pe = r.get("publicEvaluation")
            row = {"type": "row", "study": study, "run_id": rid, "requester": requester, "rep": rep,
                   "group": group, "task": tid, "kind": KIND[tid][0], "result_rows": len(rows),
                   "status": r.get("status"), "contactStatus": r.get("contactStatus"),
                   "errorCode": r.get("errorCode"), "terminalTick": r.get("terminalTick"),
                   "scored": pe is not None, "n_ticks": len(ticks_by_task.get(tid, []))}
            if pe is not None:
                if pe.get("taskId") != tid:
                    raise SystemExit(f"{rid}: publicEvaluation.taskId {pe.get('taskId')} != {tid}")
                row["pe"] = {k: pe[k] for k in PE_FIELDS if k in pe}
            if packing_arm:
                row["tick_list"] = [[t.get("tick"), t.get("phase"), int(bool(t.get("finalization"))),
                                     t.get("contactStatus")] for t in ticks_by_task.get(tid, [])]
            emit(row)
        if packing_arm:  # model names only, from the provider telemetry of every record
            arm = {"pack1": "1", "pack10": "10"}.get(study, "3")
            for rec in sorted(glob.glob(f"{mdir}/.sharedeval-file-workflow/records/record-*.json")):
                tel = get(load(rec) or {}, ("payload", "privateEvidence", "providerTelemetry")) or {}
                for side in ("requester", "responder"):
                    for q in get(tel, (side, "requests")) or []:
                        served[(arm, side, q.get("requestedModel"), q.get("resolvedModel"), q.get("servedModel"),
                                q.get("servedModelVerified"), q.get("outcome"))] += 1
    print(f"{study}: done", file=sys.stderr)

# ---- earlier grid600 attempts moved aside before a rerun (dir name: <RID>.p<pass>.<HHMMSS>) ----------------------
for d in sorted(glob.glob(f"{R}/grid600/attic/G6-*")):
    sm = load(f"{d}/multi/summary.json")
    emit({"type": "attic", "name": os.path.basename(d), "run_id": os.path.basename(d).split(".")[0],
          "summary": None if sm is None else {"selectedTasks": sm.get("selectedTasks"),
                                              "evaluationRows": sm.get("evaluationRows"),
                                              "contactCalls": (sm.get("usage") or {}).get("contactCalls")},
          "summary_mtime": mtime(f"{d}/multi/summary.json"), "dir_mtime": mtime(d)})

for (arm, side, req, res, srv, ver, outc), n in sorted(served.items(), key=lambda kv: json.dumps(kv[0])):
    emit({"type": "served", "arm": arm, "side": side, "requestedModel": req, "resolvedModel": res,
          "servedModel": srv, "servedModelVerified": ver, "outcome": outc, "requests": n})
out.close()
