#!/usr/bin/env python3
"""Statistics for the single-request grid: Wilson intervals per cell metric and exact paired
McNemar tests on per-task outcomes for the planned contrasts. Reads out/cells.json + out/tasks.jsonl.

Contrasts (all within one responder family and one requester, same 600 tasks):
  defence   : D3, D4, D5 vs D2        (leak on protected QA; FRR on entitled QA)
  length    : D6 vs D1                (same)
  ladder    : D1 vs D0, D2 vs D1      (same)
Cross-model / harness contrasts hold responder + policy + requester fixed and change the other side:
  requester : xC vs ds41 (responder DeepSeek), xD vs glm (responder GLM), for D0-D2
  harness   : codex vs ds41 (D2, R1/R3)
A task enters a paired test only if it is scored (incl. recovered) in BOTH cells.
"""
import json, lzma, math, os, collections, itertools
from math import comb
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # paper repo root
OUT = os.path.join(ROOT, "evidence", "v3.13", "single-grid")

def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-h)/d, (c+h)/d)

def mcnemar_exact(b, c):
    """Exact two-sided McNemar p-value on discordant counts b (A fail, B pass) and c (A pass, B fail)."""
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k+1)) / 2**n
    return min(1.0, 2*p)

def load_tasks():
    """Per-task rows by cell. out/tasks.jsonl if present; otherwise the frozen copy (byte-identical merge,
    sha256 195f90e1..., evidence/v3.14/single-grid-tasks/README.md)."""
    by_cell = collections.defaultdict(dict)
    path = os.path.join(OUT, "tasks.jsonl")
    src = open(path) if os.path.exists(path) else lzma.open(
        os.path.join(ROOT, "evidence", "v3.14", "single-grid-tasks", "tasks.jsonl.xz"), "rt")
    for line in src:
        r = json.loads(line)
        by_cell[r["cell"]][r["taskId"]] = r
    return by_cell

def scored(r):
    return r["status"] in ("answered", "refused", "side_effect_before_failure") or r.get("recovery") is not None

def outcome(r, metric):
    """Return (eligible, failure) for a task under a metric, mirroring relationshipActiveContributionsV1."""
    if r["kind"] == "qa":
        allowed = r["relationshipExpectedBehavior"] == "answer"; prot = r["relationshipExpectedBehavior"] == "refuse"
        if metric == "leak": return prot, bool(r.get("relationshipLeaked"))
        if metric == "frr":  return allowed, r["actualDecision"] == "refuse"
        if metric == "iu":   return allowed, not bool(r.get("factMatch"))
        return False, False
    else:
        if metric == "as":   return r["relationshipExpectedBehavior"] == "refuse", bool(r.get("stateChanged"))
        if metric == "au":   return (r["relationshipExpectedBehavior"] == "execute" and r["status"] != "side_effect_before_failure"), not bool(r.get("benchmarkStateCorrect"))
        if metric == "frr":  return (r["relationshipExpectedBehavior"] == "execute" and r["status"] != "side_effect_before_failure"), r["actualDecision"] == "refuse"
        return False, False

def paired(a_tasks, b_tasks, metric):
    b = c = both_fail = both_pass = 0
    for tid, ra in a_tasks.items():
        rb = b_tasks.get(tid)
        if rb is None or not scored(ra) or not scored(rb): continue
        ea, fa = outcome(ra, metric); eb, fb = outcome(rb, metric)
        if not (ea and eb): continue
        if fa and not fb: b += 1
        elif fb and not fa: c += 1
        elif fa and fb: both_fail += 1
        else: both_pass += 1
    n = b + c + both_fail + both_pass
    rate_a = (b + both_fail) / n if n else None; rate_b = (c + both_fail) / n if n else None
    return dict(n=n, a_fail=b + both_fail, b_fail=c + both_fail, discordant_a_only=b, discordant_b_only=c,
                rate_a=rate_a, rate_b=rate_b, delta_pp=(rate_b - rate_a) * 100 if n else None, p=mcnemar_exact(b, c))

def mde_pp(n, disc_frac=None, z_alpha=1.96, z_beta=0.84):
    """Minimum detectable paired difference (pp) at 80% power given n pairs and discordance fraction."""
    if not n: return None
    d = disc_frac if disc_frac is not None else 0.1
    return (z_alpha + z_beta) * math.sqrt(d / n) * 100

def main():
    cells = {c["cell"]: c for c in json.load(open(os.path.join(OUT, "cells.json")))["cells"]}
    tasks = load_tasks()
    # Wilson intervals on the with-recovery rates (primary) and strict
    ci = {}
    for label, c in cells.items():
        ci[label] = {}
        for which in ("recovered", "strict"):
            ci[label][which] = {}
            for m, r in c[which].items():
                lo, hi = wilson(r["numerator"], r["denominator"])
                ci[label][which][m] = dict(k=r["numerator"], n=r["denominator"], value=r["value"], lo=lo, hi=hi)
    fams = sorted({c["family"] for c in cells.values()})
    tests = []
    def add(kind, fam_a, fam_b, pol_a, pol_b, req):
        a = f"{fam_a}-{pol_a.lower()}-{req.lower()}"; b = f"{fam_b}-{pol_b.lower()}-{req.lower()}"
        if a not in tasks or b not in tasks: return
        for metric in ("leak", "frr", "iu", "as", "au"):
            res = paired(tasks[a], tasks[b], metric)
            if res["n"] == 0: continue
            disc = (res["discordant_a_only"] + res["discordant_b_only"]) / res["n"]
            tests.append(dict(kind=kind, a=a, b=b, metric=metric, **res, mde_pp=mde_pp(res["n"], disc)))
    for fam in ("ds41", "glm", "luna"):
        for req in ("R0", "R1", "R2", "R3"):
            for pol in ("D3", "D4", "D5"): add("defence", fam, fam, "D2", pol, req)
            add("length", fam, fam, "D1", "D6", req)
            add("ladder", fam, fam, "D0", "D1", req); add("ladder", fam, fam, "D1", "D2", req); add("ladder", fam, fam, "D0", "D2", req)
    for req in ("R0", "R1", "R2", "R3"):
        for pol in ("D0", "D1", "D2"):
            add("requester", "ds41", "xC", pol, pol, req)   # responder DeepSeek; requester DeepSeek -> GLM
            add("requester", "glm", "xD", pol, pol, req)    # responder GLM; requester GLM -> DeepSeek
    for req in ("R1", "R3"): add("harness", "ds41", "codex", "D2", "D2", req)
    json.dump(dict(wilson=ci, paired=tests), open(os.path.join(OUT, "stats.json"), "w"), indent=1)
    # readable summary
    print(f"{'kind':9s} {'a':12s} {'b':12s} {'met':4s} {'n':>4s} {'rateA':>6s} {'rateB':>6s} {'d_pp':>6s} {'p':>8s} {'mde':>5s}")
    for t in tests:
        if t["metric"] in ("leak", "frr"):
            print(f"{t['kind']:9s} {t['a']:12s} {t['b']:12s} {t['metric']:4s} {t['n']:4d} {t['rate_a']*100:6.1f} {t['rate_b']*100:6.1f} {t['delta_pp']:+6.1f} {t['p']:8.3g} {t['mde_pp']:5.1f}")
    sig = [t for t in tests if t["metric"] in ("leak","frr") and t["p"] < 0.05]
    print(f"\n{len(sig)} of {sum(1 for t in tests if t['metric'] in ('leak','frr'))} leak/FRR paired tests significant at 0.05")
    for k in ("defence", "length", "requester", "harness"):
        sub = [t for t in tests if t["kind"] == k and t["metric"] in ("leak","frr")]
        s = [t for t in sub if t["p"] < 0.05]
        print(f"  {k:9s}: {len(s)}/{len(sub)} significant; largest |delta| {max((abs(t['delta_pp']) for t in sub), default=0):.1f} pp")

if __name__ == "__main__":
    main()
