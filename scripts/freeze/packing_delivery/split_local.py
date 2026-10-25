#!/usr/bin/env python3
"""Write the frozen packing/delivery evidence from the stream extract_vm.py produced. Deterministic.

    ssh <host> 'nice -n 19 python3 -' < scripts/freeze/packing_delivery/extract_vm.py > /tmp/pd.jsonl.gz
    python3 scripts/freeze/packing_delivery/split_local.py /tmp/pd.jsonl.gz evidence/v3.14/packing-delivery

Writes (all JSON is sorted-key, one record per line for .jsonl):
  sessions.jsonl(.gz)   one line per session (pack1 180, pack10 18, grid600 2,400) with the fields validity is
                        decided from and the derived flag `valid`
  packing_tasks.jsonl   one line per (session, task) for the three packing arms: arm "1" = pack1,
                        arm "3" = grid600 R1 (all 600 tasks; `in_task_set_60` marks the 60), arm "10" = pack10
  grid_tasks.jsonl      one line per (session, task) for the whole probing grid (2,400 sessions x 3 tasks)
  configs.jsonl         one line per config file: the named non-secret fields only
  model_blocks.json     per arm: distinct config values, run.json model blocks, served models, harness revision
  task_kinds.json       the 600 tasks' kinds from questions.json (category expected_m2; actions by category)
  task_set_60.json      the 60-task set (union of AB-D2S selectedTaskIds)
  grid_attic.jsonl      earlier grid600 attempts moved aside before a rerun (counts and mtimes only)
  provenance.json       VM checkout revision, questions.json sha256, hashes of the legacy VM scripts
  legacy/runs/...       verbatim copies of the analysis and scheduler scripts used at the time (not executed)
  SHA256SUMS            sha256 of every file above, as stored on disk
Any file over 5 MB is stored gzip-compressed (name + ".gz"); provenance.json records its uncompressed sha256.
"""
import collections
import gzip
import hashlib
import json
import os
import sys

src, dst = sys.argv[1], sys.argv[2]
opener = gzip.open if src.endswith(".gz") else open
with opener(src, "rt", encoding="utf-8") as fh:
    records = [json.loads(line) for line in fh if line.strip()]
by = collections.defaultdict(list)
for r in records:
    by[r.pop("type")].append(r)

os.makedirs(dst, exist_ok=True)
written = []


GZIP_OVER = 5_000_000   # bytes; larger files are stored gzip-compressed (mtime 0, fixed name: deterministic)
uncompressed_sha256 = {}


def dump(name, obj):
    if name.endswith(".jsonl"):
        body = "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
                       for row in obj)
    elif isinstance(obj, str):
        body = obj
    else:
        body = json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
    data = body.encode("utf-8")
    path = os.path.join(dst, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if len(data) > GZIP_OVER:
        uncompressed_sha256[name] = hashlib.sha256(data).hexdigest()
        name += ".gz"
        path += ".gz"
        with open(path, "wb") as raw, gzip.GzipFile(filename=os.path.basename(path)[:-3], mode="wb", fileobj=raw,
                                                    mtime=0, compresslevel=9) as gz:
            gz.write(data)
    else:
        with open(path, "wb") as fh:
            fh.write(data)
    written.append(name)


def valid(s):
    """The rule fix356.py, recompute.py and the schedulers used: every selected task has an evaluation row
    and the session contacted the responder at least once."""
    sm = s["summary"] or {}
    usage = sm.get("usage") or {}
    return sm.get("evaluationRows") is not None and sm.get("evaluationRows") == sm.get("selectedTasks") \
        and (usage.get("contactCalls") or 0) > 0


def arm_of(row):
    return {"pack1": "1", "pack10": "10"}.get(row["study"], "3" if row["requester"] == "R1" else None)


meta = by["meta"][0]
t60 = by["t60"][0]
tasks60 = set(t60["tasks"])

# sessions
sessions = []
for s in sorted(by["session"], key=lambda s: (s["study"], s["run_id"])):
    s = dict(s)
    s["valid"] = valid(s)
    logs = s.get("launch_logs") or []
    s["source_revision"] = logs[-1][2] if logs else None   # the last launch produced the surviving run
    sessions.append(s)
dump("sessions.jsonl", sessions)

# task rows
packing, grid = [], []
for r in sorted(by["row"], key=lambda r: (r["study"], r["run_id"], r["task"])):
    base = {k: r[k] for k in ("run_id", "rep", "group", "task", "kind", "scored", "status", "contactStatus",
                              "errorCode", "terminalTick", "result_rows")}
    if "pe" in r:
        base["pe"] = r["pe"]
    arm = arm_of(r)
    if arm:
        packing.append({**base, "arm": arm, "requester": r["requester"], "in_task_set_60": r["task"] in tasks60,
                        "ticks": r["tick_list"]})
    if r["study"] == "grid600":
        grid.append({**base, "requester": r["requester"]})
order = {"1": 0, "3": 1, "10": 2}
dump("packing_tasks.jsonl", sorted(packing, key=lambda r: (order[r["arm"]], r["run_id"], r["task"])))
dump("grid_tasks.jsonl", grid)

# configs
dump("configs.jsonl", sorted(by["config"], key=lambda c: (c["study"], c["run_id"])))

# model blocks per arm
cfg_by_run = {c["run_id"]: c for c in by["config"]}
arms = {"1": lambda s: s["study"] == "pack1", "3": lambda s: s["study"] == "grid600" and s["requester"] == "R1",
        "10": lambda s: s["study"] == "pack10", "grid600 (R0-R3)": lambda s: s["study"] == "grid600"}
blocks = {}
for arm, sel in arms.items():
    runs = [s for s in sessions if sel(s)]
    fields = collections.defaultdict(collections.Counter)
    for s in runs:
        for k, v in cfg_by_run[s["run_id"]].items():
            if k in ("benchmark.tasks.ids", "run_id", "study"):
                continue
            fields[k][json.dumps(v)] += 1
    rj = collections.defaultdict(collections.Counter)
    for s in runs:
        j = s["run_json"] or {}
        for k in ("requester_model", "responder_model", "kernelRevision", "responder_policy", "dataset", "goldSet",
                  "requester_policy_id"):
            rj[k][json.dumps(j.get(k), sort_keys=True)] += 1
    blocks[arm] = {
        "sessions": len(runs),
        "config_fields": {k: {v: n for v, n in sorted(c.items())} for k, c in sorted(fields.items())},
        "run_json": {k: {v: n for v, n in sorted(c.items())} for k, c in sorted(rj.items())},
        "sharedeval_source_revision_of_last_launch": dict(sorted(collections.Counter(
            str(s["source_revision"]) for s in runs).items())),
        "served_models": [x for x in by["served"] if x["arm"] == arm] if arm in ("1", "3", "10") else None,
    }
dump("model_blocks.json", blocks)

# task kinds and the 60-task set
dump("task_kinds.json", {
    "source": meta["questions_path"], "sha256": meta["questions_sha256"],
    "rule": "PAIR-Q<id>: 'qa_' + categories[question.category].expected_m2 (answer = shareable, refuse = protected); "
            "PAIR-A<id>: 'act_auth' if action.category starts with 'authorized' else 'act_unauth'",
    "tasks": {t["task"]: [t["kind"], t["category"]] for t in by["task_kind"]}})
dump("task_set_60.json", {**t60, "equals_grid600_SAMPLE60_all": t60["tasks"] == t60["grid600_SAMPLE60_all"]})
dump("grid_attic.jsonl", sorted(by["attic"], key=lambda a: a["name"]))

# provenance and the legacy scripts
for lg in by["legacy"]:
    dump(os.path.join("legacy", lg["path"]), lg["content"])
dump("provenance.json", {**meta, "uncompressed_sha256": uncompressed_sha256})

# checksums (written last, over everything above)
lines = []
for name in sorted(written):
    with open(os.path.join(dst, name), "rb") as fh:
        lines.append(f"{hashlib.sha256(fh.read()).hexdigest()}  {name}\n")
dump("SHA256SUMS", "".join(lines))
print(f"wrote {len(written)} files to {dst}", file=sys.stderr)
