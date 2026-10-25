#!/usr/bin/env python3
"""Section 7's false-refusal scenarios rerun with the fixed fitting code (PREREGISTRATION section 8, correction row;
approved 2026-10-05). Local CPU only.

The simulated data sets are the original ones: the random generator is consumed in exactly the order of the original
scripts, and only the fits change.
  chi2  simulate.py 300 150 100 (seed 7): for b = 0, 1, 2 and each test in simulate.TESTS, R data sets (300, 150, 150).
        The leak data sets are generated to keep the generator aligned but not refitted (the old and the fixed code
        agree on every leak data set, check_modes_fix.py). Each false-refusal data set is fitted with the fixed code
        (design.fit_test, profile interval on the first 100 at b > 0) and, as a check that the data sets are the
        original ones, with the old code (commit 56f4bd7), whose rejection rate and mean and SD of the estimate must
        reproduce the withdrawn numbers in results.json.
  pb    simulate_pb.py 100 99 D1-FR D2-FR (seed 11, bootstrap seed 1000 + i): the bootstrap size check, fixed code;
        the old code's chi-square rejection on the same data sets must reproduce results_pb.json's reject_chi2.

Usage: simulate_fr_rerun.py chi2|pb <path to the old glmm.py>
    git show 56f4bd7:scripts/p13/glmm.py > /tmp/glmm_old.py
Outputs: evidence/v3.14/p13-simulation/results_fr_rerun.json, results_pb_rerun.json
"""
import importlib.util
import json
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.stats import chi2

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p13"))
sys.path.insert(0, str(ROOT / "scripts" / "coding"))
import design  # noqa: E402
import simulate  # noqa: E402

OUT = ROOT / "evidence/v3.14/p13-simulation"
OLD = None


def old_module(path):
    global OLD
    if OLD is None:
        spec = importlib.util.spec_from_file_location("glmm_old", path)
        OLD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(OLD)
    return OLD


def old_fit(sub, policy, path):
    """The original fit_test's chi-square path with the old glmm (estimability and cell dropping as in design)."""
    st = design.strata(sub, policy)
    if st.get(0, 0) < design.MIN_CELLS or st.get(1, 0) < design.MIN_CELLS:
        return None
    d, _, _ = design.design(sub, policy)
    k = d.X.shape[1] - 1
    if d.X[:, k].sum() in (0, len(d.y)):
        return None
    g = old_module(path)
    dd = g.Data(d.X, d.y, d.g, d.names)       # d.X, d.y and d.g are already in cluster order
    f1 = g.fit(dd)
    f0 = g.fit(dd, fixed={k: 0.0}, start=f1)
    stat = max(0.0, 2 * (f1["loglik"] - f0["loglik"]))
    return {"p": float(chi2.sf(stat, 1)), "beta": float(f1["theta"][k]),
            "converged": bool(f1["converged"] and f0["converged"])}


def job_chi2(job):
    key, sub, policy, want_ci, path = job
    f = design.fit_test(sub, policy, ci=want_ci)
    new = None if not f["estimable"] else {"p": f["p"], "beta": f["beta"], "converged": f["converged"],
                                          "refit": f["full_refitted_from_null"],
                                          "ci": f.get("profile_ci")}
    return key, new, old_fit(sub, policy, path)


def job_pb(job):
    key, sub, policy, i, B, path = job
    f = design.fit_test(sub, policy, ci=False, pb=B, seed=1000 + i)
    new = None if not f["estimable"] else {"p_pb": f["p"], "p_chi2": f["p_chi2"], "converged": f["converged"],
                                          "pb_diagnostics": f.get("pb_diagnostics")}
    return key, new, old_fit(sub, policy, path)


def run_jobs(ex, jobs, fn, sink):
    for key, new, old in ex.map(fn, jobs):
        sink[key] = (new, old)


def summarise(new, b, ci_n):
    est = [x for x in new if x is not None]
    ps = np.array([x["p"] for x in est])
    betas = [x["beta"] for x in est]
    cov = [x for x in est if x.get("ci") is not None]      # the estimable data sets among the first ci_n at b > 0
    cover = sum(x["ci"][0] <= b <= x["ci"][1] for x in cov)
    return {"estimable": len(est), "reject_at_0.05": float(np.mean(ps < 0.05)) if est else None,
            "mean_beta": float(np.mean(betas)) if est else None,
            "sd_beta": float(np.std(betas, ddof=1)) if len(est) > 1 else None,
            "profile_ci_coverage": (cover / len(cov)) if cov else None, "ci_replicates": len(cov),
            "fits_not_converged": sum(not x["converged"] for x in est),
            "full_refitted_from_null": sum(bool(x["refit"]) for x in est)}


def mode_chi2(path, workers):
    reps = {0.0: 300, 1.0: 150, 2.0: 150}
    ci_reps = 100
    rows = simulate.base_rows()
    rng = np.random.default_rng(7)
    sink, pending, t0 = {}, [], time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for b, R in reps.items():
            for policy, outcome in simulate.TESTS:
                for i in range(R):
                    sub = simulate.simulate(rows, policy, outcome, b, rng)   # consumed in the original order
                    if outcome != "FR":
                        continue
                    pending.append(((b, f"{policy}-{outcome}", i), sub, policy, b > 0 and i < ci_reps, path))
                    if len(pending) >= 4 * workers:
                        run_jobs(ex, pending, job_chi2, sink)
                        pending = []
                print(f"b={b} {policy}-{outcome} generated ({time.time() - t0:.0f}s)", flush=True)
        run_jobs(ex, pending, job_chi2, sink)
    old_ref = json.loads((OUT / "results.json").read_text())["scenarios"]
    out = {"source": "scripts/p13/simulate_fr_rerun.py chi2 (the data sets of simulate.py 300 150 100, seed 7)",
           "fitting_code": "fixed (glmm._modes damped Newton, PREREGISTRATION section 8)", "scenarios": {},
           "old_code_reproduction": {}}
    for b, R in reps.items():
        for t in ("D1-FR", "D2-FR"):
            new = [sink[(b, t, i)][0] for i in range(R)]
            old = [sink[(b, t, i)][1] for i in range(R)]
            out["scenarios"][f"b={b}/{t}"] = {"replicates": R, **summarise(new, b, ci_reps)}
            est = [x for x in old if x is not None]
            ref = old_ref[f"b={b}/{t}"]
            rep = {"reject_at_0.05": float(np.mean([x["p"] < 0.05 for x in est])),
                   "mean_beta": float(np.mean([x["beta"] for x in est])),
                   "sd_beta": float(np.std([x["beta"] for x in est], ddof=1)),
                   "fits_not_converged": sum(not x["converged"] for x in est)}
            rep["reproduces_withdrawn_numbers"] = (len(est) == ref["estimable"]
                                                   and abs(rep["reject_at_0.05"] - ref["reject_at_0.05"]) < 1e-12
                                                   and abs(rep["mean_beta"] - ref["mean_beta"]) < 1e-6
                                                   and abs(rep["sd_beta"] - ref["sd_beta"]) < 1e-6)
            out["old_code_reproduction"][f"b={b}/{t}"] = rep
            print(f"b={b} {t}: new {out['scenarios'][f'b={b}/{t}']} | old reproduces: {rep['reproduces_withdrawn_numbers']}",
                  flush=True)
    (OUT / "results_fr_rerun.json").write_text(json.dumps(out, indent=1) + "\n")
    print("wrote", OUT / "results_fr_rerun.json")


def mode_pb(path, workers, R=100, B=99):
    rows = simulate.base_rows()
    rng = np.random.default_rng(11)
    sink, pending = {}, []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for policy, outcome in simulate.TESTS:
            if outcome != "FR":
                continue                       # simulate_pb.py skipped these without drawing
            for i in range(R):
                sub = simulate.simulate(rows, policy, outcome, 0.0, rng)
                pending.append(((f"{policy}-{outcome}", i), sub, policy, i, B, path))
                if len(pending) >= 2 * workers:
                    run_jobs(ex, pending, job_pb, sink)
                    pending = []
        run_jobs(ex, pending, job_pb, sink)
    old_ref = json.loads((OUT / "results_pb.json").read_text())["results"]
    out = {"source": "scripts/p13/simulate_fr_rerun.py pb (the data sets of simulate_pb.py 100 99 D1-FR D2-FR, seed 11)",
           "fitting_code": "fixed", "scenario": "b = 0 (null)", "results": {}}
    for t in ("D1-FR", "D2-FR"):
        new = [sink[(t, i)][0] for i in range(R)]
        old = [sink[(t, i)][1] for i in range(R)]
        est = [x for x in new if x is not None]
        oest = [x for x in old if x is not None]
        old_chi = float(np.mean([x["p"] < 0.05 for x in oest]))
        out["results"][t] = {"replicates": R, "estimable": len(est), "B": B,
                             "reject_pb": float(np.mean([x["p_pb"] < 0.05 for x in est])),
                             "reject_chi2": float(np.mean([x["p_chi2"] < 0.05 for x in est])),
                             "fits_not_converged": sum(not x["converged"] for x in est),
                             "bootstrap_replicates_not_converged": sum(x["pb_diagnostics"]["not_converged"] for x in est),
                             "bootstrap_full_refitted_from_null": sum(x["pb_diagnostics"]["full_refitted_from_null"] for x in est),
                             "old_code_reject_chi2": old_chi,
                             "old_code_reproduces_withdrawn_reject_chi2": abs(old_chi - old_ref[t]["reject_chi2"]) < 1e-12}
        print(t, out["results"][t], flush=True)
    (OUT / "results_pb_rerun.json").write_text(json.dumps(out, indent=1) + "\n")
    print("wrote", OUT / "results_pb_rerun.json")


if __name__ == "__main__":
    workers = int(os.environ.get("P13_WORKERS", "8"))
    {"chi2": mode_chi2, "pb": mode_pb}[sys.argv[1]](sys.argv[2], workers)
