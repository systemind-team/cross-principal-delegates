#!/usr/bin/env python3
"""What the label variants change, and the abstract-survival rule (PREREGISTRATION section 6).

Reads evidence/v3.14/labels/applied_<variant>.json (scripts/p14/apply_variants.py) for original, S1, S2, S3,
S3-bound, S4, S5, S6, and the frozen PAIR I rows for the close friend's personal questions (the "131 to 48"
sentence, category-graded). Writes evidence/v3.14/labels/survival.json:
  - the PAIR I family (Holm over 48, total leak): significant tests per variant and the tests whose verdict or
    direction changes against the original;
  - the stranger's D0->D1 test per model; the friend's protected work questions leaked at D0 and D1;
  - Table 30 (the header comparison), pooled and per requester: total leak, FR, AS with exact McNemar;
  - the abstract claims that rest on the relationship labels, each with its test under S3 and S4, and the rule's
    verdict: a claim stays only if its direction holds and its test stays significant under S3 and S4; a claim
    that fails only under S1, S2, S5 or S6 moves to the body with that qualifier.
Usage: survival.py
"""
import collections
import json
import lzma
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
LAB = ROOT / "evidence/v3.14/labels"
VARIANTS = ("original", "S1", "S2", "S3", "S3-bound", "S4", "S5", "S6")


def load(v):
    p = LAB / f"applied_{v}.json"
    return json.loads(p.read_text()) if p.exists() else None


def main():
    A = {v: load(v) for v in VARIANTS}
    A = {v: a for v, a in A.items() if a}
    orig = A["original"]["pair1"]["tests"]
    fam = [k for k, t in orig.items() if "holm" in t]
    out = {"family": {}, "stranger": {}, "friend_work": {}, "identity": {}, "claims": {}}
    for v, a in A.items():
        t = a["pair1"]["tests"]
        sig = {k for k in fam if k in t and t[k].get("holm", 1) < 0.05}
        flips = []
        for k in fam:
            if k not in t:
                flips.append({"test": k, "change": "not estimable"})
                continue
            o, n = orig[k], t[k]
            od = o["improved_worsened"][0] - o["improved_worsened"][1]
            nd = n["improved_worsened"][0] - n["improved_worsened"][1]
            if (o.get("holm", 1) < 0.05) != (n.get("holm", 1) < 0.05) or (od > 0) != (nd > 0) and od != 0 and nd != 0:
                flips.append({"test": k, "original": {"iw": o["improved_worsened"], "holm": o.get("holm")},
                              "variant": {"iw": n["improved_worsened"], "holm": n.get("holm")}})
        out["family"][v] = {"size": a["pair1"]["family_size"], "significant": len(sig), "changes_vs_original": flips}
        out["stranger"][v] = {f: t.get(f"{f}/R0/D0->D1/TD") for f in ("ds41", "glm", "luna")}
        out["friend_work"][v] = a["pair1"]["friend_work"]
        out["identity"][v] = a["identity"]
    # the abstract claim on PAIR II's header comparison (relationship labels): the header cuts false refusal
    claims = {}
    for v in ("original", "S3", "S4", "S1", "S2", "S5", "S6", "S3-bound"):
        if v not in A:
            continue
        fr = A[v]["identity"]["pooled"]["FR"]
        td = A[v]["identity"]["pooled"]["TD"]
        claims.setdefault("header cuts false refusal (abstract)", {})[v] = {
            "without": f"{fr['without']}/{fr['n']}", "with": f"{fr['with']}/{fr['n']}",
            "discordant": [fr["only_without"], fr["only_with"]], "p": fr["p"],
            "holds": fr["only_without"] > fr["only_with"] and fr["p"] < 0.05}
        claims.setdefault("header cuts the total leak (body)", {})[v] = {
            "without": f"{td['without']}/{td['n']}", "with": f"{td['with']}/{td['n']}",
            "discordant": [td["only_without"], td["only_with"]], "p": td["p"],
            "holds": td["only_without"] > td["only_with"] and td["p"] < 0.05}
    for name, per in claims.items():
        primary = all(per[v]["holds"] for v in ("S3", "S4") if v in per)
        others = [v for v in ("S1", "S2", "S5", "S6") if v in per and not per[v]["holds"]]
        per["verdict"] = ("stays" if primary and not others else
                          f"moves to the body, qualified by {', '.join(others)}" if primary else "fails")
    out["claims"] = claims
    # the "131 to 48" sentence: the close friend's category-protected questions (personal and sensitive work),
    # DeepSeek V4.1, D0 vs D1; category-graded, so no relationship-label variant moves it
    cnt = collections.Counter()
    for l in lzma.open(ROOT / "evidence/v3.14/total-disclosure/pair1_tasks.jsonl.xz", "rt"):
        o = json.loads(l)
        if o["family"] == "ds41" and o["requester"] == "R3" and o["policy"] in ("D0", "D1") and o["kind"] == "question" \
                and o["scored"] and o["cat"] == "protect":   # all category-protected questions: personal and sensitive work
            cnt[(o["policy"], "n")] += 1
            cnt[(o["policy"], "DL")] += o["decision_leak"]
            cnt[(o["policy"], "TL")] += o["total_disclosure"]
    out["friend_category_protected_ds41"] = {g: {"n": cnt[(g, "n")], "decision_leak": cnt[(g, "DL")], "total_leak": cnt[(g, "TL")]}
                                   for g in ("D0", "D1")}
    (LAB / "survival.json").write_text(json.dumps(out, indent=1) + "\n")
    for v, f in out["family"].items():
        print(f"{v:9s} family significant {f['significant']}/{f['size']}; changes vs original: {len(f['changes_vs_original'])}")
    for name, per in claims.items():
        print(name, "->", per["verdict"])
    print("friend, category-protected (DeepSeek V4.1):", out["friend_category_protected_ds41"])


if __name__ == "__main__":
    main()
