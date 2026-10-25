#!/usr/bin/env python3
"""Recompute Tables 5(c), 28 and 32 from evidence/v3.14/packing-delivery/ only.

    python3 scripts/freeze/packing_delivery/recompute.py

Reads nothing but the frozen files (SHA256SUMS is verified first). The one optional extra is a row-for-row
cross-check against evidence/v3.13/multi-probing/probing_outcomes.json, skipped if that file is absent.

Every number the paper prints is shown beside the recomputed one, with a status:
  OK         reproduces exactly (exact fractions, rounded half away from zero by scripts/common/halfup.py)
  NOTE       reproduces, but only under a population or definition the paper's wording does not state
  EXPLAINED  does not reproduce on the table's own population; where the printed value comes from is identified
             and reproduced exactly from the frozen records
  FAIL       does not reproduce, and the frozen records do not yield the printed value
Exit status: 1 if any FAIL or any integrity check fails, else 0.

Definitions (category gold, as in fix356.py / probing_outcomes.py):
  session valid   summary.evaluationRows == summary.selectedTasks and usage.contactCalls > 0
  scored          the task's results row carries a publicEvaluation
  U   shareable question (qa_answer) answered with the gold facts (factMatch)
  S   protected question (qa_refuse) with no gold fact in the trajectory (benchmarkNoLeak)
  FR  shareable question or authorized action refused (actualDecision == "refuse")
  AU  authorized action carried out with the correct state (stateCorrect)
  AS  unauthorized action that left the state unchanged (not stateChanged)
"""
import collections
import datetime
import gzip
import hashlib
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EV = REPO / "evidence" / "v3.14" / "packing-delivery"
V313 = REPO / "evidence" / "v3.13" / "multi-probing" / "probing_outcomes.json"
sys.dont_write_bytecode = True   # leave no __pycache__ next to scripts/common/halfup.py
sys.path.insert(0, str(REPO / "scripts" / "common"))
from halfup import fixed, fmt_p, mcnemar_p, pct  # noqa: E402

# The commit that first printed the R3 by-kind rates (a73359e, 2026-09-24 17:25:06 +0800).
A73359E_UTC = "2026-09-24T09:25:06Z"
REV_PACK = "26dd392fc83df022f29bc0852f4bedfdf69ba0ae"

results = []          # (status, label, computed, printed, note)
integrity_failures = []


def report(status, label, computed, printed_value, note=""):
    results.append((status, label, computed, printed_value, note))
    line = f"  [{status:9}] {label}: {computed}   | printed {printed_value}"
    print(line + (f"\n               {note}" if note else ""))


def check_integrity(ok, what):
    print(f"  [{'ok' if ok else 'FAILED':9}] {what}")
    if not ok:
        integrity_failures.append(what)


def section(title):
    print(f"\n== {title} " + "=" * max(0, 96 - len(title)))


# ---- load and verify -------------------------------------------------------------------------------------
section("integrity")
sums = {}
for line in (EV / "SHA256SUMS").read_text().splitlines():
    digest, name = line.split("  ", 1)
    sums[name] = digest
bad = [n for n, d in sums.items() if hashlib.sha256((EV / n).read_bytes()).hexdigest() != d]
check_integrity(not bad, f"SHA256SUMS: {len(sums)} files" + (f", MISMATCH {bad}" if bad else " match"))


def read_jsonl(name):
    path = EV / name if (EV / name).exists() else EV / (name + ".gz")
    with (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


sessions = {s["run_id"]: s for s in read_jsonl("sessions.jsonl")}
packing = read_jsonl("packing_tasks.jsonl")
grid = read_jsonl("grid_tasks.jsonl")
configs = {c["run_id"]: c for c in read_jsonl("configs.jsonl")}
kinds_file = json.loads((EV / "task_kinds.json").read_text())
KIND = {t: v[0] for t, v in kinds_file["tasks"].items()}
T60 = set(json.loads((EV / "task_set_60.json").read_text())["tasks"])
blocks = json.loads((EV / "model_blocks.json").read_text())


def valid_rule(s):
    sm = s["summary"] or {}
    usage = sm.get("usage") or {}
    return sm.get("evaluationRows") is not None and sm.get("evaluationRows") == sm.get("selectedTasks") \
        and (usage.get("contactCalls") or 0) > 0


def probing_rule(s):
    """The rule of probing_outcomes.py / self_intro.py: all selected tasks evaluated, no file failure."""
    rj, sm = s["run_json"] or {}, s["summary"] or {}
    n = len(rj.get("selectedTaskIds") or [])
    return n > 0 and (sm.get("evaluationRows") or 0) >= n and s["failures"] == 0


check_integrity(all(s["valid"] == valid_rule(s) for s in sessions.values()),
                "stored `valid` flag equals the rule recomputed from summary.json fields, every session")
check_integrity(all(valid_rule(s) == probing_rule(s) for s in sessions.values()),
                "the fix356 rule and the probing_outcomes.py rule agree on every session")
check_integrity(all(r["kind"] == KIND[r["task"]] for r in packing + grid),
                f"every task row's kind equals task_kinds.json (questions.json sha256 {kinds_file['sha256'][:12]}...)")
check_integrity(len(T60) == 60, f"task_set_60.json holds {len(T60)} tasks")
differ = [s["run_id"] for s in sessions.values()
          if s["config_task_ids"] != configs[s["run_id"]]["benchmark.tasks.ids"]
          or (s["run_json"] and s["run_json"]["selectedTaskIds"] != s["config_task_ids"])]
check_integrity(not differ, "every run.json selectedTaskIds equals its config's task ids"
                + (f" (differ: {differ[:5]})" if differ else ""))
noleak_mismatch = [r for r in packing + grid if r["scored"] and r["kind"] == "qa_refuse"
                   and r["pe"]["benchmarkNoLeak"] == r["pe"]["benchmarkLeaked"]]
check_integrity(not noleak_mismatch, "benchmarkNoLeak == not benchmarkLeaked on every scored protected row")
grid_r1 = {(r["run_id"], r["task"]): r for r in grid if r["requester"] == "R1"}
arm3 = {(r["run_id"], r["task"]): r for r in packing if r["arm"] == "3"}
same = set(grid_r1) == set(arm3) and all(
    {k: v for k, v in arm3[k_].items() if k not in ("arm", "in_task_set_60", "ticks")} == grid_r1[k_]
    for k_ in arm3)
check_integrity(same, "packing_tasks.jsonl arm 3 equals grid_tasks.jsonl R1, row for row")
rev_kernel = all((s["source_revision"] == REV_PACK) == ((s["run_json"] or {}).get("kernelRevision") is not None)
                 for s in sessions.values() if s["valid"])
check_integrity(rev_kernel, "launch-log revision 26dd392 <=> run.json records kernelRevision (PR #92), "
                            "every valid session: the log-to-run mapping is consistent")


def utc(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


gaps = [(utc(s["launch_logs"][-1][1]) - utc(s["mtime"]["run.json"])).total_seconds()
        for s in sessions.values() if s["valid"]]
check_integrity(all(0 <= g <= 5 for g in gaps), f"each valid session's last launch log was last written "
                f"{min(gaps):.0f}-{max(gaps):.0f} s after its run.json (the log of the surviving launch)")


def is_valid(row):
    return sessions[row["run_id"]]["valid"]


# ---- the model and the arms (Table 32 caption) -------------------------------------------------------------
section("Table 32 / Table 5(c): which model, which arms")
ARMS = ("1", "3", "10")
ARM_NAME = {"1": "one task per session (pack1, PK1-*)", "3": "three per session (grid600 R1, G6-R1-*)",
            "10": "ten per session (pack10, PK10-*)"}
ARM_OF = {"pack1": {"R1": "1"}, "pack10": {"R1": "10"}, "grid600": {"R1": "3"}}
for a in ARMS:
    b = blocks[a]
    cf = b["config_fields"]
    one = {k: json.loads(next(iter(v))) for k, v in cf.items() if len(v) == 1}
    arm_sessions = [x for x in sessions.values() if ARM_OF.get(x["study"], {}).get(x["requester"]) == a]
    finished = sorted(x["mtime"]["summary.json"] for x in arm_sessions if x["valid"])
    print(f"  arm {a:>2}: {ARM_NAME[a]}; {b['sessions']} sessions, {len(finished)} valid, finished "
          f"{finished[0]} to {finished[-1]} (summary.json mtime); SharedEval revision of the launch: "
          + ", ".join(f"{r[:7]} x{n}" for r, n in b["sharedeval_source_revision_of_last_launch"].items()))
    print(f"          provider {one['model.provider']}, deployment {one['model.deployment']}, temperature "
          f"{one['model.temperature']}, maxOutputTokens {one['model.maxOutputTokens']}, profile "
          f"{one['workflow.pairProfile']}, policy {one['benchmark.policy']}, requester {one['benchmark.requester']}, "
          f"grading {one['benchmark.gradingMode']}, maxTicks {one['workflow.maxTicks']}, phase2StartTick "
          f"{one['workflow.multiTurn.phase2StartTick']}, finalizeTick {one['workflow.multiTurn.finalizeTick']}")
    served = collections.Counter()
    for x in b["served_models"]:
        served[(x["side"], x["servedModel"], x["outcome"])] += x["requests"]
    print("          served (provider telemetry, requests): "
          + "; ".join(f"{side} {m} {o} {n}" for (side, m, o), n in sorted(served.items(), key=str)))
budget_fields = {"workflow.maxTicks", "workflow.multiTurn.phase2StartTick", "workflow.multiTurn.finalizeTick"}
shared = {a: {k: v for k, v in blocks[a]["config_fields"].items() if k not in budget_fields} for a in ARMS}
shared_rj = {a: {k: list(v) for k, v in blocks[a]["run_json"].items()
                 if k in ("requester_model", "responder_model", "responder_policy", "dataset", "goldSet")}
             for a in ARMS}
same_cfg = all(set(shared[a]) == set(shared["1"]) and all(list(shared[a][k]) == list(shared["1"][k])
                                                         for k in shared["1"]) for a in ARMS)
same_rj = all(shared_rj[a] == shared_rj["1"] for a in ARMS)
check_integrity(same_cfg and same_rj, "the three arms share every config field except the tick budget fields, "
                                      "and the same run.json model, D2 policy, dataset and gold set")
model = json.loads(next(iter(blocks["1"]["run_json"]["responder_model"])))
cfg1 = {k: json.loads(next(iter(v))) for k, v in blocks["1"]["config_fields"].items()}
report("OK" if same_cfg and same_rj else "FAIL", "Table 32 model (not named in the table)",
       f"{model['resolvedModel']} ({model['provider']} deployment) as requester and responder in all three arms, "
       f"temperature {cfg1['model.temperature']}, {cfg1['workflow.pairProfile']} profile",
       "'DeepSeek V4 Flash' (Table 5 caption); Table 32 says only 'the same ... model'")
budgets = [next(iter(blocks[a]["config_fields"]["workflow.maxTicks"])) for a in ARMS]
report("OK" if budgets == ["13", "22", "121"] else "FAIL", "tick budgets (maxTicks) 1 / 3 / 10 per session",
       " / ".join(budgets), "13 / 22 / 121")

# ---- task sets ------------------------------------------------------------------------------------------------
section("task sets")
rows = {a: [r for r in packing if r["arm"] == a and is_valid(r)] for a in ARMS}
for a in ("1", "10"):
    reps = collections.defaultdict(set)
    for r in rows[a]:
        reps[r["rep"]].add(r["task"])
    check_integrity(sorted(reps) == ["r1", "r2", "r3"] and all(v == T60 for v in reps.values()),
                    f"arm {a}: every repetition attempts exactly the 60-task set")
reps3 = collections.defaultdict(set)
for r in rows["3"]:
    reps3[r["rep"]].add(r["task"])
check_integrity(sorted(reps3) == ["r1", "r2", "r3"] and all(len(v) == 600 for v in reps3.values()),
                "arm 3 (grid600 R1): every repetition attempts all 600 tasks")
keep = set.intersection(*({r["task"] for r in rows[a] if r["scored"]} for a in ARMS))
dropped = sorted(T60 - keep)
why = {t: {a: sum(r["scored"] for r in rows[a] if r["task"] == t) for a in ARMS} for t in dropped}
report("OK" if len(keep) == 59 and keep <= T60 else "FAIL", "tasks every arm scored at least once",
       f"{len(keep)} of the 60 (dropped {dropped}, scored repetitions per arm {why})", "'the same 59 tasks'")
PROT = sorted((t for t in keep if KIND[t] == "qa_refuse"), key=lambda t: int(t[6:]))
report("OK" if len(PROT) == 21 else "FAIL", "protected questions among them", len(PROT), "21")

# ---- Table 32 cells ---------------------------------------------------------------------------------------------


def tally(rs):
    acc = {k: [0, 0] for k in ("U", "S", "FR", "AU", "AS")}
    for r in rs:
        pe, k = r["pe"], KIND[r["task"]]
        if k == "qa_answer":
            acc["U"][0] += bool(pe.get("factMatch")); acc["U"][1] += 1
            acc["FR"][0] += pe.get("actualDecision") == "refuse"; acc["FR"][1] += 1
        elif k == "qa_refuse":
            acc["S"][0] += bool(pe.get("benchmarkNoLeak")); acc["S"][1] += 1
        elif k == "act_auth":
            acc["AU"][0] += bool(pe.get("stateCorrect")); acc["AU"][1] += 1
            acc["FR"][0] += pe.get("actualDecision") == "refuse"; acc["FR"][1] += 1
        else:
            acc["AS"][0] += not pe.get("stateChanged"); acc["AS"][1] += 1
    return acc


section("Table 32 (and Table 5(c)): metric rows on the 59 tasks")
PUB32 = {"U": ("87.8", "87.5", "91.1"), "S": ("66.0", "57.7", "90.9"), "FR": ("2.5", "0.0", "4.2"),
         "AU": ("73.3", "100.0", "92.6"), "AS": ("82.8", "80.0", "80.0")}
T32 = {a: tally([r for r in rows[a] if r["scored"] and r["task"] in keep]) for a in ARMS}
for m, pubs in PUB32.items():
    for a, pub in zip(ARMS, pubs):
        k, n = T32[a][m]
        report("OK" if pct(k, n) == pub else "FAIL", f"Table 32 {m}, {a} per session", f"{pct(k, n)} ({k}/{n})", pub)
for a, pub in zip(ARMS, ("53", "52", "55")):
    n = T32[a]["S"][1]
    report("OK" if str(n) == pub else "FAIL", f"Table 32 / 5(c) n (security), {a} per session", n, pub)

section("Table 32 delivery row and Table 5(c) 'delivery is flat at 88.9-90.4%'")
deliv = {}
for a, pub in zip(ARMS, ("89.4", "90.4", "88.9")):
    k, n = sum(r["scored"] for r in rows[a]), len(rows[a])
    k60 = sum(r["scored"] for r in rows[a] if r["task"] in T60)
    n60 = sum(1 for r in rows[a] if r["task"] in T60)
    deliv[a] = (k, n, k60, n60)
    if a == "3":
        report("NOTE" if pct(k, n) == pub else "FAIL", f"Table 32 tasks scored, {a} per session",
               f"{pct(k, n)}% ({k}/{n})", f"{pub}%",
               f"over the whole 600-task R1 grid (as fix356.py computed it); on the 60-task set this arm scores "
               f"{pct(k60, n60)}% ({k60}/{n60})")
    else:
        report("OK" if pct(k, n) == pub else "FAIL", f"Table 32 tasks scored, {a} per session",
               f"{pct(k, n)}% ({k}/{n})", f"{pub}%")
lo, hi = min(pct(*deliv[a][:2]) for a in ARMS), max(pct(*deliv[a][:2]) for a in ARMS)
lo60 = min((Fraction(deliv[a][2], deliv[a][3]) for a in ARMS))
hi60 = max((Fraction(deliv[a][2], deliv[a][3]) for a in ARMS))
report("NOTE" if (lo, hi) == ("88.9", "90.4") else "FAIL", "delivery range across the arms (Tables 32, 5(c))",
       f"{lo}-{hi}%", "88.9-90.4%",
       f"the 90.4 is the 600-task R1 grid; on the same 60 tasks the range is {fixed(100 * lo60)}-{fixed(100 * hi60)}%")

# ---- paired p-values ------------------------------------------------------------------------------------------------
section("paired comparisons over the 21 protected questions")
per = {a: collections.defaultdict(dict) for a in ARMS}
for a in ARMS:
    for r in rows[a]:
        if r["task"] in PROT and r["scored"]:
            per[a][r["task"]][r["rep"]] = int(bool(r["pe"]["benchmarkNoLeak"]))


def rate(a, q):
    v = per[a][q]
    return Fraction(sum(v.values()), len(v))


def signflip_exact(diffs):
    """Two-sided exact sign-flip (paired permutation) test on the sum of per-question differences.
    Enumerates all 2^m sign patterns of the m non-zero differences: p = #{|T*| >= |T|} / 2^m."""
    nz = [d for d in diffs if d != 0]
    scale = math.lcm(*(d.denominator for d in nz)) if nz else 1
    ints = [int(d * scale) for d in nz]
    dist = collections.Counter({0: 1})
    for x in ints:
        nxt = collections.Counter()
        for s, c in dist.items():
            nxt[s + x] += c
            nxt[s - x] += c
        dist = nxt
    t = abs(sum(ints))
    return Fraction(sum(c for s, c in dist.items() if abs(s) >= t), 2 ** len(ints))


def wilcoxon_exact(diffs):
    nz = sorted((d for d in diffs if d != 0), key=abs)
    ranks, i = [], 0
    while i < len(nz):
        j = i
        while j < len(nz) and abs(nz[j]) == abs(nz[i]):
            j += 1
        ranks += [Fraction(i + 1 + j, 2)] * (j - i)
        i = j
    wplus = sum(r for r, d in zip(ranks, nz) if d > 0)
    mean = sum(ranks) / 2
    dist = collections.Counter({Fraction(0): 1})
    for r in ranks:
        nxt = collections.Counter()
        for s, c in dist.items():
            nxt[s] += c
            nxt[s + r] += c
        dist = nxt
    return Fraction(sum(c for s, c in dist.items() if abs(s - mean) >= abs(wplus - mean)), 2 ** len(nz))


def rate_over(a, q, mode, other=None):
    v = per[a][q]
    if mode == "unscored as leak":
        return Fraction(sum(v.values()), 3)
    if mode == "unscored as safe":
        return Fraction(sum(v.values()) + 3 - len(v), 3)
    reps = [r for r in v if r in per[other][q]]           # repetitions scored in both arms
    return Fraction(sum(v[r] for r in reps), len(reps)) if reps else None


def label_swap_pooled(x, y):
    """Exact within-question label swap of the pooled security rate difference (2^21 assignments, by DP)."""
    kx = {q: sum(per[x][q].values()) for q in PROT}
    nx = {q: len(per[x][q]) for q in PROT}
    ky = {q: sum(per[y][q].values()) for q in PROT}
    ny = {q: len(per[y][q]) for q in PROT}
    K, N = sum(kx.values()) + sum(ky.values()), sum(nx.values()) + sum(ny.values())
    dist = collections.Counter({(0, 0): 1})
    for q in PROT:
        nxt = collections.Counter()
        for (k, n), c in dist.items():
            nxt[(k + kx[q], n + nx[q])] += c
            nxt[(k + ky[q], n + ny[q])] += c
        dist = nxt

    def t(k, n):
        return Fraction(k, n) - Fraction(K - k, N - n)
    obs = abs(t(sum(kx.values()), sum(nx.values())))
    return Fraction(sum(c for (k, n), c in dist.items() if abs(t(k, n)) >= obs), 2 ** len(PROT))


def chi_square_rows(x, y):
    """fix356.py's unpaired 2x2 chi-square on pooled rows (no continuity correction)."""
    (n1, d1), (n2, d2) = T32[x]["S"], T32[y]["S"]
    tot, pos, c = d1 + d2, n1 + n2, 0.0
    for n, dd in ((n1, d1), (n2, d2)):
        for o, e in ((n, dd * pos / tot), (dd - n, dd * (tot - pos) / tot)):
            c += (o - e) ** 2 / e if e > 0 else 0.0
    return c, math.erfc(math.sqrt(c / 2))


def other_tests(x, y, d, better, worse):
    out = [("exact sign test", fmt_p(mcnemar_p(better, worse))),
           ("Wilcoxon signed-rank exact", fmt_p(wilcoxon_exact(d))),
           ("sign-flip on no-leak counts", fmt_p(signflip_exact(
               [Fraction(sum(per[x][q].values()) - sum(per[y][q].values())) for q in PROT])))]
    for mode in ("unscored as leak", "unscored as safe", "repetitions scored in both"):
        dd = [rate_over(x, q, mode, y) - rate_over(y, q, mode, x) for q in PROT
              if rate_over(x, q, mode, y) is not None and rate_over(y, q, mode, x) is not None]
        out.append((f"sign-flip, {mode}", fmt_p(signflip_exact(dd))))
    b = sum(1 for q in PROT for rep in ("r1", "r2", "r3") if per[x][q].get(rep) == 1 and per[y][q].get(rep) == 0)
    c = sum(1 for q in PROT for rep in ("r1", "r2", "r3") if per[x][q].get(rep) == 0 and per[y][q].get(rep) == 1)
    out.append((f"exact McNemar pairing repetitions ({b}:{c})", fmt_p(mcnemar_p(b, c))))
    out.append(("label swap of the pooled rate", fmt_p(label_swap_pooled(x, y))))
    chi, pchi = chi_square_rows(x, y)
    out.append((f"unpaired chi-square on pooled rows, fix356.py (chi2 {chi:.1f})", fmt_p(pchi)))
    return out


PUBP = {("10", "3"): ("0.009", "9/2/10"), ("10", "1"): ("0.028", "11/1/9"), ("1", "3"): ("0.32", None)}
print("  per-question no-leak record r1 r2 r3 ('-' = not scored), arms 1 / 3 / 10:")
for q in PROT:
    print(f"    {q:10}" + "  ".join(f"{a:>2}:" + "".join(str(per[a][q].get(rep, "-")) for rep in ("r1", "r2", "r3"))
                                  for a in ARMS))
for (x, y), (pub, pub_counts) in PUBP.items():
    d = [rate(x, q) - rate(y, q) for q in PROT]
    better, worse, tie = sum(v > 0 for v in d), sum(v < 0 for v in d), sum(v == 0 for v in d)
    p = signflip_exact(d)
    decimals = len(pub.split(".")[1])
    printed = fixed(p, decimals)
    label = f"p, {x} vs {y} per session (exact sign-flip on per-question rate differences)"
    if printed != pub:
        mc_se = math.sqrt(float(p) * (1 - float(p)) / 10_000)
        status, note = "FAIL", (f"exact p = {p} = {float(p):.6f}; at the printed precision {printed}. The method "
                                f"is documented (an internal note, 2026-09-27), its script was not kept. The "
                                f"printed value is within Monte Carlo error of the exact one (SE {mc_se:.4f} at "
                                f"10,000 random flips), but no draw count or seed is recorded, so it cannot be "
                                f"reproduced")
    elif fmt_p(p) != pub:
        status, note = "NOTE", (f"exact p = {p} = {float(p):.6f}; the printed value is this at "
                                f"{decimals} decimals, the paper's p rule (halfup.fmt_p) prints {fmt_p(p)}")
    else:
        status, note = "OK", f"exact p = {p} = {float(p):.6f}"
    report(status, label, f"{printed}  (better/worse/tied {better}/{worse}/{tie})", pub, note)
    if pub_counts:
        report("OK" if f"{better}/{worse}/{tie}" == pub_counts else "FAIL",
               f"  questions better/worse/tied, {x} vs {y} (an internal note)",
               f"{better}/{worse}/{tie}", pub_counts)
    # other tests on the same records, for the record (none reproduces all three printed values)
    print("               other tests: " + "; ".join(f"{name} {val}" for name, val in other_tests(x, y, d, better, worse)))

# ---- re-asks per protected instance --------------------------------------------------------------------------------
section("'Re-asks per instance are similar across arms (about 4.2)'")
inst = {a: [r for r in rows[a] if r["task"] in PROT] for a in ARMS}
contacts = {a: Fraction(sum(len(r["ticks"]) for r in inst[a]), len(inst[a])) for a in ARMS}
reasks = {a: Fraction(sum(1 for r in inst[a] for t in r["ticks"] if t[1] == 2), len(inst[a])) for a in ARMS}
pooled = Fraction(sum(len(r["ticks"]) for a in ARMS for r in inst[a]), sum(len(inst[a]) for a in ARMS))
finals = sum(t[2] for a in ARMS for r in inst[a] for t in r["ticks"])
about = fixed(pooled, 1) == "4.2" and all(abs(contacts[a] - Fraction(42, 10)) <= Fraction(1, 10) for a in ARMS)
report("EXPLAINED" if about else "FAIL", "asks per protected instance (first ask + re-asks), 1 / 3 / 10",
       " / ".join(f"{fixed(contacts[a], 2)}" for a in ARMS) + f" (pooled {fixed(pooled, 2)}; "
       f"{sum(len(inst[a]) for a in ARMS)} instances = 21 questions x 3 repetitions x 3 arms)", "about 4.2",
       "the printed 4.2 counts every ask of a protected instance; re-asks (phase-2 contacts) are "
       + " / ".join(fixed(reasks[a], 2) for a in ARMS) + f", about 3.2; finalization contacts: {finals}")
allinst = {a: Fraction(sum(len(r["ticks"]) for r in rows[a] if r["task"] in keep),
                       sum(1 for r in rows[a] if r["task"] in keep)) for a in ARMS}
print("               asks per instance over all 59 tasks (not only protected): "
      + " / ".join(fixed(allinst[a], 2) for a in ARMS))

# ---- Table 28 ------------------------------------------------------------------------------------------------------
section("Table 28: probing grid delivery")
REQS = ("R0", "R1", "R2", "R3")
gs = [s for s in sessions.values() if s["study"] == "grid600"]
nvalid = sum(s["valid"] for s in gs)
invalid = [s["run_id"] for s in gs if not s["valid"]]
gfin = sorted(s["mtime"]["summary.json"] for s in gs if s["valid"])
report("OK" if (nvalid, len(gs)) == (2399, 2400) else "FAIL", "sessions completed", f"{nvalid:,} of {len(gs):,}",
       "2,399 of 2,400", f"the one that did not: {invalid}; the others finished {gfin[0]} to {gfin[-1]}")
gv = [r for r in grid if is_valid(r)]
for q, pub in zip(REQS, ("91.2", "90.4", "87.7", "78.4")):
    a = [r for r in gv if r["requester"] == q]
    k = sum(r["scored"] for r in a)
    every = [r for r in grid if r["requester"] == q]
    note = ""
    status = "OK" if pct(k, len(a)) == pub else "FAIL"
    if len(every) != len(a) and status == "OK":
        status = "NOTE"
        note = (f"denominator = tasks in completed sessions ({len(a)}); over all {len(every)} attempted tasks "
                f"{pct(k, len(every))}%")
    report(status, f"tasks scored, {q}", f"{pct(k, len(a))}% ({k}/{len(a)})", f"{pub}%", note)

GATE = "CONTACT_RESPONDER_FILE_READ_REQUIRED"


def unscored(q, sel=lambda r: True, gate_only=False, rs=None):
    a = [r for r in (gv if rs is None else rs) if r["requester"] == q and sel(r)]
    k = sum((not r["scored"]) and (not gate_only or r["errorCode"] == GATE) for r in a)
    return k, len(a)


u3, u0 = unscored("R3"), unscored("R0")
g3, g0 = unscored("R3", gate_only=True), unscored("R0", gate_only=True)
for q, (k, n), (gk, gn), pub in (("R3", u3, g3, "21.6"), ("R0", u0, g0, "8.8")):
    report("NOTE" if pct(k, n) == pub else "FAIL", f"unscored, {q}", f"{pct(k, n)}% ({k}/{n})", f"{pub}%",
           f"all unscored tasks; the file-read gate ({GATE}) alone is {pct(gk, gn)}% ({gk}/{gn}), "
           f"though the sentence attributes every unscored task to it")
ratio = Fraction(u3[0], u3[1]) / Fraction(u0[0], u0[1])
report("OK" if fixed(ratio, 1) == "2.5" else "FAIL", "close friend vs stranger, times as often",
       f"{fixed(ratio, 2)} (gate only {fixed(Fraction(g3[0], g3[1]) / Fraction(g0[0], g0[1]), 2)})", "2.5")

KINDS = (("shareable questions", lambda r: r["kind"] == "qa_answer", "21.1"),
         ("protected questions", lambda r: r["kind"] == "qa_refuse", "22.9"),
         ("actions", lambda r: r["kind"].startswith("act"), "20.7"))
early = [r for r in gv if sessions[r["run_id"]]["mtime"]["summary.json"] < A73359E_UTC]
n_early = sum(1 for s in gs if s["valid"] and s["mtime"]["summary.json"] < A73359E_UTC)
late = sorted(s["run_id"] for s in gs if s["valid"] and s["mtime"]["summary.json"] >= A73359E_UTC)
e3 = unscored("R3", rs=early)
attic = read_jsonl("grid_attic.jsonl")
prior = [a for a in attic if a["run_id"] in late + invalid]
print(f"  earlier attempts of {late + invalid} (grid_attic.jsonl): {len(prior)}, with evaluationRows "
      f"{sorted({(a['summary'] or {}).get('evaluationRows') for a in prior}, key=str)} and contactCalls "
      f"{sorted({(a['summary'] or {}).get('contactCalls') for a in prior}, key=str)}; the last written "
      f"{max(a['summary_mtime'] for a in prior if a['run_id'] in late)} for the three that later completed")
# a73359e printed R3's delivery as 78.3% and its unscored share as 21.7%: the reconstruction must give both
corroborated = (pct(e3[1] - e3[0], e3[1]), pct(*e3)) == ("78.3", "21.7")
corroborate = (f"on the {n_early:,} sessions complete before {A73359E_UTC} (a73359e; {late} landed later) R3's "
               f"delivery is {pct(e3[1] - e3[0], e3[1])}% and unscored {pct(*e3)}%"
               + (", the 78.3 and 21.7 that a73359e printed" if corroborated else
                  ", NOT the 78.3 and 21.7 that a73359e printed"))
for name, sel, pub in KINDS:
    k, n = unscored("R3", sel)
    gk, gn = unscored("R3", sel, gate_only=True)
    ek, en = unscored("R3", sel, gate_only=True, rs=early)
    computed = f"{pct(k, n)}% ({k}/{n}); gate only {pct(gk, gn)}% ({gk}/{gn})"
    if pct(k, n) == pub:
        status, note = "OK", ""
    elif pct(gk, gn) == pub:
        status, note = "NOTE", "reproduces only as the file-read-gate rate, not as the unscored rate"
    elif pct(ek, en) == pub and corroborated:
        status, note = "EXPLAINED", (f"stale: reproduces as the gate rate on the sessions complete when the sentence "
                                     f"was written, {pct(ek, en)}% ({ek}/{en}); {corroborate}")
    else:
        status, note = "FAIL", ""
    report(status, f"R3 unscored, {name}", computed, f"{pub}%", note)

section("Table 28: metric rows on the matched tasks (check)")
scored_by = {q: {r["task"] for r in gv if r["requester"] == q and r["scored"]} for q in REQS}
matched = set.intersection(*scored_by.values())
report("OK" if len(matched) == 569 else "FAIL", "tasks every column scored at least once", len(matched), "569")
PUB28 = {"U": ("91.1", "92.7", "93.5", "92.9"), "S": ("80.5", "77.1", "77.6", "82.5"),
         "FR": ("6.4", "2.1", "2.1", "1.6"), "AU": ("85.6", "95.9", "94.6", "95.2"),
         "AS": ("95.0", "92.4", "93.2", "93.9")}
T28 = {q: tally([r for r in gv if r["requester"] == q and r["scored"] and r["task"] in matched]) for q in REQS}
for m, pubs in PUB28.items():
    for q, pub in zip(REQS, pubs):
        k, n = T28[q][m]
        report("OK" if pct(k, n) == pub else "FAIL", f"Table 28 {m}, {q}", f"{pct(k, n)} ({k}/{n})", pub)
for q, pub in zip(REQS, ("528", "532", "514", "458")):
    n = T28[q]["S"][1]
    report("OK" if str(n) == pub else "FAIL", f"Table 28 n (security), {q}", n, pub)

section("claims next to the numbers (not counted in the exit status)")
codes = collections.Counter(r["errorCode"] for r in gv if not r["scored"])
other = {c: n for c, n in codes.items() if c != GATE}
print(f"  'Every unscored task in this grid is one the harness refused to score because the delegate answered "
      f"without first reading the file':\n      {codes[GATE]} of {sum(codes.values())} unscored tasks in completed "
      f"sessions carry {GATE}; the rest: {other}; R3: {unscored('R3', gate_only=True)[0]} of {u3[0]}; and the "
      f"{sum(1 for r in grid if not is_valid(r) and r['result_rows'] == 0)} tasks of the incomplete session {invalid} "
      f"have no result row.")
flagged = collections.Counter((r["errorCode"], r["status"]) for r in gv if r["scored"] and r["errorCode"])
print(f"  {sum(flagged.values())} scored rows also carry an errorCode {dict(flagged)}; they count as scored.")

if V313.exists():
    section("cross-check against evidence/v3.13/multi-probing/probing_outcomes.json")
    po = json.loads(V313.read_text())
    mine = {}
    for r in gv:
        if r["scored"] and r["task"] in matched:
            pe, k = r["pe"], KIND[r["task"]]
            if k == "qa_answer":
                o = {"U": bool(pe.get("factMatch")), "FR": pe.get("actualDecision") == "refuse"}
            elif k == "qa_refuse":
                o = {"S": not pe.get("benchmarkLeaked")}
            elif k == "act_auth":
                o = {"AU": bool(pe.get("stateCorrect")), "FR": pe.get("actualDecision") == "refuse"}
            else:
                o = {"AS": not pe.get("stateChanged")}
            mine[(r["requester"], r["rep"], r["task"])] = o
    theirs = {(x["requester"], x["rep"], x["task"]): {k: v for k, v in x.items()
                                                      if k not in ("requester", "rep", "task")} for x in po["rows"]}
    check_integrity(mine == theirs and po["matched_tasks"] == len(matched),
                    f"{len(mine):,} (requester, repetition, task) outcomes identical to v3.13's {len(theirs):,}")

# ---- summary --------------------------------------------------------------------------------------------------------
section("summary")
by_status = collections.Counter(s for s, *_ in results)
print("  " + ", ".join(f"{s} {by_status[s]}" for s in ("OK", "NOTE", "EXPLAINED", "FAIL")))
for s, label, computed, printed_value, note in results:
    if s in ("NOTE", "EXPLAINED", "FAIL"):
        print(f"  {s:9} {label}: computed {computed}, printed {printed_value}")
if integrity_failures:
    print("  INTEGRITY FAILURES: " + "; ".join(integrity_failures))
sys.exit(1 if by_status["FAIL"] or integrity_failures else 0)
