#!/usr/bin/env python3
"""P1-2 agreement statistics (protocol §6), used by score.py.

  cohen_kappa(a, b)                  unweighted Cohen's kappa
  weighted_kappa(a, b, order)        linearly weighted kappa on an ordered scale
  gwet_ac1(a, b)                     Gwet's AC1, beside kappa where prevalence is low
  bootstrap_ci(stat, pairs, ...)     percentile interval, resampling items or clusters (instances)
  clopper_pearson(x, n)              exact binomial interval

Run directly for a self-test against values computed by hand.
"""
import collections
import math
import random

BINARY = {"FULL": 1, "PARTIAL": 1, "EXISTENCE": 0, "NONE": 0}
ORDER = ("NONE", "EXISTENCE", "PARTIAL", "FULL")


def cohen_kappa(a, b):
    n = len(a)
    cats = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[c] * cb[c] for c in cats) / n ** 2
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def weighted_kappa(a, b, order=ORDER):
    k = len(order)
    pos = {c: i for i, c in enumerate(order)}
    n = len(a)
    w = lambda i, j: 1 - abs(i - j) / (k - 1)
    po = sum(w(pos[x], pos[y]) for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(w(pos[x], pos[y]) * ca[x] * cb[y] for x in order for y in order) / n ** 2
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def gwet_ac1(a, b):
    n = len(a)
    cats = sorted(set(a) | set(b))
    q = len(cats)
    if q < 2:
        return 1.0
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pi = {c: (ca[c] + cb[c]) / (2 * n) for c in cats}
    pe = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    return (po - pe) / (1 - pe)


def bootstrap_ci(stat, units, b=2000, seed=20261004, level=0.95):
    """units: a list of clusters, each a list of (label_a, label_b) pairs; resampled with replacement."""
    rng = random.Random(seed)
    vals = []
    for _ in range(b):
        sample = [pair for _ in units for pair in rng.choice(units)]
        a, bb = [x for x, _ in sample], [y for _, y in sample]
        v = stat(a, bb)
        if v == v:
            vals.append(v)
    vals.sort()
    lo = vals[int((1 - level) / 2 * len(vals))]
    hi = vals[int((1 + level) / 2 * len(vals)) - 1]
    return lo, hi


def _cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(x, n, level=0.95):
    alpha = (1 - level) / 2

    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2

    lower = 0.0 if x == 0 else solve(lambda p: 1 - _cdf(x - 1, n, p) < alpha)
    upper = 1.0 if x == n else solve(lambda p: _cdf(x, n, p) > alpha)
    return lower, upper


if __name__ == "__main__":
    # Hand-computed check: 2x2 table [[20, 5], [10, 15]] (n = 50): po = 0.7, pe = 0.5, kappa = 0.4.
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert abs(cohen_kappa(a, b) - 0.4) < 1e-12
    # AC1 on the same table: pi_y = 0.55, pe = 2 * 0.55 * 0.45 = 0.495, AC1 = (0.7 - 0.495) / 0.505.
    assert abs(gwet_ac1(a, b) - (0.7 - 0.495) / 0.505) < 1e-12
    # Weighted kappa equals unweighted kappa on a two-point scale.
    assert abs(weighted_kappa(a, b, order=("n", "y")) - 0.4) < 1e-12
    # Clopper-Pearson: 0 of 10 gives an upper bound of 1 - 0.025 ** (1/10) = 0.3085.
    assert abs(clopper_pearson(0, 10)[1] - (1 - 0.025 ** 0.1)) < 1e-9
    print("agreement.py self-test passed")
