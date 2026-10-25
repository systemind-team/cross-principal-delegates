#!/usr/bin/env python3
"""Decision leak with every task a content-filter block touched (any rung) removed from its block."""
import json, os, math, collections
L = "<vm>/runs/t3simple"; os.chdir(L)
src = open("analyze_s4.py").read(); cut = src.index('report = {"provenance"'); g = {}; exec(src[:cut], g)
cell_items, BUILDS, POLS, REQS, kindof = g["cell_items"], g["BUILDS"], g["POLS"], g["REQS"], g["kindof"]
cls = {tuple(k.split("|")): v for k, v in json.load(open("/tmp/s4_rescore_blocks.json"))["cls"].items()}
fl = json.load(open("filter_loss.json"))
touched = {(b, r, gr, t) for b, p, r, gr, t in fl["touched"]}
def mcnemar(x, y):
    b = sum(1 for u, v in zip(x, y) if u and not v); c = sum(1 for u, v in zip(x, y) if v and not u); n = b + c
    if n == 0: return (1.0, 0, 0)
    k = min(b, c); return (min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n), b, c)
res = {}
for b in BUILDS:
    for r in REQS:
        keep = set(cell_items(b, "D0", r)) & set(cell_items(b, "D1", r)) & set(cell_items(b, "D2", r))
        prot_all = sorted((gr, t) for (gr, t) in keep if kindof(t) == "qa_refuse")
        prot = [(gr, t) for gr, t in prot_all if (b, r, gr, t) not in touched]
        dec = {p: [cls.get((b, p, r, gr, t)) == "decision" for gr, t in prot] for p in POLS}
        n = len(prot)
        res[f"{b}-{r}"] = {"n_all": len(prot_all), "n_clean": n,
                           "decision_leak": {p: (round(100.0 * sum(dec[p]) / n, 1) if n else None) for p in POLS},
                           "p_D0D2": mcnemar(dec["D0"], dec["D2"]), "p_D1D2": mcnemar(dec["D1"], dec["D2"])}
        v = res[f"{b}-{r}"]
        print(f"{b}-{r}: prot {v['n_all']} -> untouched {n} | dec {v['decision_leak']} | D0->D2 p={v['p_D0D2'][0]:.2g} ({v['p_D0D2'][1]}:{v['p_D0D2'][2]}) | D1->D2 p={v['p_D1D2'][0]:.2g} ({v['p_D1D2'][1]}:{v['p_D1D2'][2]})")
json.dump(res, open("/tmp/s4_sensitivity.json", "w"), indent=1)
