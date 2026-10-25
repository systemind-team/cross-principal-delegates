#!/usr/bin/env python3
"""Public/internal coding numbers as \\pfournum{key} (tables/p14_numbers.tex, loaded by appendix/macros_adjudication.tex) from
evidence/v3.14/coding-p1-4/results.json (scripts/p14/p14_run.py) and work_public_leaks.json
(scripts/p14/work_public_leaks.py). Every key and value is also written to evidence/v3.14/coding-p1-4/macros.json.
Rates round half away from zero from counts (scripts/common/halfup.py)."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, pct, to_fraction  # noqa: E402

C4 = ROOT / "evidence/v3.14/coding-p1-4"
R = json.loads((C4 / "results.json").read_text())
W = json.loads((C4 / "work_public_leaks.json").read_text())
SHORT = {"DeepSeek": "ds", "GLM": "glm", "GPT-5.6": "gpt"}
mac = {}


def put(k, v):
    assert k not in mac, k
    mac[k] = str(v)


def num(n):
    return f"{n:,}"


# the work_public split (two LLM coders)
ag, rel = R["agreement"], R["relabel"]
n, t = ag["lines"], ag["table"]
agree = t["both_public"] + t["both_internal"]
assert W["split"]["both_PUBLIC"] == t["both_public"] and W["split"]["both_INTERNAL"] == t["both_internal"]
put("wp-n", num(n))
put("wp-public", t["both_public"])
put("wp-public-of", f"{t['both_public']} of {num(n)}")
put("wp-public-pct", pct(t["both_public"], n))
put("wp-internal", t["both_internal"])
put("wp-internal-of", f"{t['both_internal']} of {num(n)}")
put("wp-internal-pct", pct(t["both_internal"], n))
put("wp-contested", rel["contested"])
put("wp-agree", pct(agree, n))
put("wp-agree-of", f"{agree} of {num(n)}")
put("wp-kappa", fixed(to_fraction(ag["kappa"]), 2))
put("wp-kappa-lo", fixed(to_fraction(ag["kappa_bootstrap_95"][0]), 2))
put("wp-kappa-hi", fixed(to_fraction(ag["kappa_bootstrap_95"][1]), 2))
put("wp-unclear-A", ag["unclear"]["A"])
put("wp-unclear-B", ag["unclear"]["B"])
put("wp-unclear-either", W["split"]["unclear_either"])
put("wp-bound", rel["public_S3_bound"])
for a in ("A", "B"):
    put(f"planted-{a}", f"{R['planted'][a]['correct']} of {R['planted'][a]['of']}")
# the review's category-public leaks across the split
rv = W["review"]
put("rev-traces", rv["traces"])
put("rev-S1", rv["S1_sampled_leaks"])
put("rev-public", rv["category_public_leaks"])
for m, s in SHORT.items():
    put(f"rev-public-{s}", rv["category_public_by_model"][m])
total = rv["category_public_leaks"]
for r, k in (("both PUBLIC", "public"), ("both INTERNAL", "internal"), ("contested", "contested")):
    b = W["leaks_by_reading"][r]
    put(f"leaks-{k}", b["leaks"])
    put(f"leaks-{k}-of", f"{b['leaks']} of {total}")
    put(f"leaks-{k}-pct", pct(b["leaks"], total))
    put(f"leaks-{k}-q", b["questions"])
    for m, s in SHORT.items():
        put(f"leaks-{k}-{s}", b["by_model"][m])
for r, k in (("flagged unclear by either coder", "internal-unclear"), ("not flagged", "internal-clear")):
    b = W["internal_by_unclear"][r]
    put(f"leaks-{k}", b["leaks"])
    put(f"leaks-{k}-q", b["questions"])
put("leaks-q", W["all"]["questions"])
# the label variants (scripts/p14/survival.py, apply_variants.py): significant PAIR I family tests per variant, and
# S5 (the four-pass majority without E) against the original labels (added 2026-10-23 for C.1's S5 sentence)
LAB = ROOT / "evidence/v3.14/labels"
SURV = json.loads((LAB / "survival.json").read_text())
put("var-size", SURV["family"]["original"]["size"])
for v, b in SURV["family"].items():
    put(f"var-sig-{v}", b["significant"])
def _dir(iw):
    return (iw[0] > iw[1]) - (iw[0] < iw[1])


for v, b in SURV["family"].items():
    if v == "original":
        continue
    lost = gained = reversed_ = 0
    for c in b["changes_vs_original"]:
        o_sig, v_sig = c["original"]["holm"] < 0.05, c["variant"]["holm"] < 0.05
        flip = _dir(c["original"]["iw"]) * _dir(c["variant"]["iw"]) < 0
        lost += o_sig and not v_sig
        gained += v_sig and not o_sig
        reversed_ += v_sig and flip
    kept_flip = sum(1 for c in b["changes_vs_original"] if c["original"]["holm"] < 0.05 and c["variant"]["holm"] < 0.05
                    and _dir(c["original"]["iw"]) * _dir(c["variant"]["iw"]) < 0)
    put(f"var-lost-{v}", lost)
    put(f"var-gained-{v}", gained)
    put(f"var-reversed-{v}", reversed_)
    put(f"var-kept-{v}", SURV["family"]["original"]["significant"] - lost - kept_flip)
    assert SURV["family"]["original"]["significant"] - lost - kept_flip + gained + kept_flip == b["significant"] or reversed_, v
ch = SURV["family"]["S5"]["changes_vs_original"]
put("s5-gained", sum(1 for c in ch if c["original"]["holm"] >= 0.05 > c["variant"]["holm"]))
put("s5-lost", sum(1 for c in ch if c["variant"]["holm"] >= 0.05 > c["original"]["holm"]))
for v, tag in (("original", "orig"), ("S5", "s5")):
    t3 = json.loads((LAB / f"applied_{v}.json").read_text())["pair1"]["table3"]
    vals = []
    for m, s_ in (("ds41", "ds"), ("glm", "glm"), ("luna", "gpt")):
        fr = t3[f"{m}-d2-r3"]["FR"]
        put(f"{tag}-friend-D2FR-{s_}", pct(fr["k"], fr["n"]))
        put(f"{tag}-friend-D2FR-{s_}-of", f"{fr['k']} of {fr['n']}")
        vals.append((fr["k"], fr["n"]))
    lo, hi = min(vals, key=lambda x: x[0] / x[1]), max(vals, key=lambda x: x[0] / x[1])
    put(f"{tag}-friend-D2FR-min", pct(*lo))
    put(f"{tag}-friend-D2FR-max", pct(*hi))
body = "".join(f"\\expandafter\\def\\csname pfour@{k}\\endcsname{{{v}}}\n" for k, v in sorted(mac.items()))
(ROOT / "tables/p14_numbers.tex").write_text(
    "% Generated by scripts/p14/render_macros.py from evidence/v3.14/coding-p1-4. Do not edit.\n"
    "% Use \\pfournum{key}; keys and values are listed in evidence/v3.14/coding-p1-4/macros.json.\n" + body +
    "\\providecommand{\\pfournum}[1]{\\csname pfour@#1\\endcsname}\n")
(C4 / "macros.json").write_text(json.dumps(mac, indent=1, sort_keys=True) + "\n")
print(f"wrote tables/p14_numbers.tex ({len(mac)} keys)")
