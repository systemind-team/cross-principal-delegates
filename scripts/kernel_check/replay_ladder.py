#!/usr/bin/env python3
"""Kernel check, option B driver: replay every recorded kernel authorization decision of the PAIR II ladder
grid through K2 and K1 (scripts/kernel_check/replay_decisions.mjs), then summarize.

Runs on the experiment VM. The session list is the frozen ladder per-task file
(evidence/v3.14/ladder-per-task/ladder.jsonl.xz, copied next to this script): every slot's run folder as chosen
by analyze_s4.py's rule (first attempt if valid, else the -x2 retry if valid, else none), relative to
<vm>/runs/t3simple. Slots with no chosen run are listed as missing, never replayed.

  replay_ladder.py run <ladder.jsonl.xz> <samples.json> <out.jsonl>    replay every chosen run (all builds)
  replay_ladder.py summary <ladder.jsonl.xz> <samples.json> <out.jsonl> per-slot table and totals (JSON)

The pre-registered subset is the brief's: DeepSeek build, rungs D0 and D2, requesters R1 and R3, the 20 sampled
groups (80 slots). The other slots are reported as a separate, larger block.
"""
import collections
import json
import lzma
import os
import subprocess
import sys

T3S = "<vm>/runs/t3simple"
KC = "<vm>/kernel-check"
NODE = "<vm>/toolchain/node-v24.18.0-linux-x64/bin/node"


def slots(ladder_xz):
    out = []
    with lzma.open(ladder_xz, "rt") as f:
        for line in f:
            r = json.loads(line)
            if "run" not in r:
                continue  # the last line holds the policy texts
            out.append({k: r[k] for k in ("arm", "rung", "requester", "group", "run")})
    return out


def in_subset(s, groups):
    return s["arm"] == "DS" and s["rung"] in ("D0", "D2") and s["requester"] in ("R1", "R3") and s["group"] in groups


def run(ladder_xz, samples_path, out_path):
    groups = set(json.load(open(samples_path))["pair2"]["groups"])
    todo = [s for s in slots(ladder_xz) if s["run"]]
    dirs = [os.path.join(T3S, s["run"]) for s in todo]
    with open(out_path, "w") as out:
        for i in range(0, len(dirs), 50):
            batch = dirs[i:i + 50]
            p = subprocess.run([NODE, f"{KC}/scripts/replay_decisions.mjs", "--k2", f"{KC}/kernels/K2",
                                "--k1", f"{KC}/kernels/K1", *batch], capture_output=True, text=True)
            if p.returncode != 0:
                raise SystemExit(p.stderr)
            out.write(p.stdout)
    print(f"replayed {len(dirs)} runs; subset slots with a run: {sum(in_subset(s, groups) for s in todo)}")


def summary(ladder_xz, samples_path, out_path):
    groups = set(json.load(open(samples_path))["pair2"]["groups"])
    by_dir = {}
    for line in open(out_path):
        r = json.loads(line)
        by_dir[os.path.relpath(r["run"], T3S)] = r
    blocks = collections.defaultdict(collections.Counter)
    diffs, missing, errors = [], [], []
    for s in slots(ladder_xz):
        key = "subset (DS, D0/D2, R1/R3, 20 groups)" if in_subset(s, groups) else "rest of the ladder grid"
        b = blocks[key]
        b["slots"] += 1
        if not s["run"]:
            b["no_valid_run"] += 1
            missing.append(s)
            continue
        r = by_dir.get(s["run"])
        if r is None or "error" in r:
            b["replay_error"] += 1
            errors.append({**s, "error": None if r is None else r["error"]})
            continue
        b["runs"] += 1
        for k in ("decisions", "recorded_allowed", "recorded_denied", "k2_equals_recorded", "k1_equals_recorded",
                  "k1_equals_k2"):
            b[k] += r[k]
        b["usage_calibrated_runs"] += bool(r["usage_calibrated"])
        for reason, n in r["denied_reasons"].items():
            b[f"denied:{reason}"] += n
        for d in r["differences"]:
            diffs.append({**s, **d})
    res = {"blocks": {k: dict(v) for k, v in blocks.items()}, "differences": diffs,
           "slots_without_valid_run": missing, "replay_errors": errors}
    print(json.dumps(res, indent=1, sort_keys=True))


if __name__ == "__main__":
    mode, ladder_xz, samples_path, out_path = sys.argv[1:5]
    {"run": run, "summary": summary}[mode](ladder_xz, samples_path, out_path)
