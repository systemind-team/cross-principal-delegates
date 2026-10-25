#!/usr/bin/env python3
"""Kernel check, option B: the replay report, from the frozen replay outputs.

Inputs (evidence/v3.14/kernel-check/replay/): lane-<lane>.jsonl written by replay_decisions.mjs v2 over every run
folder of each lane (replay_lanes.sh), plus evidence/v3.14/ladder-per-task/ladder.jsonl.xz (the run folder
analyze_s4.py chose for each ladder slot) and evidence/v3.14/kernel-check/samples.json (the 20 sampled groups).

The gate comes first: for each study, K2's replay must reproduce every recorded decision. A study that fails the
gate is reported with its K2 mismatches and gets no K1 comparison. Then, per study: folders, replay errors,
questions replayed, recorded allowed/denied with the denial reasons, runs whose usage reconstruction matched their
usage records, K2 = recorded, K1 = recorded, K1 = K2, and every disagreement with its actor, action, resource,
reason and run. The 80 sampled ladder sessions (DeepSeek, D0/D2, R1/R3, 20 groups; the chosen folder of each slot)
are reported as their own block.

Usage: replay_report.py [--json]
"""
import collections
import json
import lzma
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
R = ROOT / "evidence/v3.14/kernel-check/replay"
STUDIES = [  # lane, study label
    ("t3simple", "PAIR II ladder grid (E3, 8081e7e)"),
    ("pair2id2", "PAIR II header comparison (E3, 8081e7e)"),
    ("pair2told", "PAIR II header ladder (E3-header, 4565add)"),
    ("grid600", "PAIR II probing grid (E2)"),
    ("pack1", "PAIR II packing, 1 per session (E2)"),
    ("pack10", "PAIR II packing, 10 per session (E2)"),
]
KEYS = ("decisions", "recorded_allowed", "recorded_denied", "k2_equals_recorded", "k1_equals_recorded", "k1_equals_k2")


def lane_rel(run_path, lane):
    marker = f"/runs/{lane}/"
    return run_path.split(marker, 1)[1] if marker in run_path else run_path


def block(rows):
    b = collections.Counter()
    errors = collections.Counter()
    diffs, k2_mismatch = [], []
    for r in rows:
        b["folders"] += 1
        if "error" in r:
            errors[r["error"]] += 1
            continue
        b["runs_replayed"] += 1
        b["usage_calibrated_runs"] += bool(r["usage_calibrated"])
        b["runs_with_deferred_grants"] += bool(r.get("deferred_grants"))
        for k in KEYS:
            b[k] += r[k]
        for reason, n in r["denied_reasons"].items():
            b[f"denied:{reason}"] += n
        for d in r["differences"]:
            row = {"run": r["run"], "actor": d["actor"], "action": d["action"], "resource": d["resource"],
                   "recorded": d["recorded"], "k2": d["k2"], "k1": d["k1"]}
            if d["k2"] != d["recorded"]:
                k2_mismatch.append(row)
            if d["k1"] != d["k2"]:
                diffs.append(row)
    gate = b["k2_equals_recorded"] == b["decisions"] and not k2_mismatch
    out = {"totals": dict(b), "replay_errors": dict(errors), "gate_k2_reproduces_record": gate}
    if gate:
        out["k1_vs_k2_disagreements"] = diffs
    else:
        out["k2_mismatches"] = k2_mismatch
    return out


def main():
    lanes = {}
    for lane, _ in STUDIES:
        p = R / f"lane-{lane}.jsonl"
        lanes[lane] = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else None
    report = {"studies": {}}
    for lane, label in STUDIES:
        if lanes[lane] is None:
            report["studies"][label] = {"missing": f"lane-{lane}.jsonl"}
            continue
        for r in lanes[lane]:
            r["run"] = lane_rel(r["run"], lane)
        report["studies"][label] = {"lane": lane, **block(lanes[lane])}
    # the 80 sampled ladder sessions: the chosen folder of each sampled slot
    groups = set(json.loads((ROOT / "evidence/v3.14/kernel-check/samples.json").read_text())["pair2"]["groups"])
    chosen = []
    with lzma.open(ROOT / "evidence/v3.14/ladder-per-task/ladder.jsonl.xz", "rt") as f:
        for line in f:
            s = json.loads(line)
            if "run" in s and s["arm"] == "DS" and s["rung"] in ("D0", "D2") and s["requester"] in ("R1", "R3") \
                    and s["group"] in groups:
                chosen.append(s["run"])
    by_run = {r["run"]: r for r in lanes["t3simple"] or []}
    subset = [by_run[c] for c in chosen if c in by_run]
    report["sampled_80"] = {"slots": len(chosen), "found": len(subset), **block(subset)}
    all_rows = [r for lane, _ in STUDIES if lanes[lane] for r in lanes[lane]]
    report["all_studies"] = block(all_rows)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=1, sort_keys=True))
        return
    for label, s in list(report["studies"].items()) + [("sampled 80 ladder sessions", report["sampled_80"]),
                                                       ("all studies", report["all_studies"])]:
        if "missing" in s:
            print(f"{label}: missing {s['missing']}")
            continue
        t = s["totals"]
        print(f"{label}: folders {t.get('folders', 0)}, replayed {t.get('runs_replayed', 0)}, replay errors "
              f"{sum(s['replay_errors'].values())} {dict(s['replay_errors']) or ''}")
        print(f"  questions {t.get('decisions', 0)} (recorded allowed {t.get('recorded_allowed', 0)}, denied "
              f"{t.get('recorded_denied', 0)}: " + ", ".join(f"{k[7:]} {v}" for k, v in sorted(t.items())
                                                              if k.startswith('denied:')) + ")")
        print(f"  usage reconstruction matches usage records in {t.get('usage_calibrated_runs', 0)} runs; runs with "
              f"deferred grants {t.get('runs_with_deferred_grants', 0)}")
        print(f"  GATE K2 = recorded: {t.get('k2_equals_recorded', 0)} of {t.get('decisions', 0)} -> "
              f"{'PASS' if s['gate_k2_reproduces_record'] else 'FAIL'}")
        if s["gate_k2_reproduces_record"]:
            print(f"  K1 = recorded {t.get('k1_equals_recorded', 0)}, K1 = K2 {t.get('k1_equals_k2', 0)} of "
                  f"{t.get('decisions', 0)}; disagreements {len(s['k1_vs_k2_disagreements'])}")
            for d in s["k1_vs_k2_disagreements"]:
                print(f"    {d}")
        else:
            for d in s["k2_mismatches"][:20]:
                print(f"    K2 mismatch {d}")


if __name__ == "__main__":
    main()
