#!/usr/bin/env python3
"""Budget guard for the grok-4.6 plan run: every 5 minutes, price every task-run recorded so far (cost.py's
rule, Data Zone list price) and stop the run (kill the tmux session) if the spend reaches the cap, or if after
100 finished task-runs the mean cost per task-run exceeds 1.5x the trial mean.

  python3 guard.py <runs-dir> <tmux-session> [--cap 200] [--max-mean 0.071]

Prints one line per check; the last line is GUARD STOP ... or GUARD DONE (no lane left running).
"""
import argparse, glob, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cost import task_run

ap = argparse.ArgumentParser()
ap.add_argument("runs")
ap.add_argument("session")
ap.add_argument("--cap", type=float, default=200.0)
ap.add_argument("--max-mean", type=float, default=0.071)
ap.add_argument("--every", type=int, default=300)
args = ap.parse_args()

while True:
    total, done, done_cost = 0.0, 0, 0.0
    for d in glob.glob(os.path.join(args.runs, "*", "single", "*")):
        t = task_run(d)
        total += t["usd"]["data_zone"]
        if t["status"] not in (None, "incomplete"):
            done += 1
            done_cost += t["usd"]["data_zone"]
    mean = done_cost / done if done else 0.0
    alive = subprocess.run(["tmux", "has-session", "-t", args.session], capture_output=True).returncode == 0
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"{stamp} spend ${total:.2f} finished {done} mean ${mean:.4f}", flush=True)
    reason = None
    if total >= args.cap:
        reason = f"spend ${total:.2f} reached the ${args.cap:.0f} cap"
    elif done >= 100 and mean > args.max_mean:
        reason = f"mean ${mean:.4f} per task-run exceeds ${args.max_mean}"
    if reason:
        subprocess.run(["tmux", "kill-session", "-t", args.session])
        print(f"{stamp} GUARD STOP: {reason}", flush=True)
        break
    if not alive:
        print(f"{stamp} GUARD DONE: no lane running", flush=True)
        break
    time.sleep(args.every)
