#!/usr/bin/env python3
"""P1-6 design v2: power of the primary tests for the impersonation arms. Design numbers only.

Primary outcomes (item 2): total leak (TL) on O1, the 51 questions the colleague may receive (52 minus
the flagged Q324), and execution of O2, the 22 actions the colleague may cause; pairs are (impersonation,
control) on the same task and replicate, 2 replicates, so 102 and 44 pairs. Control rates are the 10-02 header
comparison's stranger on the same items (the frozen classes and records, read below): with the header and
without it. A rate of 0 is replaced by 1% (an exact zero has no power curve).

Two calculations.
1. The exact two-sided McNemar test alone, analytic (as power.py v1): pair outcomes bivariate Bernoulli with
   marginals p0 and p1 and correlation rho, rho = 0 (independent arms, the conservative end) or the replicate
   correlation of the probing grid (numbers.json: 0.54 for questions, 0.69 for actions; the optimistic end).
2. The joint rule: McNemar over pairs and the exact sign-flip test over groups must both reject.
   Simulated: a latent probit model per item, y = 1[mu_arm + u_item + e > 0], u ~ N(0, s^2) shared by both arms
   and both replicates, e ~ N(0, 1) independent; s is set so that two replicates of the control correlate at
   the probing grid's value (or s = 0, independent). Groups as in the ladder's MANIFEST.
Each is evaluated at alpha 0.05 (the last Holm step) and 0.00625 (the first of eight). Output: the smallest
impersonation rate with 80% power, as an increase in points over the control rate. For scale the script also
prints every 10-02 arm's rates on R0's labels (O1, O2 and F1) and the relationship claims in the 10-02
requesters' messages (numbers.py's frozen pattern), by first request and follow-up request.

Usage: python3 power.py [--classes <pair2_classes_identity.jsonl.xz>] [--identity <identity.jsonl.xz>] > power.json
"""
import argparse
import collections
import hashlib
import json
import lzma
import math
import pathlib
import re

import numpy as np
from scipy.stats import multivariate_normal, norm

ROOT = pathlib.Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser()
ap.add_argument("--classes", default=str(ROOT / "evidence/v3.14/total-disclosure/pair2_classes_identity.jsonl.xz"))
ap.add_argument("--identity", default=str(ROOT / "evidence/v3.14/identity-per-task/identity.jsonl.xz"))
ap.add_argument("--sims", type=int, default=2000)
args = ap.parse_args()
SHA = {"classes": "441c128f9f44a1c7c297e8bb7f6d78f94f365c90f0c80a4d49e63c75e7e2b579",
       "identity": "08e7bd334fb084eb8bc6e40f0114eb83ad3b3de4faa25346a4bec4d2422a76a1"}
for k in SHA:
    got = hashlib.sha256(open(getattr(args, k), "rb").read()).hexdigest()
    assert got == SHA[k], f"{k}: {got}"

LAB = json.load(open(ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json"))
QL = {f"PAIR-Q{r['id']}": r for r in LAB["questions"]}
AL = {f"PAIR-A{r['id']}": r for r in LAB["actions"]}
GROUPS = json.load(open(ROOT / "evidence/v3.13/multi-table3/MANIFEST.json"))["groups"]
EXCL = set(json.load(open(ROOT / "evidence/v3.14/multi-spoof/design/prefix_overlap.json"))["excludedFromPrimary"])
O1 = [t for g in sorted(GROUPS) for t in GROUPS[g] if t in QL and QL[t]["R1"] == "L" and t not in EXCL]
O2 = [t for g in sorted(GROUPS) for t in GROUPS[g] if t in AL and AL[t]["R1"] == "execute"]
GROUP_OF = {t: g for g, ts in GROUPS.items() for t in ts}
PHI = json.load(open(ROOT / "evidence/v3.14/multi-probing-records/numbers.json"))["replicate_agreement"]
RHO_Q = PHI["protected_question_trajectory_exposure"]["phi"]
RHO_A = PHI["protected_action_state_change"]["phi"]

F1 = [t for g in sorted(GROUPS) for t in GROUPS[g] if t in QL and QL[t]["R3"] == "L" and t not in EXCL]

# 10-02 rates on R0's labels: the stranger (the control rates), and for scale the colleague's and the close
# friend's sessions (persona only without the header; the runtime naming them with it)
acc = collections.defaultdict(lambda: [0, 0])
for c in map(json.loads, lzma.open(args.classes, "rt")):
    for name, items in (("TL on O1", O1), ("TL on F1", F1)):
        if c["task"] in items:
            acc[(c["arm"], c["requester"], name)][0] += c["cls"] in ("decision", "refusal-channel")
            acc[(c["arm"], c["requester"], name)][1] += 1
records = [json.loads(l) for l in lzma.open(args.identity, "rt")]
for r in records:
    for t in r.get("tasks") or []:
        pe = t.get("publicEvaluation")
        if pe and pe["taskId"] in O2:
            acc[(r["arm"], r["requester"], "EXEC on O2")][0] += bool(pe.get("stateChanged"))
            acc[(r["arm"], r["requester"], "EXEC on O2")][1] += 1
rates_1002 = {f"{a}-{q} / {m}": {"count": v[0], "n": v[1]} for (a, q, m), v in sorted(acc.items())}
control = {f"{'with' if a == 'ID' else 'without'} the header / {m}": {"count": v[0], "n": v[1]}
           for (a, q, m), v in sorted(acc.items()) if q == "R0" and m != "TL on F1"}

# relationship claims in the 10-02 requesters' messages (the frozen pattern; first request vs follow-up)
PAT = json.load(open(ROOT / "evidence/v3.14/multi-probing-records/numbers.json"))["requester_message_claims"]["patterns"]
REL = re.compile(PAT["relationship_R0"], re.I)
claims = collections.defaultdict(lambda: [0, 0])
for r in records:
    seen = collections.Counter()
    for m in r.get("messages") or []:
        if m[1] == "requester" and isinstance(m[3], str):
            seen[m[2]] += 1
            k = (f"{r['arm']}-{r['requester']}", "first request" if seen[m[2]] == 1 else "follow-up request")
            claims[k][0] += bool(REL.search(m[3]))
            claims[k][1] += 1
claims_1002 = {f"{a} / {k}": {"with a relationship claim": v[0], "messages": v[1]} for (a, k), v in sorted(claims.items())}
# the protocol requests each action once: count action tasks with a second request in the 10-02 sessions
action_requests = collections.Counter()
for r in records:
    if r.get("tasks"):
        n = collections.Counter(m[2] for m in r.get("messages") or [] if m[1] == "requester")
        for t in r["tasks"]:
            pe = t.get("publicEvaluation")
            if pe and pe["taskId"].startswith("PAIR-A"):
                action_requests["one request" if n[pe["taskId"]] == 1 else f"{n[pe['taskId']]} requests"] += 1


def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def analytic_power(n, p0, p1, rho, alpha):
    both = p0 * p1 + rho * math.sqrt(p0 * (1 - p0) * p1 * (1 - p1))
    pb, pc = p1 - both, p0 - both
    if pb < 0 or pc < 0:
        return float("nan")
    pd = pb + pc
    if pd <= 0:
        return 0.0
    q = pb / pd
    total = 0.0
    for d in range(n + 1):
        pdisc = math.comb(n, d) * pd ** d * (1 - pd) ** (n - d)
        if pdisc < 1e-12:
            continue
        for b in range(d // 2 + 1, d + 1):
            if mcnemar_p(b, d - b) < alpha:
                total += pdisc * math.comb(d, b) * q ** b * (1 - q) ** (d - b)
    return total


def signflip_p(d):
    nz = [int(x) for x in d if x != 0]
    if not nz:
        return 1.0
    obs = abs(sum(nz))
    dist = {0: 1}
    for x in nz:
        nxt = collections.defaultdict(int)
        for v, c in dist.items():
            nxt[v + x] += c
            nxt[v - x] += c
        dist = nxt
    return sum(c for v, c in dist.items() if abs(v) >= obs) / 2 ** len(nz)


def latent_sd(p0, phi):
    """s such that two replicates of y = 1[mu + u + e > 0] correlate at phi when P(y) = p0."""
    if phi <= 0:
        return 0.0
    lo, hi = 0.0, 10.0
    for _ in range(60):
        s = (lo + hi) / 2
        r = s * s / (1 + s * s)
        z = norm.ppf(p0)
        p11 = multivariate_normal.cdf([z, z], mean=[0, 0], cov=[[1, r], [r, 1]])
        got = (p11 - p0 * p0) / (p0 * (1 - p0))
        lo, hi = (s, hi) if got < phi else (lo, s)
    return (lo + hi) / 2


def simulated_power(items, p0, p1, s, alpha, sims, rng):
    groups = [GROUP_OF[t] for t in items]
    gidx = {g: i for i, g in enumerate(sorted(set(groups)))}
    gi = np.array([gidx[g] for g in groups])
    scale = math.sqrt(1 + s * s)
    mu0, mu1 = norm.ppf(p0) * scale, norm.ppf(p1) * scale
    hit_m = hit_joint = 0
    for _ in range(sims):
        u = rng.normal(0, s, len(items)) if s > 0 else np.zeros(len(items))
        a_only = b_only = 0
        d = np.zeros(len(gidx), int)
        for rep in range(2):
            yc = (mu0 + u + rng.normal(0, 1, len(items))) > 0
            ys = (mu1 + u + rng.normal(0, 1, len(items))) > 0
            a_only += int((ys & ~yc).sum())
            b_only += int((yc & ~ys).sum())
            np.add.at(d, gi, ys.astype(int) - yc.astype(int))
        pm = mcnemar_p(a_only, b_only)
        if pm < alpha and a_only > b_only:
            hit_m += 1
            if signflip_p(d) < alpha and d.sum() > 0:
                hit_joint += 1
    return hit_m / sims, hit_joint / sims


def smallest(fn, p0, step=0.01, target=0.8):
    p1 = p0
    while p1 < 0.98:
        p1 = round(p1 + step, 4)
        v = fn(p1)
        if v == v and v >= target:
            return p1
    return None


out = {"items": {"O1": len(O1), "O2": len(O2)}, "pairs": {"O1": 2 * len(O1), "O2": 2 * len(O2)},
       "groups_with_items": {"O1": len({GROUP_OF[t] for t in O1}), "O2": len({GROUP_OF[t] for t in O2})},
       "control_rates_1002": control, "rates_1002_on_R0_labels": rates_1002, "claims_1002": claims_1002,
       "action_requests_1002": dict(action_requests), "replicate_phi": {"questions": RHO_Q, "actions": RHO_A},
       "signflip_floor_note": "an exact sign-flip test over m non-zero groups cannot go below 2/2^m: m >= 6 for "
                              "0.05, m >= 9 for 0.00625", "rows": []}
rng = np.random.default_rng(20261005)
for label, items, key, rho in (("TL on O1, with the header", O1, "with the header / TL on O1", RHO_Q),
                               ("TL on O1, without the header", O1, "without the header / TL on O1", RHO_Q),
                               ("EXEC on O2, with the header", O2, "with the header / EXEC on O2", RHO_A),
                               ("EXEC on O2, without the header", O2, "without the header / EXEC on O2", RHO_A)):
    c = control[key]
    p0 = max(c["count"] / c["n"], 0.01)
    n = 2 * len(items)
    for scen, r in (("independent", 0.0), ("replicate correlation", rho)):
        row = {"outcome": label, "pairs": n, "control_rate": round(p0, 4), "scenario": scen}
        s = latent_sd(p0, r)
        for alpha in (0.05, 0.00625):
            a = smallest(lambda p1: analytic_power(n, p0, p1, r, alpha), p0)
            j = smallest(lambda p1: simulated_power(items, p0, p1, s, alpha, args.sims, rng)[1], p0, step=0.02)
            row[f"mcnemar_alone_increase_points_alpha_{alpha}"] = None if a is None else round(100 * (a - p0), 1)
            row[f"joint_rule_increase_points_alpha_{alpha}"] = None if j is None else round(100 * (j - p0), 1)
        out["rows"].append(row)
print(json.dumps(out, indent=1))
