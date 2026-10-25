#!/usr/bin/env python3
"""Price grok-4.6 task-runs from the runner's per-request usage records, and project the run plan's cost.

  python3 cost.py <run-dir>... [--out FILE]

Each <run-dir> is a runner output (runs/<runId>/ with single/<NNNN>-<task>/). Azure returns no cost, so every
model request recorded in a task's .sharedeval-file-workflow/records/ is priced at Azure's list price for
grok-4.6 (retail price API, effective 2026-09-01, per million tokens). Billed output is total minus prompt
tokens: grok reports its reasoning tokens outside completion_tokens but inside total_tokens.
The projection multiplies the mean cost of a QA and of an action task-run by the plan's counts; the budget
cap is the projection at the upper 95% bound of each mean (t interval), plus 25% headroom, rounded up to $50.
"""
import argparse, collections, glob, json, math, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DESIGN_DIR

PRICES = {  # USD per 1M tokens: input, cached input, output
    "global": (2.00, 0.50, 6.00),
    "data_zone": (2.20, 0.55, 6.60),
}
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 15: 2.13, 20: 2.09, 30: 2.04}


def t95(df):
    return T95[max(k for k in T95 if k <= df)] if df < 60 else 1.96


def requests(obj, acc):
    if isinstance(obj, dict):
        if "outcome" in obj and "usage" in obj:
            acc.append(obj)
        for v in obj.values():
            requests(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            requests(v, acc)


def task_run(task_dir):
    reqs = []
    for f in sorted(glob.glob(os.path.join(task_dir, ".sharedeval-file-workflow", "records", "*.json"))):
        requests(json.load(open(f)), reqs)
    tok = {"prompt": 0, "cached": 0, "output": 0, "reasoning": 0}
    served = set()
    for q in reqs:
        u = q.get("usage") or {}
        p = u.get("promptTokens") or 0
        tok["prompt"] += p
        tok["cached"] += u.get("cachedTokens") or 0
        tok["reasoning"] += u.get("reasoningTokens") or 0
        total = u.get("totalTokens")
        tok["output"] += (total - p) if total is not None else (u.get("completionTokens") or 0) + (u.get("reasoningTokens") or 0)
        if q.get("servedModel"):
            served.add(q["servedModel"])
    summary_path = os.path.join(task_dir, "summary.json")
    status = "incomplete"  # an interrupted task still spent its recorded requests
    if os.path.exists(summary_path):
        status = next((k for k, v in json.load(open(summary_path))["statuses"].items() if v), None)
    cost = {zone: ((tok["prompt"] - tok["cached"]) * pin + tok["cached"] * pcache + tok["output"] * pout) / 1e6
            for zone, (pin, pcache, pout) in PRICES.items()}
    task = os.path.basename(task_dir).split("-", 1)[1]
    return {"task": task, "kind": "qa" if task.startswith("PAIR-Q") else "action", "status": status,
            "requests": len(reqs), "tokens": tok, "served": sorted(served), "usd": cost}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out")
    args = ap.parse_args()
    rows = []
    for run in args.runs:
        for d in sorted(glob.glob(os.path.join(run, "single", "*"))):
            rows.append({"run": os.path.basename(run.rstrip("/")), **task_run(d)})
    plan = json.load(open(os.path.join(DESIGN_DIR, "run_plan.json")))
    report = {"prices_per_million": PRICES, "taskRuns": rows, "byKind": {}, "projection": {}}
    for kind in ("qa", "action"):
        xs = [r["usd"]["data_zone"] for r in rows if r["kind"] == kind]
        if xs:
            m = statistics.mean(xs)
            sd = statistics.stdev(xs) if len(xs) > 1 else m
            report["byKind"][kind] = {"n": len(xs), "mean": m, "sd": sd, "upper95": m + t95(len(xs) - 1) * sd / math.sqrt(len(xs))}
    allx = [r["usd"]["data_zone"] for r in rows]
    pooled = statistics.mean(allx)
    pooled_up = pooled + t95(len(allx) - 1) * (statistics.stdev(allx) if len(allx) > 1 else pooled) / math.sqrt(len(allx))
    point = upper = 0.0
    for kind, count in plan["taskRunsByKind"].items():
        k = report["byKind"].get(kind, {"mean": pooled, "upper95": pooled_up})
        point += k["mean"] * count
        upper += k["upper95"] * count
    report["projection"] = {"taskRuns": plan["taskRuns"], "point_usd": point, "upper95_usd": upper,
                            "budget_cap_usd": 50 * math.ceil(upper * 1.25 / 50),
                            "global_point_usd": point * PRICES["global"][2] / PRICES["data_zone"][2]}
    tot = {k: sum(r["tokens"][k] for r in rows) for k in ("prompt", "cached", "output", "reasoning")}
    print(f"{len(rows)} task-runs, {sum(r['requests'] for r in rows)} requests, served {sorted({s for r in rows for s in r['served']})}")
    print(f"tokens: {tot}; statuses: {dict(collections.Counter(str(r['status']) for r in rows))}")
    for kind, k in report["byKind"].items():
        print(f"  {kind:6s} n {k['n']:2d}  mean ${k['mean']:.4f}  sd ${k['sd']:.4f}  upper95 ${k['upper95']:.4f} (data zone)")
    p = report["projection"]
    print(f"plan {p['taskRuns']} task-runs: point ${p['point_usd']:.0f} (global ${p['global_point_usd']:.0f}), "
          f"upper95 ${p['upper95_usd']:.0f}, cap ${p['budget_cap_usd']}")
    if args.out:
        json.dump(report, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
