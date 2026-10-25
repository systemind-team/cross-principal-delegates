#!/usr/bin/env python3
"""PAIR I grok-4.6 supplement: the analysis, fixed before the run.

  python3 analyze.py --grok DIR --grok-scan FILE [--grok-retry DIR --retry-list FILE] [--frozen DIR] [--out FILE]
  python3 analyze.py --dry-run luna [--frozen DIR] [--out FILE]

--grok is the offline rescore of the twelve grok cells (rescore.json + tasks/grok-d<k>-r<j>.tasks.jsonl, from
SharedEval's rescore-relationship-grid.ts --include-text --recover-quarantined-qa); --grok-scan is refusal_scan.mts
over those task files. --grok-retry is the same rescore (plus scan.json) of the <cell>-retry reruns of the
task-runs that Azure rate limiting killed (--retry-list, from retry_list.py); each rerun replaces its error row.
--dry-run puts one frozen model's rows for the planned tasks in grok's seat, to exercise
every path before the run (its grok-versus-itself contrasts must come out identical, p = 1).

Gates, before any number: the frozen inputs' digests; the per-row rules reproduce every numerator and denominator
of the 110 frozen cells (relationship-v2 strict and with recovery, category contract strict); the grok rescore uses
the same relationship labels, its per-row rules reproduce its own cells the same way, and every cell holds exactly
the planned tasks once.

Units and populations. A unit is a (task, requester) pair at one policy; rows are scored with recovery. Both label
sets are reported: relationship-v2 (the paper's gold) and the category contract (the run-time grading). Metrics are
in common.METRIC_NAMES; total leak adds refusals whose literal reply carries a gold fact to the decision leak.
  random : the 100 random tasks x 4 requesters. The unbiased population: grok's rates, its ladder, and grok against
           each PAIR I model on the same pairs (exact McNemar, paired by task).
  hard   : the 609 hard pairs, chosen on the three models' own failures, so their rates there are inflated by
           selection. The fair contrast is leave-one-out: for each model M, the pairs the other two models made
           hard (the same rule) are chosen without looking at M or grok, and M and grok are compared on them.
Primary tests (Holm within each family; everything else is descriptive with raw p):
  F1 grok's ladder on the random set, relationship-v2: D0->D1 and D1->D2, total leak and false refusal, R1-R3.
  F2 grok against each model at D2 on the random set, relationship-v2: total leak and false refusal, R1-R3.
  F3 leave-one-out on the hard set at D2, relationship-v2, pooled over requesters: total leak and false refusal.
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (DESIGN_DIR, FROZEN_DIR, FROZEN_SHA256, LABEL_SHA256, LABELS, METRIC_NAMES, METRICS, MODELS, NEW,
                    POLICIES, REQUESTERS, cell_id, check_frozen, hard_reasons, load_jsonl, mcnemar_exact, outcome,
                    rate_block, refusal_hits, scored, sha256_file, success_metric)

REPORT_KEYS = {"iu": "informationUtility", "fr": "falseRefusalRate", "leak": "leakRate", "as": "actionSafety",
               "au": "actionUtility"}
GATE_BLOCKS = (("relationship", "relationshipActive", False), ("relationship", "relationshipActiveWithRecovery", True),
               ("category", "category", False))
FAMILIES = (NEW,) + MODELS


def parse_cell(label):
    m = re.fullmatch(r"([A-Za-z0-9]+)-d(\d)-r(\d)", label)
    if not m:
        raise SystemExit(f"bad cell label {label}")
    return m.group(1), f"D{m.group(2)}", f"R{m.group(3)}"


def gate(rows, report_cells, hits, where):
    """Per-row rules must reproduce the rescore report's numerators and denominators for every cell."""
    by_cell = collections.defaultdict(list)
    for r in rows:
        by_cell[r["cell"]].append(r)
    if set(by_cell) != set(report_cells):
        raise SystemExit(f"{where}: task rows cover {sorted(set(by_cell) ^ set(report_cells))} differently from the report")
    bad = []
    for cid, rs in by_cell.items():
        for label, block, recovery in GATE_BLOCKS:
            for m, key in REPORT_KEYS.items():
                k = n = 0
                for r in rs:
                    if not scored(r, recovery):
                        continue
                    eligible, failed = outcome(r, label, m, (cid, r["taskId"]) in hits)
                    n += eligible
                    k += eligible and failed
                shown = n - k if success_metric(m) else k
                want = report_cells[cid][block][key]
                if [shown, n] != [want["numerator"], want["denominator"]]:
                    bad.append((cid, block, m, [shown, n], [want["numerator"], want["denominator"]]))
    if bad:
        raise SystemExit(f"{where}: per-row rules do not reproduce the report: {bad[:5]} ({len(bad)} in all)")
    print(f"gate: {where}: {len(by_cell)} cells reproduced (relationship strict and with recovery, category strict)")


class Data:
    def __init__(self):
        self.rows = {}   # (family, policy, requester) -> {taskId: row}
        self.hits = set()  # (family, policy, requester, taskId)

    def add(self, rows, hits):
        for r in rows:
            fam, pol, req = parse_cell(r["cell"])
            self.rows.setdefault((fam, pol, req), {})[r["taskId"]] = r
        for cell, t in hits:
            self.hits.add(parse_cell(cell) + (t,))

    def unit(self, fam, pol, req, t, label, metric):
        """(eligible, failed) or None when the task is not scored in that cell."""
        r = self.rows.get((fam, pol, req), {}).get(t)
        if r is None or not scored(r):
            return None
        e, f = outcome(r, label, metric, (fam, pol, req, t) in self.hits)
        return (e, f) if e else None

    def rate(self, fam, pol, req, tasks, label, metric):
        k = n = 0
        for t in tasks:
            u = self.unit(fam, pol, req, t, label, metric)
            if u:
                n += 1
                k += u[1]
        return rate_block(k, n, metric)

    def paired(self, a, b, units, label, metric):
        """a, b: (family, policy). units: [(task, requester)]. Exact McNemar on the units scored and eligible in both."""
        cnt = collections.Counter()
        for t, req in units:
            ua = self.unit(*a, req, t, label, metric)
            ub = self.unit(*b, req, t, label, metric)
            if ua and ub:
                cnt[(ua[1], ub[1])] += 1
        n = sum(cnt.values())
        fa = cnt[(True, False)] + cnt[(True, True)]
        fb = cnt[(False, True)] + cnt[(True, True)]
        out = {"n": n, "a_only": cnt[(True, False)], "b_only": cnt[(False, True)], "p": mcnemar_exact(cnt[(True, False)], cnt[(False, True)])}
        if n:
            sa, sb = (n - fa, n - fb) if success_metric(metric) else (fa, fb)
            out.update(a_pct=100 * sa / n, b_pct=100 * sb / n, delta_pp=100 * (sb - sa) / n)
        return out


def holm(tests):
    order = sorted(range(len(tests)), key=lambda i: tests[i]["p"])
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(tests) - rank) * tests[i]["p"]))
        tests[i]["p_holm"] = running
    return tests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", default=FROZEN_DIR)
    ap.add_argument("--grok")
    ap.add_argument("--grok-scan")
    ap.add_argument("--grok-retry")
    ap.add_argument("--retry-list")
    ap.add_argument("--dry-run", choices=MODELS)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(DESIGN_DIR), "grok_supplement.json"))
    args = ap.parse_args()
    if bool(args.dry_run) == bool(args.grok):
        raise SystemExit("give either --grok (with --grok-scan) or --dry-run")

    check_frozen(args.frozen)
    plan = json.load(open(os.path.join(DESIGN_DIR, "run_plan.json")))
    random_set = json.load(open(os.path.join(DESIGN_DIR, "random_set.json")))
    hard = load_jsonl(os.path.join(DESIGN_DIR, "hard_set.jsonl"))
    frozen_rows = load_jsonl(os.path.join(args.frozen, "tasks.jsonl"))
    frozen_hits = refusal_hits(json.load(open(os.path.join(args.frozen, "diag_scan.json"))))
    frozen_report = {}
    for name in ("rescore-openrouter-82.json", "rescore-azure-28.json"):
        rep = json.load(open(os.path.join(args.frozen, name)))
        if rep["relationshipLabelProvenance"]["sha256"] != LABEL_SHA256:
            raise SystemExit(f"{name}: relationship labels differ")
        frozen_report.update(rep["cells"])
    gate(frozen_rows, frozen_report, frozen_hits, "frozen grid")

    data = Data()
    data.add([r for r in frozen_rows if r["family"] in MODELS and r["policy"] in POLICIES],
             {h for h in frozen_hits if parse_cell(h[0])[0] in MODELS})
    meta = {"design": {f: sha256_file(os.path.join(DESIGN_DIR, f)) for f in ("hard_set.jsonl", "random_set.json", "run_plan.json")},
            "frozenInputs": FROZEN_SHA256, "metrics": METRIC_NAMES}
    if args.dry_run:
        src = args.dry_run
        new_rows, new_hits = [], set()
        for cid, c in plan["cells"].items():
            _, pol, req = parse_cell(cid)
            have = data.rows[(src, pol, req)]
            for t in c["ids"]:
                new_rows.append({**have[t], "cell": cid})
                if (src, pol, req, t) in data.hits:
                    new_hits.add((cid, t))
        meta["mode"] = f"dry run: {src} rows in grok's seat"
        delivery = None
    else:
        rep = json.load(open(os.path.join(args.grok, "rescore.json")))
        if rep["relationshipLabelProvenance"]["sha256"] != LABEL_SHA256:
            raise SystemExit("grok rescore: relationship labels differ from the frozen grid's")
        new_rows = []
        for cid in plan["cells"]:
            for r in load_jsonl(os.path.join(args.grok, "tasks", f"{cid}.tasks.jsonl")):
                new_rows.append({**r, "cell": cid})
        new_hits = refusal_hits(json.load(open(args.grok_scan)))
        gate(new_rows, rep["cells"], new_hits, "grok cells")
        meta["mode"] = "grok-4.6 run"
        meta["grokInputs"] = {"rescore.json": sha256_file(os.path.join(args.grok, "rescore.json")),
                              "scan": sha256_file(args.grok_scan)}
        delivery = {cid: rep["cells"][cid]["taskCounts"] for cid in plan["cells"]}
        if args.grok_retry:
            # task-runs that Azure rate limiting killed (retry_list.py) ran again with the same config; their
            # rerun replaces the error row, after the rerun's own rescore passes the same gate
            listed = json.load(open(args.retry_list))["cells"]
            rrep = json.load(open(os.path.join(args.grok_retry, "rescore.json")))
            if rrep["relationshipLabelProvenance"]["sha256"] != LABEL_SHA256:
                raise SystemExit("grok retry rescore: relationship labels differ from the frozen grid's")
            retry_rows = []
            for cid in listed:
                for r in load_jsonl(os.path.join(args.grok_retry, "tasks", f"{cid}-retry.tasks.jsonl")):
                    retry_rows.append({**r, "cell": f"{cid}-retry"})
            retry_hits = refusal_hits(json.load(open(os.path.join(args.grok_retry, "scan.json"))))
            gate(retry_rows, rrep["cells"], retry_hits, "grok retry cells")
            replace = {(cid, t["taskId"]) for cid, ts in listed.items() for t in ts}
            if any((r["cell"], r["taskId"]) in replace and r["status"] != "error" for r in new_rows):
                raise SystemExit("a listed task-run did not end in error in the plan run")
            if {(r["cell"][: -len("-retry")], r["taskId"]) for r in retry_rows} != replace or len(retry_rows) != len(replace):
                raise SystemExit("retry rows differ from the retry list")
            new_rows = [r for r in new_rows if (r["cell"], r["taskId"]) not in replace] \
                + [{**r, "cell": r["cell"][: -len("-retry")]} for r in retry_rows]
            new_hits = {h for h in new_hits if h not in replace} | {(c[: -len("-retry")], t) for c, t in retry_hits}
            meta["mode"] += f"; {len(replace)} rate-limited task-runs replaced by their rerun"
            meta["grokInputs"].update({"retry_list": sha256_file(args.retry_list),
                                       "retry rescore.json": sha256_file(os.path.join(args.grok_retry, "rescore.json")),
                                       "retry scan": sha256_file(os.path.join(args.grok_retry, "scan.json"))})
            delivery = {"plan": delivery, "retry": {c: rrep["cells"][c]["taskCounts"] for c in rrep["cells"]}}
    for cid, c in plan["cells"].items():
        got = [r["taskId"] for r in new_rows if r["cell"] == cid]
        if sorted(got) != sorted(c["ids"]) or len(got) != len(set(got)):
            raise SystemExit(f"{cid}: tasks differ from the run plan")
    data.add(new_rows, new_hits)

    rand = random_set["tasks"]
    hard_by_req = collections.defaultdict(list)
    for h in hard:
        hard_by_req[h["requester"]].append(h["taskId"])
    loo = {}
    model_rows = [r for r in frozen_rows if r["family"] in MODELS]
    for m in MODELS:
        others = [r for r in model_rows if r["family"] != m]
        loo[m] = sorted(hard_reasons(others, frozen_hits))

    out = {"meta": meta, "delivery": delivery, "random": {}, "hard": {}, "primary": {}}
    for label in LABELS:
        R = out["random"][label] = {"rates": {}, "ladder": [], "vsModels": [], "fullGrid": {}}
        for req in REQUESTERS:
            for pol in POLICIES:
                for fam in FAMILIES:
                    R["rates"][f"{fam}-{pol}-{req}"] = {m: data.rate(fam, pol, req, rand, label, m) for m in METRICS}
                for fam in MODELS:
                    R["fullGrid"][f"{fam}-{pol}-{req}"] = {
                        m: data.rate(fam, pol, req, list(data.rows[(fam, pol, req)]), label, m) for m in METRICS}
            units = [(t, req) for t in rand]
            for a, b in (("D0", "D1"), ("D1", "D2"), ("D0", "D2")):
                for m in METRICS:
                    R["ladder"].append({"requester": req, "from": a, "to": b, "metric": m,
                                        **data.paired((NEW, a), (NEW, b), units, label, m)})
            for pol in POLICIES:
                for fam in MODELS:
                    for m in METRICS:
                        R["vsModels"].append({"requester": req, "policy": pol, "model": fam, "metric": m,
                                              **data.paired((fam, pol), (NEW, pol), units, label, m)})
        H = out["hard"][label] = {"rates": {}, "leaveOneOut": []}
        for req in REQUESTERS + ("all",):
            units = [(h["taskId"], h["requester"]) for h in hard if req in ("all", h["requester"])]
            for pol in POLICIES:
                for fam in FAMILIES:
                    for m in ("total_leak", "leak", "fr"):
                        k = n = 0
                        for t, q in units:
                            u = data.unit(fam, pol, q, t, label, m)
                            if u:
                                n += 1
                                k += u[1]
                        H["rates"].setdefault(f"{fam}-{pol}-{req}", {})[m] = rate_block(k, n, m)
                for fam in MODELS:
                    sub = [u for u in loo[fam] if req in ("all", u[1])]
                    for m in ("total_leak", "leak", "fr"):
                        H["leaveOneOut"].append({"requester": req, "policy": pol, "model": fam, "pairs": len(sub), "metric": m,
                                                 **data.paired((fam, pol), (NEW, pol), sub, label, m)})

    rel = "relationship"
    out["primary"]["F1"] = holm([t for t in out["random"][rel]["ladder"]
                                 if t["metric"] in ("total_leak", "fr") and t["requester"] != "R0"
                                 and (t["from"], t["to"]) in (("D0", "D1"), ("D1", "D2"))])
    out["primary"]["F2"] = holm([t for t in out["random"][rel]["vsModels"]
                                 if t["metric"] in ("total_leak", "fr") and t["requester"] != "R0" and t["policy"] == "D2"])
    out["primary"]["F3"] = holm([t for t in out["hard"][rel]["leaveOneOut"]
                                 if t["metric"] in ("total_leak", "fr") and t["requester"] == "all" and t["policy"] == "D2"])
    json.dump(out, open(args.out, "w"), indent=1)

    def pct(b):
        return "  -  " if b["pct"] is None else f"{b['pct']:5.1f}"
    print(f"\n{meta['mode']}; random set, relationship-v2 (n = protected / entitled units)")
    for req in REQUESTERS:
        for pol in POLICIES:
            line = [f"{req} {pol}"]
            for fam in FAMILIES:
                rb = out["random"][rel]["rates"][f"{fam}-{pol}-{req}"]
                line.append(f"{fam:5s} TL {pct(rb['total_leak'])} FR {pct(rb['fr'])}")
            n = out["random"][rel]["rates"][f"{NEW}-{pol}-{req}"]
            print(" | ".join(line) + f"  (n {n['total_leak']['n']}/{n['fr']['n']})")
    for fam_key, tests in out["primary"].items():
        print(f"\n{fam_key}:")
        for t in tests:
            what = (f"{t['requester']} {t.get('from', t.get('policy'))}->{t.get('to', '')}" if "from" in t
                    else f"{t['requester']} {t['policy']} {t['model']} vs grok")
            d = "" if not t["n"] else f"{t['a_pct']:5.1f} -> {t['b_pct']:5.1f}"
            print(f"  {what:24s} {t['metric']:10s} n {t['n']:4d}  {d:16s} p {t['p']:.3g}  holm {t['p_holm']:.3g}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
