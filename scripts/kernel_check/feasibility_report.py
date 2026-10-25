#!/usr/bin/env python3
"""Kernel check: every number of the feasibility memo, read from the frozen files.

Inputs (evidence/v3.14/kernel-check/feasibility/): kernels.jsonl (kernel_digests.sh), logs/test-sharedos-*.txt
and full-tests/*.txt (compat_tests.sh / feasibility_runs.sh), scripted_audit_counts.jsonl (audit_counts.py over
the scripted runs), logs/feas-*.txt (the scripted runner's own output), original_configs.json
(original_configs.py). Prints a plain-text report; writes nothing.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
F = ROOT / "evidence/v3.14/kernel-check/feasibility"
PINNED_K2_DIGEST = "4afb23d79851a83a48e25e968f04e45cefc81847b4a9963c62277b5c05862d5d"


def tap(path):
    text = path.read_text()
    get = lambda k: int(m.group(1)) if (m := re.search(rf"^ℹ {k} (\d+)", text, re.M)) else None
    fails = sorted(set(re.findall(r"^✖ (.+?) \(\d", text, re.M)))
    return {"tests": get("tests"), "pass": get("pass"), "fail": get("fail"), "todo": get("todo"),
            "failing": fails}


def main():
    print("== kernels (fresh builds; digest = SharedEval digestSharedOsRuntimeV1)")
    for line in (F / "kernels.jsonl").read_text().splitlines():
        k = json.loads(line)
        d = k["result"]["digest"]
        print(f"  {k['kernel']:4s} {k['commit']} tree {k['tree'][:12]} packages {k['versions']['core']} "
              f"clean={k['clean']} digest {d}" + ("  == pinned K2 digest" if d == PINNED_K2_DIGEST else ""))

    print("== SharedEval real-kernel tests (test:sharedos: loader + runtime conformance)")
    for p in sorted((F / "logs").glob("test-sharedos-*.txt")):
        t = tap(p)
        print(f"  {p.stem.removeprefix('test-sharedos-'):12s} tests {t['tests']} pass {t['pass']} fail {t['fail']}")
        for name in t["failing"]:
            if name != "failing tests:":
                print(f"      fail: {name}")
        reasons = sorted(set(re.findall(r"(SharedOS runtime module is missing \w+|SharedOS turn produced no "
                                        r"authorization audit evidence)", p.read_text())))
        for r in reasons:
            print(f"      cause: {r}")

    full = F / "full-tests"
    if full.exists():
        print("== SharedEval full suite (`npm test` file list)")
        for p in sorted(full.glob("*.txt")):
            t = tap(p)
            print(f"  {p.stem:22s} tests {t['tests']} pass {t['pass']} fail {t['fail']} todo {t['todo']}")
            for name in t["failing"]:
                if name != "failing tests:":
                    print(f"      fail: {name}")

    print("== scripted end-to-end runs (no model call)")
    for line in (F / "scripted_audit_counts.jsonl").read_text().splitlines():
        r = json.loads(line)
        log = (F / "logs" / f"{r['run']}.txt").read_text()
        cause = re.search(r"\[heartbeat ([a-z_]+)\] Error: (.+)", log)
        summ = re.search(r'"event":"scripted_summary","requests":(\d+),"contacts":(\d+)', log)
        statuses = {k: v for k, v in (r["summary"].get("statuses") or {}).items() if v}
        print(f"  {r['run']:14s} audit records {r['audit_records']:4d}  model requests {summ.group(1)} contacts "
              f"{summ.group(2)}  task statuses {statuses}  records with `id` {r['event_keys'].get('id', 0)}")
        if cause:
            print(f"      stopped: {cause.group(1)}: {cause.group(2)}")
        for k, v in r["by_type_outcome_reason"].items():
            print(f"      {v:4d} {k}")

    oc = json.loads((F / "original_configs.json").read_text())
    print("== originals")
    for cell, v in sorted(oc["pair1"].items()):
        print(f"  PAIR I {cell}: {v['imageRef']} {v['startedAt']}..{v['finishedAt']} exit {v['cliExitCode']}")
    p2 = oc["pair2"]
    print(f"  PAIR II ladder configs read: {len(p2['ladder_configs'])}; model blocks: "
          f"{[m.get('provider') + ':' + (m.get('deployment') or m.get('model')) for m in p2['ladder_distinct']['model']]}")
    print(f"  PAIR II same-route D2 control configs read: {len(p2['told_ctrl_configs'])}; model blocks: "
          f"{[m.get('provider') + ':' + m.get('model') + ' ' + json.dumps(m.get('providerRouting')) for m in p2['told_distinct']['model']]}")


def budget():
    c = json.loads((F / "cost_reference.json").read_text())
    rates = [c["header_ladder_2026_10_03"]["usd_per_session"], c["identity_comparison_2026_10_02"]["usd_per_session"]]
    lo, hi = min(rates), max(rates)
    print("== budget arithmetic (PAIR II on the Relace route; stop line $9)")
    print(f"  per session ${lo} .. ${hi}; one 80-session arm ${80 * lo:.2f} .. ${80 * hi:.2f}; "
          f"three arms ${3 * 80 * hi:.2f} at the higher rate")
    print(f"  three PAIR I arms fit under $9 if one 240-task arm costs <= ${(9 - 3 * 80 * hi) / 3:.2f}")
    print(f"  kernel-check key so far: {c['kernel_check_key_so_far']}")


if __name__ == "__main__":
    main()
    budget()
