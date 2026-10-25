#!/usr/bin/env python3
"""PAIR I under total disclosure (total leak), per model, requester and rung, under both label sets.

Input: evidence/v3.14/total-disclosure/pair1_cells.json (scripts/p11/pair1_td.py). Output:
evidence/v3.14/total-disclosure/pair1_summary.json and a printed view of Table 3 (R1-R3 x D0-D2 x three models)
and of the crossed table (close friend and colleague, both label sets). Rates are rounded half away from zero
from the counts. Leak = total disclosure (decision + refusal channel); its two parts are given separately.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import pct  # noqa: E402

C = json.loads((ROOT / "evidence/v3.14/total-disclosure/pair1_cells.json").read_text())["cells"]
MODELS = (("ds41", "DS-4.1"), ("glm", "GLM-F"), ("luna", "GPT"))
out = {}
for fam, _ in MODELS:
    for r in ("R0", "R1", "R2", "R3"):
        for p in ("D0", "D1", "D2", "D3", "D4", "D5", "D6"):
            cell = f"{fam}-{p.lower()}-{r.lower()}"
            for ls in ("relationship", "category"):
                a = C[cell][ls]
                out[f"{cell}/{ls}"] = {
                    "n_protected": a.get("n", 0), "DL": a.get("DL", 0), "RC": a.get("RC", 0), "TD": a.get("TD", 0),
                    "n_entitled": a.get("n_entitled", 0), "FR": a.get("FR", 0),
                    "TD_pct": pct(a["TD"], a["n"]) if a.get("n") else None,
                    "DL_pct": pct(a["DL"], a["n"]) if a.get("n") else None,
                    "RC_pct": pct(a["RC"], a["n"]) if a.get("n") else None,
                    "FR_pct": pct(a["FR"], a["n_entitled"]) if a.get("n_entitled") else None}
(ROOT / "evidence/v3.14/total-disclosure/pair1_summary.json").write_text(json.dumps(out, indent=1) + "\n")


def show(ls, reqs, pols=("D0", "D1", "D2")):
    for r in reqs:
        for p in pols:
            cells = []
            for fam, name in MODELS:
                x = out[f"{fam}-{p.lower()}-{r.lower()}/{ls}"]
                cells.append(f"{name} TD {x['TD']}/{x['n_protected']}={x['TD_pct']} (DL {x['DL']} RC {x['RC']}) "
                             f"FR {x['FR']}/{x['n_entitled']}={x['FR_pct']}")
            print(f"  {r} {p}: " + " | ".join(cells))


print("Relationship labels (Table 3 population, with recovery):")
show("relationship", ("R0", "R1", "R2", "R3"))
print("Category labels (with recovery):")
show("category", ("R1", "R3"))
