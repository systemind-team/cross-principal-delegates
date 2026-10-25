import json, os, collections, math
base = "<vm>/runs/t3simple"; os.chdir(base)
src = open("analyze_s4.py").read(); cut = src.index('report = {"provenance"'); g = {}; exec(src[:cut], g)
cell_items = g["cell_items"]; BUILDS = g["BUILDS"]; POLS = g["POLS"]; REQS = g["REQS"]; kindof = g["kindof"]
cls = {tuple(k.split("|")): v for k, v in json.load(open("/tmp/s4_rescore_blocks.json"))["cls"].items()}
t3 = json.load(open("table3s.json"))
def mcnemar(x, y):
    b = sum(1 for u, v in zip(x, y) if u and not v); c = sum(1 for u, v in zip(x, y) if v and not u); n = b + c
    if n == 0: return {"b": 0, "c": 0, "p": 1.0}
    k = min(b, c); return {"b": b, "c": c, "p": min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)}
rep = {}
for b in BUILDS:
    for r in REQS:
        keep = set(cell_items(b, "D0", r)) & set(cell_items(b, "D1", r)) & set(cell_items(b, "D2", r))
        prot = sorted((gr, t) for (gr, t) in keep if kindof(t) == "qa_refuse")
        dec = {p: [cls.get((b, p, r, gr, t)) == "decision" for gr, t in prot] for p in POLS}
        rch = {p: [cls.get((b, p, r, gr, t)) == "refusal-channel" for gr, t in prot] for p in POLS}
        n = len(prot)
        rep["%s-%s" % (b, r)] = {
            "n": n,
            "decision_leak": {p: (100.0 * sum(dec[p]) / n if n else None) for p in POLS},
            "refusal_channel": {p: (100.0 * sum(rch[p]) / n if n else None) for p in POLS},
            "counts": {p: [sum(dec[p]), sum(rch[p])] for p in POLS},
            "p_D0D2": mcnemar(dec["D0"], dec["D2"]), "p_D1D2": mcnemar(dec["D1"], dec["D2"]),
            "orig_leak": {p: t3["blocks"]["%s-%s" % (b, r)]["rates"][p].get("Leak", {}).get("value") for p in POLS},
        }
json.dump(rep, open("/tmp/s4_rescore_table.json", "w"), indent=1)
for k, v in rep.items():
    print(k, "n", v["n"], "dec", {p: round(x, 1) for p, x in v["decision_leak"].items()}, "rc", {p: round(x, 1) for p, x in v["refusal_channel"].items()},
          "p02 %.2g (%d:%d)" % (v["p_D0D2"]["p"], v["p_D0D2"]["b"], v["p_D0D2"]["c"]), "p12 %.2g (%d:%d)" % (v["p_D1D2"]["p"], v["p_D1D2"]["b"], v["p_D1D2"]["c"]))
