#!/usr/bin/env python3
"""Size check of the parametric-bootstrap likelihood-ratio test (design.pb_lrt).

simulate.py showed the chi-square reference over-rejecting for the false-refusal tests, where events are
rare. This script repeats the null scenario (b = 0) for every test with the bootstrap p (B per replicate)
and records the rejection rate at 0.05 for both references. Same design and data-generating model as
simulate.py. Output: evidence/v3.14/p13-simulation/results_pb.json
Usage: simulate_pb.py <replicates> <B> [test names, e.g. D1-FR D2-FR]
"""
import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p13"))
import design  # noqa: E402
import simulate  # noqa: E402


def main():
    R, B = int(sys.argv[1]), int(sys.argv[2])
    rows = simulate.base_rows()
    rng = np.random.default_rng(11)
    out, t0 = {}, time.time()
    only = set(sys.argv[3:])
    for policy, outcome in simulate.TESTS:
        name = f"{policy}-{outcome}"
        if only and name not in only:
            continue
        rej_pb, rej_chi, n = 0, 0, 0
        for i in range(R):
            sub = simulate.simulate(rows, policy, outcome, 0.0, rng)
            f = design.fit_test(sub, policy, ci=False, pb=B, seed=1000 + i)
            if not f["estimable"]:
                continue
            n += 1
            rej_pb += f["p"] < 0.05
            rej_chi += f["p_chi2"] < 0.05
        out[name] = {"replicates": R, "estimable": n, "B": B, "reject_pb": rej_pb / n if n else None,
                     "reject_chi2": rej_chi / n if n else None}
        print(name, out[name], f"({time.time() - t0:.0f}s)", flush=True)
    dst = ROOT / "evidence/v3.14/p13-simulation/results_pb.json"
    dst.write_text(json.dumps({"scenario": "b = 0 (null)", "seed": 11, "results": out}, indent=1) + "\n")
    print("wrote", dst.relative_to(ROOT))


if __name__ == "__main__":
    main()
