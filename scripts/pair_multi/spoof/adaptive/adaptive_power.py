"""P2-3 adaptive attacker: detectable effect. Design numbers only, no spend.

The primary comparator is the CONCURRENT degenerate-attacker control (Gemini, plain asking), whose O1 total-leak
rate is not known a priori, so the detectable effect is reported as a function of that control base rate. The
primary family is Holm over P1 (O1) and P2 (rest questions); the joint rule requires the exact McNemar and the
exact group sign-flip to both reject in the adaptive direction. For a two-test Holm family the first (smaller)
p-value is compared with alpha/2, so the planning alpha for the harder test is 0.025; 0.05 is also reported.

It reports, for 1 replicate per arm (51 O1 pairs, 22 O2 pairs) and 2 replicates (102, 44), and for a sweep of
control base rates, the smallest adaptive-arm rate detectable at 80% power under the joint rule, as an increase
in points. The lower (item-correlated) value assumes the two arms share item effects as two replicates of one
arm do (phi 0.54 on O1, 0.69 on O2); the independent value is the planning number. P2's base is near
zero, so any real effect there is easy to detect; O2 is gated behind P1.

The group layout (51 questions in 49 groups, 22 actions in 22 groups) is P1-6's, from power.json.

Usage: python3 adaptive_power.py > ../../../../evidence/v3.14/multi-adaptive/power.json
"""
import json
import math
import pathlib

import numpy as np
from scipy.stats import multivariate_normal, norm

ROOT = pathlib.Path(__file__).resolve().parents[4]
P16 = json.loads((ROOT / "evidence/v3.14/multi-spoof/design/power.json").read_text())
N_O1, N_O2 = 51, 22
GROUPS_O1 = P16["groups_with_items"]["O1"]
GROUPS_O2 = P16["groups_with_items"]["O2"]
PHI_Q, PHI_A = 0.54, 0.69
SIMS = 1500


def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def signflip_p(d):
    nz = [int(x) for x in d if x != 0]
    if not nz:
        return 1.0
    obs = abs(sum(nz))
    dist = {0: 1}
    for x in nz:
        nxt = {}
        for v, cnt in dist.items():
            nxt[v + x] = nxt.get(v + x, 0) + cnt
            nxt[v - x] = nxt.get(v - x, 0) + cnt
        dist = nxt
    return sum(cnt for v, cnt in dist.items() if abs(v) >= obs) / 2 ** len(nz)


def latent_sd(p0, phi):
    if phi <= 0:
        return 0.0
    lo, hi = 0.0, 10.0
    for _ in range(60):
        s = (lo + hi) / 2
        r = s * s / (1 + s * s)
        z = norm.ppf(min(max(p0, 1e-4), 1 - 1e-4))
        p11 = multivariate_normal.cdf([z, z], mean=[0, 0], cov=[[1, r], [r, 1]])
        got = (p11 - p0 * p0) / (p0 * (1 - p0))
        lo, hi = (s, hi) if got < phi else (lo, s)
    return (lo + hi) / 2


def sim_power(n_items, n_groups, p0, p1, s, alpha, reps, rng):
    base = n_items // n_groups
    rem = n_items - base * n_groups
    groups = []
    for g in range(n_groups):
        groups += [g] * (base + (1 if g < rem else 0))
    groups = np.array(groups)
    scale = math.sqrt(1 + s * s)
    mu0, mu1 = norm.ppf(min(max(p0, 1e-4), 1 - 1e-4)) * scale, norm.ppf(min(max(p1, 1e-4), 1 - 1e-4)) * scale
    hit = 0
    for _ in range(SIMS):
        u = rng.normal(0, s, n_items) if s > 0 else np.zeros(n_items)
        a_only = b_only = 0
        d = np.zeros(n_groups, int)
        for _r in range(reps):
            yc = (mu0 + u + rng.normal(0, 1, n_items)) > 0
            ys = (mu1 + u + rng.normal(0, 1, n_items)) > 0
            a_only += int((ys & ~yc).sum())
            b_only += int((yc & ~ys).sum())
            np.add.at(d, groups, ys.astype(int) - yc.astype(int))
        if mcnemar_p(a_only, b_only) < alpha and a_only > b_only and signflip_p(list(d)) < alpha and d.sum() > 0:
            hit += 1
    return hit / SIMS


def smallest(fn, p0, step=0.01, target=0.8):
    p1 = p0
    while p1 < 0.98:
        p1 = round(p1 + step, 4)
        v = fn(p1)
        if v == v and v >= target:
            return p1
    return None


rng = np.random.default_rng(20261024)
out = {
    "comparator": "concurrent degenerate-attacker control (Gemini, plain asking); its O1 total-leak rate is "
                  "unknown a priori, so the detectable effect is reported over a sweep of control base rates. "
                  "The pilot's observed control rate fixes the planning value.",
    "family": "Holm over P1 (O1) and P2 (rest questions); joint rule (exact McNemar AND exact group sign-flip "
              "both reject in the adaptive direction). First Holm step alpha = 0.025 for a two-test family.",
    "a_priori_anchors": {"A0h_O1_1005": round(P16["control_rates_1002"]["with the header / TL on O1"]["count"]
                                             / P16["control_rates_1002"]["with the header / TL on O1"]["n"], 4)
                         if "control_rates_1002" in P16 else None},
    "note_P2": "rest-questions base is near zero (P1-6 header arms 0 of 96), so P2 has a low false-positive "
               "rate, but the exact group sign-flip needs at least 7 of the 48 groups to show an adaptive-only "
               "leak at Holm's first step (6 at the second), so the smallest detectable effect is about 15 "
               "points at one replicate and about 7 at two. P2 is co-primary, not a cheap detector of "
               "a few points.",
    "note_O2": "O2 is tested at 0.05 only if P1 counts; at 44 pairs vs a near-zero control, a "
               "few-point increase is detectable.",
    "rows": [],
}
for reps, pairs_o1, pairs_o2 in ((2, 2 * N_O1, 2 * N_O2), (1, N_O1, N_O2)):
    for control_rate in (0.05, 0.10, 0.16):
        p0 = max(control_rate, 0.01)
        row = {"replicates_per_arm": reps, "O1_pairs": pairs_o1, "control_base_rate": control_rate}
        for alpha_label, alpha in (("alpha_0.05", 0.05), ("alpha_0.025_holm_first_step", 0.025)):
            for scen, phi in (("independent", 0.0), ("item_correlated", PHI_Q)):
                s = latent_sd(p0, phi if reps == 2 else 0.0)
                inc = smallest(lambda p1: sim_power(N_O1, GROUPS_O1, p0, p1, s, alpha, reps, rng), p0)
                row[f"O1_detectable_increase_points__{alpha_label}__{scen}"] = None if inc is None else round(100 * (inc - p0), 1)
        out["rows"].append(row)
# O2 (near-zero control) at 0.05, both sizes, independent only (zero base is unstable under correlation)
for reps, pairs in ((2, 2 * N_O2), (1, N_O2)):
    p0 = 0.01
    inc = smallest(lambda p1: sim_power(N_O2, GROUPS_O2, p0, p1, 0.0, 0.05, reps, rng), p0, step=0.02)
    out.setdefault("O2", []).append({"replicates_per_arm": reps, "O2_pairs": pairs, "control_base_rate": "~0",
                                     "detectable_increase_points_alpha_0.05_independent": None if inc is None else round(100 * (inc - p0), 1)})
print(json.dumps(out, indent=1))
