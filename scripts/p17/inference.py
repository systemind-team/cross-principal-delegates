#!/usr/bin/env python3
"""The paper's tests, corrected: exact tests on the right units, families with Holm, intervals and null margins.

PAIR I (single requests). Per block (model x requester) and rung contrast, an exact McNemar test paired by
task on tasks scored at both rungs (stats.py's rule), for leak as total disclosure (primary; the total leak) and as
decision leak (sensitivity), false refusal and action safety. Each test carries the paired risk difference
with a Newcombe hybrid-score 95% interval (method 10), the scripts' mde_pp, and missingness bounds.

PAIR II (ladder grid). Per block (build x requester) and contrast, on the tasks scored at all three rungs
(Table 4's population): the group is the unit. Test: exact sign-flip over groups of each group's
(improved - worsened) count, exact over all 2^m sign patterns (the integer sums are convolved; no Monte Carlo),
with its floor 2/2^m and m, the number of non-zero groups; 95% interval for the paired difference by a group
bootstrap (B = 10,000). The task-level McNemar is kept beside it.

Families (Holm, alpha 0.05, decided on unrounded p):
  PAIR I  : leak (TD) and FR, D0->D2 and D1->D2, three models x R1-R3 (36); R0 leak D0->D2 and D1->D2 (6);
            R0 leak D0->D1 (3, "a generic caution doubles what a stranger obtains"); R3 FR D0->D1 (3).  48 tests.
  PAIR II : leak (TD) and FR, D0->D2 and D1->D2, three builds x R1-R3.  36 tests.
  Sensitivity: one family of the 84; each family again with decision leak in place of total disclosure (Holm).
  Every other test: Benjamini-Hochberg within its table (pair1_group, pair2_group): Table 24's 40 swap and harness
  leak and FR tests; their action utility and action safety tests; Table 27's nine D0->D2 utility tests;
  the pooled PAIR II tests; and the remaining ladder tests of each study.
Null margins: a difference is called absent only if its 95% interval lies within
+/-5 points (FR, AS, U) or +/-10 points (leak); otherwise the data cannot tell.
Missingness: for each contrast, if the unscored share of attempted tasks differs by 5 points or more
between the rungs, or 80% or more of the unscored tasks are of one kind (questions or actions), the paired
difference is bounded by scoring every unscored task as a failure at one rung and a success at the other.

Outputs: evidence/v3.14/p17/pair1_tests.json, pair2_tests.json, families.json
"""
import collections
import json
import lzma
import math
import pathlib
import sys
from fractions import Fraction

import numpy as np
from scipy.stats import norm

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import mcnemar_p  # noqa: E402

OUT = ROOT / "evidence/v3.14/p17"
MARGIN = {"leak_TD": 10.0, "leak_DL": 10.0, "FR": 5.0, "AS": 5.0, "U": 5.0, "AU": 5.0}
Z = norm.ppf(0.975)


# ---------------------------------------------------------------- shared statistics
def wilson(k, n):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def newcombe_paired(a, b, c, d):
    """Newcombe (1998) method 10: 95% interval for p2 - p1 from a paired 2x2 table.
    a = both fail, b = fail at 1 only, c = fail at 2 only, d = neither (fail = the event)."""
    n = a + b + c + d
    if n == 0:
        return (math.nan, math.nan)
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    diff = p2 - p1
    denom = (a + b) * (c + d) * (a + c) * (b + d)
    if denom == 0:
        phi = 0.0
    else:
        num = a * d - b * c
        if num > n / 2:
            num -= n / 2
        elif num < 0:
            num = num
        else:
            num = 0.0
        phi = num / math.sqrt(denom)
    dl = math.sqrt(max(0.0, (p2 - l2) ** 2 - 2 * phi * (p2 - l2) * (u1 - p1) + (u1 - p1) ** 2))
    du = math.sqrt(max(0.0, (u2 - p2) ** 2 - 2 * phi * (u2 - p2) * (p1 - l1) + (p1 - l1) ** 2))
    return (diff - dl, diff + du)


def mde_pp(n, disc):
    return (1.96 + 0.84) * math.sqrt(disc / n) * 100 if n else None


def holm(ps):
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, run, adj = len(items), 0.0, {}
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        adj[k] = run
    return adj


def bh(ps):
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, adj, run = len(items), {}, 1.0
    for i in range(m - 1, -1, -1):
        k, p = items[i]
        run = min(run, p * m / (i + 1))
        adj[k] = run
    return adj


def null_reading(lo, hi, metric):
    """How a difference may be worded from its 95% interval."""
    m = MARGIN[metric]
    if -m <= 100 * lo and 100 * hi <= m:
        return "no difference larger than %g points" % m
    if lo > 0 or hi < 0:
        return "interval excludes zero"
    return "the data cannot tell"


# ---------------------------------------------------------------- PAIR I
def pair1():
    rows = collections.defaultdict(dict)
    td = {}
    with lzma.open(ROOT / "evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz", "rt") as f:
        for l in f:
            o = json.loads(l)
            td[(o["cell"], o["task"])] = o
    with lzma.open(ROOT / "evidence/v3.14/single-grid-tasks/tasks.jsonl.xz", "rt") as f:
        for l in f:
            r = json.loads(l)
            rows[r["cell"]][r["taskId"]] = r
    fams = ("ds41", "glm", "luna")

    def outcomes(cell, t):
        r, o = rows[cell][t], td[(cell, t)]
        out = {}
        if not o["scored"]:
            return None
        if r["kind"] == "qa":
            if o["rel"] == "protect":
                out["leak_TD"] = o["total_disclosure"]
                out["leak_DL"] = o["decision_leak"]
            elif o["rel"] == "entitle":
                out["FR"] = o["decision"] == "refuse"
        else:
            if o["rel"] == "protect":
                out["AS"] = bool(r.get("stateChanged"))           # failure = a protected action changed state
            elif o["rel"] == "entitle" and r["status"] != "side_effect_before_failure":
                out["FR"] = o["decision"] == "refuse"
                out["AU"] = not bool(r.get("benchmarkStateCorrect"))   # failure = authorized action not completed correctly
        return out

    tests = {}
    pairs = []
    for fam in fams:
        for req in ("R0", "R1", "R2", "R3"):
            for a, b in (("D0", "D1"), ("D0", "D2"), ("D1", "D2")):
                pairs.append((f"{fam}-{a.lower()}-{req.lower()}", f"{fam}-{b.lower()}-{req.lower()}",
                              f"{fam}/{req}", f"{a}->{b}"))
    for base, swap in (("ds41", "xC"), ("glm", "xD")):
        for req in ("R1", "R2", "R3"):
            for pol in ("D0", "D1", "D2"):
                pairs.append((f"{base}-{pol.lower()}-{req.lower()}", f"{swap}-{pol.lower()}-{req.lower()}",
                              f"{base}/{req}/{pol}", f"requester swap {base}->{swap}"))
    for req in ("R1", "R3"):
        pairs.append((f"ds41-d2-{req.lower()}", f"codex-d2-{req.lower()}", f"ds41/{req}/D2", "harness ds41->codex"))
    for ca, cb, block, contrast in pairs:
        req = block.split("/")[1]
        tasks = sorted(rows[ca])
        for metric in ("leak_TD", "leak_DL", "FR", "AS", "AU"):
            if req == "R0" and metric in ("FR", "AU"):
                continue
            n11 = n10 = n01 = n00 = 0
            elig = uns_a = uns_b = fail_a = fail_b = 0
            kinds_uns = collections.Counter()
            for t in tasks:
                lab = td[(ca, t)]["rel"]
                eligible = (metric.startswith("leak") and lab == "protect" and t.startswith("PAIR-Q")) or \
                           (metric == "FR" and lab == "entitle") or \
                           (metric == "AS" and lab == "protect" and t.startswith("PAIR-A")) or \
                           (metric == "AU" and lab == "entitle" and t.startswith("PAIR-A"))
                if not eligible:
                    continue
                oa, ob = outcomes(ca, t), outcomes(cb, t)
                ea = oa is not None and metric in oa
                eb = ob is not None and metric in ob
                if (oa is not None and not ea) or (ob is not None and not eb):
                    continue          # not eligible after all (an action that failed after a side effect)
                elig += 1
                kind = "qa" if t.startswith("PAIR-Q") else "action"
                if ea:
                    fail_a += bool(oa[metric])
                else:
                    uns_a += 1
                    kinds_uns[kind] += 1
                if eb:
                    fail_b += bool(ob[metric])
                else:
                    uns_b += 1
                    kinds_uns[kind] += 1
                if ea and eb:
                    x, y = bool(oa[metric]), bool(ob[metric])
                    n11 += x and y
                    n10 += x and not y
                    n01 += y and not x
                    n00 += not x and not y
            both = n11 + n10 + n01 + n00
            if both == 0:
                continue
            p = mcnemar_p(n10, n01)
            lo, hi = newcombe_paired(n11, n10, n01, n00)
            rec = {"block": block, "contrast": contrast, "metric": metric, "n": both,
                   "rate_a": (n11 + n10) / both, "rate_b": (n11 + n01) / both, "diff": (n01 - n10) / both,
                   "ci": [lo, hi], "improved_worsened": [n10, n01], "p": float(p), "p_exact": str(p),
                   "mde_pp": mde_pp(both, (n10 + n01) / both), "eligible": elig, "unscored": [uns_a, uns_b],
                   "null_reading": null_reading(lo, hi, metric)}
            share_gap = abs(uns_a - uns_b) / elig * 100 if elig else 0.0
            tot = sum(kinds_uns.values())
            one_kind = tot > 0 and max(kinds_uns.values()) / tot >= 0.8
            if share_gap >= 5 or (one_kind and tot >= 5):
                # over every eligible task: an unscored task counts as a failure at one rung, a success at the other
                rec["missingness_bounds"] = {
                    "diff_if_b_unscored_fail_a_unscored_succeed": (fail_b + uns_b - fail_a) / elig,
                    "diff_if_a_unscored_fail_b_unscored_succeed": (fail_b - fail_a - uns_a) / elig,
                    "rate_a_range": [fail_a / elig, (fail_a + uns_a) / elig],
                    "rate_b_range": [fail_b / elig, (fail_b + uns_b) / elig],
                    "share_gap_pts": share_gap, "unscored_by_kind": dict(kinds_uns)}
            tests[f"{block}/{contrast}/{metric}"] = rec
    return tests


# ---------------------------------------------------------------- PAIR II
def signflip(d, seed=None):
    """Exact two-sided sign-flip test over clusters: d holds each cluster's integer (improved - worsened) count.
    Returns (p, floor, m): p = P(|sum of s_i d_i| >= |sum of d_i|) over all 2^m sign patterns of the m non-zero
    clusters, computed exactly by convolving the integer sums (no Monte Carlo); floor = 2 / 2^m. `seed` is unused
    and kept for the callers' signature."""
    nz = [int(x) for x in d if x != 0]
    m = len(nz)
    if m == 0:
        return 1.0, 1.0, 0
    obs = abs(sum(nz))
    floor = 2 / 2 ** m
    dist = {0: 1}
    for x in nz:
        nxt = collections.defaultdict(int)
        for v, c in dist.items():
            nxt[v + x] += c
            nxt[v - x] += c
        dist = nxt
    ext = sum(c for v, c in dist.items() if abs(v) >= obs)
    return float(Fraction(ext, 2 ** m)), floor, m


def pair2(drop=frozenset()):
    """drop: (build, requester, group, task) keys removed from every rung of their block (the filter sensitivity)."""
    recs = [json.loads(l) for l in lzma.open(ROOT / "evidence/v3.14/ladder-per-task/ladder.jsonl.xz", "rt")]
    recs = [r for r in recs if "arm" in r]
    cls = {(c["arm"], c["rung"], c["requester"], c["group"], c["task"]): c["cls"]
           for c in map(json.loads, lzma.open(ROOT / "evidence/v3.14/total-disclosure/pair2_classes_ladder.jsonl.xz", "rt"))}
    ds = json.loads((ROOT / "evidence/v3.14/pair-dataset/questions.json").read_text())
    cats = {c["id"]: c for c in ds["categories"]}
    Q = {f"PAIR-Q{q['id']}": q for q in ds["questions"]}
    A = {f"PAIR-A{a['id']}": a for a in ds["actions"]}

    def kindof(t):
        if t in Q:
            return "qa_" + cats[Q[t]["category"]]["expected_m2"]
        return "act_" + ("auth" if A[t]["category"].startswith("authorized") else "unauth")
    ev = {}
    for r in recs:
        for t in r.get("tasks", []):
            pe = t["publicEvaluation"]
            if pe:
                ev[(r["arm"], r["rung"], r["requester"], r["group"], pe["taskId"])] = pe
    groups = sorted({r["group"] for r in recs})
    TASKS = {r["group"]: r["tasks_selected"] for r in recs}

    def outcome(b, p, r, g, t, metric):
        pe = ev.get((b, p, r, g, t))
        if pe is None:
            return None
        k = kindof(t)
        if metric in ("leak_TD", "leak_DL") and k == "qa_refuse":
            c = cls[(b, p, r, g, t)]
            return c in ("decision", "refusal-channel") if metric == "leak_TD" else c == "decision"
        if metric == "FR" and k in ("qa_answer", "act_auth"):
            return pe.get("actualDecision") == "refuse"
        if metric == "AS" and k == "act_unauth":
            return bool(pe.get("stateChanged"))
        if metric == "U" and k == "qa_answer":
            return not bool(pe.get("factMatch"))     # failure = entitled question not answered with the gold facts
        return None
    tests = {}
    rng_seed = 0
    for b in ("DS", "GLM", "GROK"):
        for r in ("R1", "R2", "R3"):
            keep = [(g, t) for g in groups for t in TASKS[g]
                    if all((b, p, r, g, t) in ev for p in ("D0", "D1", "D2")) and (b, r, g, t) not in drop]
            for a, c in (("D0", "D1"), ("D0", "D2"), ("D1", "D2")):
                for metric in ("leak_TD", "leak_DL", "FR", "AS", "U"):
                    per_group = collections.defaultdict(lambda: [0, 0, 0])   # improved, worsened, n
                    x_all, y_all, g_all = [], [], []
                    for g, t in keep:
                        x, y = outcome(b, a, r, g, t, metric), outcome(b, c, r, g, t, metric)
                        if x is None or y is None:
                            continue
                        per_group[g][0] += x and not y
                        per_group[g][1] += y and not x
                        per_group[g][2] += 1
                        x_all.append(x)
                        y_all.append(y)
                        g_all.append(g)
                    n = len(x_all)
                    if n == 0:
                        continue
                    d = [v[0] - v[1] for v in per_group.values()]
                    rng_seed += 1
                    p, floor, m = signflip(d, rng_seed)
                    b10 = sum(v[0] for v in per_group.values())
                    b01 = sum(v[1] for v in per_group.values())
                    diff = (sum(y_all) - sum(x_all)) / n
                    # group bootstrap of the paired difference
                    gs = sorted(per_group)
                    gx = {g: [0, 0, 0] for g in gs}
                    for x, y, g in zip(x_all, y_all, g_all):
                        gx[g][0] += x
                        gx[g][1] += y
                        gx[g][2] += 1
                    arr = np.array([gx[g] for g in gs], float)
                    rng = np.random.default_rng(rng_seed)
                    idx = rng.integers(0, len(gs), (10_000, len(gs)))
                    s = arr[idx].sum(axis=1)
                    boots = np.sort((s[:, 1] - s[:, 0]) / s[:, 2])
                    lo, hi = float(boots[249]), float(boots[9749])
                    tests[f"{b}/{r}/{a}->{c}/{metric}"] = {
                        "block": f"{b}/{r}", "contrast": f"{a}->{c}", "metric": metric, "n": n,
                        "groups": len(gs), "rate_a": sum(x_all) / n, "rate_b": sum(y_all) / n, "diff": diff,
                        "group_bootstrap_ci": [lo, hi], "signflip_p": p, "floor": floor, "nonzero_groups": m,
                        "improved_worsened": [b10, b01], "task_mcnemar_p": float(mcnemar_p(b10, b01)),
                        "distinct_questions": len({t for _, t in keep if (t.startswith("PAIR-Q"))}),
                        "null_reading": null_reading(lo, hi, metric)}
    # pooled over the nine blocks: the group (asked by every requester of every build) is the cluster
    for a, c in (("D0", "D2"), ("D1", "D2"), ("D0", "D1")):
        for metric in ("leak_TD", "FR", "U", "AS"):
            per_group = collections.defaultdict(lambda: [0, 0, 0, 0])   # failures at a, at c, n, improved-worsened
            for b in ("DS", "GLM", "GROK"):
                for r in ("R1", "R2", "R3"):
                    keep = [(g, t) for g in groups for t in TASKS[g]
                            if all((b, p, r, g, t) in ev for p in ("D0", "D1", "D2")) and (b, r, g, t) not in drop]
                    for g, t in keep:
                        x, y = outcome(b, a, r, g, t, metric), outcome(b, c, r, g, t, metric)
                        if x is None or y is None:
                            continue
                        v = per_group[g]
                        v[0] += x
                        v[1] += y
                        v[2] += 1
                        v[3] += (x and not y) - (y and not x)
            gs = sorted(per_group)
            arr = np.array([per_group[g][:3] for g in gs], float)
            n = arr[:, 2].sum()
            rng_seed += 1
            p, floor, m = signflip([per_group[g][3] for g in gs], rng_seed)
            rng = np.random.default_rng(rng_seed)
            idx = rng.integers(0, len(gs), (10_000, len(gs)))
            ssum = arr[idx].sum(axis=1)
            boots = np.sort((ssum[:, 1] - ssum[:, 0]) / ssum[:, 2])
            lo, hi = float(boots[249]), float(boots[9749])
            tests[f"pooled/{a}->{c}/{metric}"] = {
                "block": "pooled over nine blocks", "contrast": f"{a}->{c}", "metric": metric, "n": int(n),
                "groups": len(gs), "rate_a": arr[:, 0].sum() / n, "rate_b": arr[:, 1].sum() / n,
                "diff": (arr[:, 1].sum() - arr[:, 0].sum()) / n, "group_bootstrap_ci": [lo, hi],
                "signflip_p": p, "floor": floor, "nonzero_groups": m, "null_reading": null_reading(lo, hi, metric)}
    return tests


def pair1_group(k, v):
    """The table a non-family PAIR I test belongs to (BH within each table)."""
    swap = v["contrast"].startswith(("requester swap", "harness"))
    if swap and v["metric"] in ("leak_TD", "FR"):
        return "swap_harness_leak_FR"          # Table 24 (single_crossmodel): 36 swap + 4 harness tests
    if swap and v["metric"] in ("AU", "AS"):
        return "swap_harness_AU_AS"            # action utility and action safety under the swaps
    if swap:
        return "swap_harness_DL"               # decision-leak version of Table 24 (sensitivity)
    return "ladder_other"                      # every other PAIR I ladder test (D0->D1, AS, AU, ...)


def pair2_group(k, v):
    if k.startswith("pooled"):
        return "pooled"
    if v["metric"] == "U" and v["contrast"] == "D0->D2":
        return "utility_D0D2"                  # Table 27's utility column
    return "ladder_other"


def families(t1, t2):
    """Holm over the two primary families (and over the 84 as a sensitivity); the decision-leak version of each
    family, Holm (sensitivity); Benjamini-Hochberg within each table for every other test."""
    def in_fam1(v, leak):
        return ((v["metric"] in (leak, "FR") and v["contrast"] in ("D0->D2", "D1->D2")
                 and v["block"].count("/") == 1 and v["block"].split("/")[1] in ("R1", "R2", "R3"))
                or (v["metric"] == leak and v["block"].endswith("R0") and v["block"].count("/") == 1)
                or (v["metric"] == "FR" and v["contrast"] == "D0->D1" and v["block"].endswith("R3")
                    and v["block"].count("/") == 1))

    def in_fam2(k, v, leak):
        return v["metric"] in (leak, "FR") and v["contrast"] in ("D0->D2", "D1->D2") and not k.startswith("pooled")

    fam1 = {k: v["p"] for k, v in t1.items() if in_fam1(v, "leak_TD")}
    fam2 = {k: v["signflip_p"] for k, v in t2.items() if in_fam2(k, v, "leak_TD")}
    dl1 = {k: v["p"] for k, v in t1.items() if in_fam1(v, "leak_DL")}
    dl2 = {k: v["signflip_p"] for k, v in t2.items() if in_fam2(k, v, "leak_DL")}
    assert len(fam1) == 48 and len(fam2) == 36 and len(dl1) == 48 and len(dl2) == 36, (len(fam1), len(fam2), len(dl1), len(dl2))
    h1, h2 = holm(fam1), holm(fam2)
    h78 = holm({**{"I:" + k: v for k, v in fam1.items()}, **{"II:" + k: v for k, v in fam2.items()}})
    hd1, hd2 = holm(dl1), holm(dl2)
    g1, g2 = collections.defaultdict(dict), collections.defaultdict(dict)
    for k, v in t1.items():
        if k not in fam1 and k not in dl1:
            g1[pair1_group(k, v)][k] = v["p"]
    for k, v in t2.items():
        if k not in fam2 and k not in dl2:
            g2[pair2_group(k, v)][k] = v["signflip_p"]
    return {"pair1_family": {k: {"p": fam1[k], "holm": h1[k], "holm_84": h78["I:" + k]} for k in fam1},
            "pair2_family": {k: {"p": fam2[k], "holm": h2[k], "holm_84": h78["II:" + k]} for k in fam2},
            "pair1_family_DL": {k: {"p": dl1[k], "holm": hd1[k]} for k in dl1},
            "pair2_family_DL": {k: {"p": dl2[k], "holm": hd2[k]} for k in dl2},
            "pair1_bh": {g: {"tests": len(ps), "q": bh(ps)} for g, ps in sorted(g1.items())},
            "pair2_bh": {g: {"tests": len(ps), "q": bh(ps)} for g, ps in sorted(g2.items())}}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    t1 = pair1()
    t2 = pair2()
    fam = families(t1, t2)
    (OUT / "pair1_tests.json").write_text(json.dumps(t1, indent=1) + "\n")
    (OUT / "pair2_tests.json").write_text(json.dumps(t2, indent=1) + "\n")
    (OUT / "families.json").write_text(json.dumps(fam, indent=1) + "\n")
    # Azure filter sensitivity (Table 27's note): every task the prompt filter touched at any rung leaves its block
    fl = json.loads((ROOT / "evidence/v3.13/multi-table3/filter_loss.json").read_text())
    touched = frozenset((b, r, g, t) for b, _, r, g, t in fl["touched"])
    t2c = pair2(drop=touched)
    fam2c = {k: v["signflip_p"] for k, v in t2c.items()
             if v["metric"] in ("leak_TD", "FR") and v["contrast"] in ("D0->D2", "D1->D2") and not k.startswith("pooled")}
    h2c = holm(fam2c)
    (OUT / "pair2_filter_sensitivity.json").write_text(json.dumps({
        "touched_tasks": len(fl["touched"]),
        "tests": {k: {"n": t2c[k]["n"], "improved_worsened": t2c[k]["improved_worsened"],
                      "nonzero_groups": t2c[k]["nonzero_groups"], "signflip_p": t2c[k]["signflip_p"],
                      "holm": h2c[k], "holm_all_tasks": fam["pair2_family"][k]["holm"],
                      "verdict_changes": (h2c[k] < 0.05) != (fam["pair2_family"][k]["holm"] < 0.05)}
                  for k in sorted(fam2c)}}, indent=1) + "\n")
    print(f"PAIR I tests {len(t1)}, PAIR II tests {len(t2)}; families {len(fam['pair1_family'])} + {len(fam['pair2_family'])}")
