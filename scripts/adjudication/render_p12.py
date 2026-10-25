#!/usr/bin/env python3
"""P1-2: render Appendix F's tables and number macros from score.py's summary (no number typed by hand).

Reads evidence/v3.14/adjudication/analysis/final/summary.json (or --summary), the packets manifest, the frame's
cells.json and the probing records' numbers.json; writes
  tables/adjudication_results.tex   three tables: agreement per stratum (binary and six-class), the two matchers against
                                    what the annotators read, and the earlier single review of the 79 later exposures
                                    against the new labels, split by whether that review saw the full replies;
  tables/adjudication_numbers.tex   \\ptwonum{key} macros for every number F's paragraph and the body cite.
A key the summary does not carry yet (the author check, until the authors answer) prints a bold "??", so an unset number
is visible in the PDF instead of silently empty.
Wording rule: agreement with two LLM annotators; never "human", "validated", "precision", "recall".

Usage: python3 render_p12.py [--summary ...] [--manifest ...] [--cells ...] [--numbers ...] [--out tables]
"""
import argparse
import ast
import collections
import json
import os
import pathlib
import re
from decimal import ROUND_HALF_UP, Decimal

ROOT = pathlib.Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument("--summary", default=str(ROOT / "evidence/v3.14/adjudication/analysis/final/summary.json"))
ap.add_argument("--manifest", default=str(ROOT / "evidence/v3.14/adjudication/packets/MANIFEST.json"))
ap.add_argument("--cells", default=str(ROOT / "evidence/v3.14/adjudication/frame/cells.json"))
ap.add_argument("--numbers", default=str(ROOT / "evidence/v3.14/multi-probing-records/numbers.json"))
ap.add_argument("--out", default=str(ROOT / "tables"))
a = ap.parse_args()
S = json.load(open(a.summary))
M = json.load(open(a.manifest))
C = json.load(open(a.cells))
P = json.load(open(a.numbers))["published_counts"]


def r1(x):
    return "--" if x is None else str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def r2(x):
    if x is None:
        return "--"
    t = str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if t in ("-0.00", "0.00"):
        return "0.00"
    return t.replace("-", "$-$") if t.startswith("-") else t


def pct(x):
    return "--" if x is None else r1(100 * x)


def n(x):
    return f"{x:,}".replace(",", "{,}")


def span(x, y):
    """A range over two readings, printed low to high."""
    if x is None or y is None:
        return "--"
    lo, hi = sorted((x, y))
    return pct(lo) if pct(lo) == pct(hi) else f"{pct(lo)}--{pct(hi)}"


STRATA = [("S1L", "PAIR~II, later replies of the 79 with an exposure"), ("S1F", "PAIR~II, first replies of the 79"),
          ("S2", "PAIR~II, first replies with an exposure, not answered"), ("S3P", "PAIR~II, answered, no exposure"),
          ("S4P", "PAIR~II, answered, with an exposure"), ("SR", "PAIR~II, exposure for the scoring matcher only"),
          ("S5F", "PAIR~II, first refusals, no exposure (sample)"), ("S5L", "PAIR~II, later refusals, no exposure (sample)"),
          ("S3I", "PAIR~I, answered, no exposure"), ("S4I", "PAIR~I, answered, with an exposure"),
          ("S6F", "PAIR~I, refused, with an exposure"), ("S6C", "PAIR~I, refused, no exposure")]
POPS = {"PAIR II first replies": ("p2first", "PAIR~II, first replies"),
        "PAIR II later replies, first-clean instances": ("p2later", "PAIR~II, later replies, first reply clean"),
        "PAIR I DeepSeek": ("p1deepseek", "PAIR~I, DeepSeek"), "PAIR I GLM": ("p1glm", "PAIR~I, GLM"),
        "PAIR I GPT-5.6": ("p1gpt", "PAIR~I, GPT-5.6"), "PAIR I pooled": ("p1pooled", "PAIR~I, pooled")}
MATCHERS = {"analyser": ("diag", "diagnostic"), "runtime": ("score", "scoring")}
CELLS = [("dis-conv", "old disclosure / new conveyed"), ("dis-not", "old disclosure / new not conveyed"),
         ("fp-conv", "old false positive / new conveyed"), ("fp-not", "old false positive / new not conveyed")]
SPLITS = [("all", "all"), ("full", "full view"), ("notfull", "not full view")]
READINGS = [("final", "final"), ("A", "annotator A"), ("B", "annotator B")]

# ------------------------------------------------------------------ table 1: agreement per stratum
rows = []
for k, d in STRATA:
    g = S["agreement"].get(k)
    if not g:
        rows.append(f"{k} & {d} & \\multicolumn{{7}}{{l}}{{MISSING}} \\\\")
        continue
    ci = g.get("kappa_interval") or [None, None]
    rows.append(" & ".join([k, d, n(g["n"]), f"{pct(g['prevalence_a'])}/{pct(g['prevalence_b'])}", pct(g["raw_agreement"]),
                            f"{r2(g['kappa'])} [{r2(ci[0])}, {r2(ci[1])}]" if g.get("kappa") is not None else "--",
                            r2(g.get("positive_specific_agreement")), r2(g.get("ac1")), r2(g.get("six_class_kappa"))]) + " \\\\")

# ------------------------------------------------------------------ table 2: the matchers
mrows = []
for k, v in S["matchers"].items():
    pop, matcher = k.split(" / ")
    f = v["final"]
    ci = v.get("final_interval", {})
    c1 = ci.get("share_of_flags_read_as_conveying")
    c2 = ci.get("share_of_conveying_replies_flagged")
    mrows.append(" & ".join([POPS.get(pop, (None, pop))[1], MATCHERS.get(matcher, (None, matcher))[1],
                             pct(f["share_of_flags_read_as_conveying"]) + (f" [{pct(c1[0])}, {pct(c1[1])}]" if c1 and c1[0] != c1[1] else ""),
                             span(v["strict"]["share_of_flags_read_as_conveying"], v["lenient"]["share_of_flags_read_as_conveying"]),
                             pct(f["share_of_conveying_replies_flagged"]) + (f" [{pct(c2[0])}, {pct(c2[1])}]" if c2 and c2[0] != c2[1] else ""),
                             span(v["strict"]["share_of_conveying_replies_flagged"], v["lenient"]["share_of_conveying_replies_flagged"])])
                 + " \\\\")

# ------------------------------------------------------------------ table 3: the earlier review of the 79
ov = S["later_exposures_79"]["old_reviewer_vs_new"]


def old(reading, split):
    c = ov.get(f"{reading} / {split}", {})
    vals = {short: c.get(long_, 0) for short, long_ in CELLS}
    vals["n"] = sum(vals.values())
    return vals


orows = []
for reading, rlabel in (("final", "Final labels"), ("annotator A", "Coder A"), ("annotator B", "Coder B")):
    for split, slabel in (("full view", "full replies seen"), ("not full view", "not all seen"), ("all", "all")):
        if reading != "final" and split != "all":
            continue
        o = old(reading, split)
        orows.append(" & ".join([rlabel, slabel, n(o["n"])] + [n(o[c]) for c, _ in CELLS]) + " \\\\")

tex = r"""% Generated by scripts/adjudication/render_p12.py from evidence/v3.14/adjudication/analysis/final/summary.json.
\begin{table}[!ht]
\centering\small
\caption{\textbf{Agreement between the two LLM coders, per stratum.} Binary outcome: the reply conveys at least one
protected fact. Exposure: a gold fact the diagnostic matcher finds (PAIR~II; SR: the scoring matcher only) or the scoring
matcher finds (PAIR~I). Prevalence: share conveyed by coder A / coder B, in percent. $\kappa$ with a bootstrap 95\% interval
(S1 resampled by instance); PSA: positive specific agreement $2a/(2a+b+c)$; AC1: Gwet's coefficient, read where prevalence
is under 10\%; $\kappa_6$: Cohen's $\kappa$ on the six labels. A dash marks a statistic with a zero denominator.}
\label{tab:adjudication-agreement}
\setlength{\tabcolsep}{2.2pt}
\begin{tabularx}{\linewidth}{@{}lYrrrlrrr@{}}
\toprule
Stratum & Replies & $n$ & Prev.\ A/B & Agree & $\kappa$ [95\%] & PSA & AC1 & $\kappa_6$ \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabularx}
\end{table}

\begin{table}[!ht]
\centering\small
\caption{\textbf{The matchers compared with what the two LLM coders read.} Weighted by each stratum's inclusion probability.
Exposures read as conveying: the share of replies with the matcher's exposure that the final labels read as conveying a
protected fact. Conveying replies with an exposure: the share of replies read as conveying in which the matcher finds a
gold fact. Each share is given for the final labels, with a stratified bootstrap 95\% interval where a sampled stratum
enters, and as the range over the strict labels (both coders) and the lenient ones (either coder). In percent.}
\label{tab:adjudication-matchers}
\setlength{\tabcolsep}{2.4pt}
\begin{tabularx}{\linewidth}{@{}Ylrrrr@{}}
\toprule
& & \multicolumn{2}{c}{Exposures read as conveying} & \multicolumn{2}{c}{Conveying replies with an exposure} \\
\cmidrule(lr){3-4}\cmidrule(l){5-6}
Replies & Matcher & Final [95\%] & Strict, lenient & Final [95\%] & Strict, lenient \\
\midrule
""" + "\n".join(mrows) + r"""
\bottomrule
\end{tabularx}
\end{table}

\begin{table}[!ht]
\centering\small
\caption{\textbf{The LLM reviewer's verdicts on the 79 later exposures versus the coders' labels.} Per instance: the
reviewer's verdict (disclosure or false positive) versus whether the coders' final labels read a later reply with an
exposure as conveying a protected fact. Seen in full: every such reply was displayed and was no longer than 1,800
characters (cases 1--8) or 900 characters (cases 9--64); otherwise not all seen. The rule is conservative, since the
reviewer's displays showed between 900 and 1,800 characters depending on the batch.}
\label{tab:adjudication-old-review}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}llrrrrr@{}}
\toprule
& & & \multicolumn{2}{c}{Reviewer: disclosure} & \multicolumn{2}{c}{Reviewer: false positive} \\
\cmidrule(lr){4-5}\cmidrule(l){6-7}
Coders' labels & Reviewer's view & Cases & Conveyed & Not conveyed & Conveyed & Not conveyed \\
\midrule
""" + "\n".join(orows) + r"""
\bottomrule
\end{tabular}
\end{table}
"""

# ------------------------------------------------------------------ macros
nums = {}
pl = S["planted"]
for who in ("A", "B"):
    nums[f"planted-{who}"] = f"{pl[who]['binary_right']} of {pl[who]['n']}"
    per = pl[who]["per_class_exact"]
    nums[f"planted-{who}-exact"] = f"{sum(v['right'] for v in per.values())} of {sum(v['n'] for v in per.values())}"
    for c, v in per.items():
        nums[f"planted-{who}-{c}"] = f"{v['right']} of {v['n']}"
for k in ("S1", "S2"):
    g = S["gates"]["kappa"][k]
    nums[f"kappa-{k}"] = r2(g.get("kappa"))
    ci = g.get("interval") or [None, None]
    nums[f"kappa-{k}-lo"], nums[f"kappa-{k}-hi"] = r2(ci[0]), r2(ci[1])
    nums[f"psa-{k}"] = r2(g.get("positive_specific_agreement"))
    nums[f"kappa-{k}-n"] = n(g.get("n", 0))
for k, _ in STRATA:
    g = S["agreement"].get(k)
    if g:
        nums.update({f"agree-{k}-n": n(g["n"]), f"agree-{k}-kappa": r2(g.get("kappa")),
                     f"agree-{k}-psa": r2(g.get("positive_specific_agreement")), f"agree-{k}-ac1": r2(g.get("ac1")),
                     f"agree-{k}-six": r2(g.get("six_class_kappa")), f"agree-{k}-wk": r2(g.get("weighted_kappa")),
                     f"agree-{k}-bindis": n(g["a_only"] + g["b_only"]),
                     f"agree-{k}-labdis": n(sum(g.get("disagreements_by_label_pair", {}).values()))})
nums["s1-bindis"] = n(sum(S["agreement"][k]["a_only"] + S["agreement"][k]["b_only"] for k in ("S1L", "S1F") if k in S["agreement"]))
nums["real-bindis"] = n(sum(g["a_only"] + g["b_only"] for g in S["agreement"].values()))
nums["real-items"] = n(S["real"])
ad = S["adjudication"]
nums.update({"adj-disagreements": n(ad["disagreements"]), "adj-adjudicated": n(ad["adjudicated"]),
             "adj-higher": n(ad["chose_higher_label"]), "adj-A": n(ad["sided_with_A"]), "adj-B": n(ad["sided_with_B"]),
             "adj-unreadable": n(ad["unreadable"])})
le = S["later_exposures_79"]
ub = le["upper_bound_addition"]
nums.update({"later-instances": n(le["instances"]),
             "later-final": str(le["final"]["later_disclosures"]), "later-strict": str(le["strict"]["later_disclosures"]),
             "later-lenient": str(le["lenient"]["later_disclosures"]),
             "later-A": str(le["annotator A"]["later_disclosures"]), "later-B": str(le["annotator B"]["later_disclosures"]),
             "later-first-conveyed": str(le["final"]["first_reply_conveyed"]),
             "later-some": str(le["final"]["some_flagged_later_reply_conveyed"]),
             "later-add": r1(ub["estimated_clean_later_replies_conveying"]),
             "later-add-lo": r1(ub["interval"][0]) if ub["interval"] else "--",
             "later-add-hi": r1(ub["interval"][1]) if ub["interval"] else "--",
             "later-s5l-k": n(ub["S5L_conveyed"]), "later-s5l-n": n(ub["S5L_labelled"]), "later-s5l-pop": n(ub["S5L_population"]),
             "later-sr": n(ub["SR_later_conveyed"]), "later-sr-n": n(ub["SR_later"])})
if ub["estimated_clean_later_replies_conveying"] is not None:
    base = le["final"]["later_disclosures"] + ub["SR_later_conveyed"]
    nums["later-upper"] = r1(base + ub["estimated_clean_later_replies_conveying"])
    nums["later-upper-lo"] = r1(base + ub["interval"][0])
    nums["later-upper-hi"] = r1(base + ub["interval"][1])
for short, reading in READINGS:
    for sshort, split in SPLITS:
        o = old(reading, split)
        for c in ("n", "dis-conv", "dis-not", "fp-conv", "fp-not"):
            nums[f"old-{short}-{sshort}-{c}"] = n(o[c])
o = old("final", "all")
nums["old-dis"], nums["old-fp"] = n(o["dis-conv"] + o["dis-not"]), n(o["fp-conv"] + o["fp-not"])
fr = S["first_reply_refusal_channel"]
by = fr["by_labels"]
nums.update({"first-pct": r1(fr["point_over_2396"]), "first-pct-reply": r1(fr["point_over_first_asks_with_reply"]),
             "first-ann-lo": r1(fr["annotator_interval_over_2396"][0]), "first-ann-hi": r1(fr["annotator_interval_over_2396"][1]),
             "first-samp-lo": r1(fr["sampling_interval_over_2396"][0]), "first-samp-hi": r1(fr["sampling_interval_over_2396"][1]),
             "first-out-lo": r1(fr["outer_interval_over_2396"][0]), "first-out-hi": r1(fr["outer_interval_over_2396"][1]),
             "first-count": r1(by["final"]["estimate_count"]), "first-count-strict": r1(by["strict"]["estimate_count"]),
             "first-count-lenient": r1(by["lenient"]["estimate_count"]),
             "first-census": n(by["final"]["census_conveyed"]), "first-census-n": n(by["final"]["census_items"]),
             "first-s5f-k": n(by["final"]["S5F_conveyed"]), "first-s5f-n": n(by["final"]["S5F_labelled"]),
             "first-s5f-pop": n(C["pair2"]["strata"]["S5F"]["population"]),
             "instances": n(C["pair2"]["instances"]), "first-with-reply": n(C["pair2"]["first_replies_with_text"]),
             "analyser-k": n(P["first_reply_hit_not_recorded_answered"]),
             "analyser-pct": r1(100 * P["first_reply_hit_not_recorded_answered"] / P["first_asks"]),
             "decision-k": n(P["first_asks_recorded_answered_with_hit"]),
             "decision-pct": r1(100 * P["first_asks_recorded_answered_with_hit"] / P["first_asks"])})
for k, v in S["matchers"].items():
    pop, matcher = k.split(" / ")
    key = f"m-{POPS.get(pop, (re.sub(r'[^a-z0-9]+', '', pop.lower()),))[0]}-{MATCHERS.get(matcher, (matcher,))[0]}"
    ci = v.get("final_interval", {})
    for short, field in (("flags", "share_of_flags_read_as_conveying"), ("conv", "share_of_conveying_replies_flagged")):
        nums[f"{key}-{short}"] = pct(v["final"][field])
        nums[f"{key}-{short}-strict"] = pct(v["strict"][field])
        nums[f"{key}-{short}-lenient"] = pct(v["lenient"][field])
        c = ci.get(field)
        nums[f"{key}-{short}-lo"], nums[f"{key}-{short}-hi"] = (pct(c[0]), pct(c[1])) if c else ("--", "--")
for k, v in S["existence"].items():
    nums[f"ex-{k}-k"], nums[f"ex-{k}-n"] = n(v["existence"]), n(v["conveying_and_narrowing_nothing"])
models = M.get("annotator_models", {})
nums["model-A"] = "Claude Sonnet 5.5" if "sonnet-5-5" in models.get("annotator-A", "") else models.get("annotator-A", "")
nums["model-B"] = "Claude Fable 5.1" if "fable-5-1" in models.get("annotator-B", "") else models.get("annotator-B", "")
adj_model = (M.get("adjudication") or {}).get("model", "")
if adj_model:
    nums["model-adj"] = "Claude Haiku 4.5" if "haiku-4-5" in adj_model else adj_model
if "author_check" in S:
    au = S["author_check"]
    ci = au.get("binary_interval") or [None, None]
    nums.update({"author-n": str(au["items"]), "author-binary": str(au["binary_agreement"]),
                 "author-label": str(au["label_agreement"]), "author-err-hi": pct(au["error_upper_bound"]),
                 "author-binary-lo": pct(ci[0]), "author-binary-hi": pct(ci[1]),
                 "author-contradict-both": str(len(au["stop_rule_author_contradicts_both"]))})
# The LLM reviewer's view of each of the 79 later exposures: key.jsonl's old_reviewer.view, from
# make_packets.py's rule (a later reply with an exposure counts as seen in full when it was displayed and is no
# longer than 1,800 characters for cases 1-8 or 900 for cases 9-64). One count per case.
KEY = ROOT / "evidence/v3.14/adjudication/sealed/key.jsonl"
if KEY.exists():
    views, seen_cases = collections.Counter(), set()
    for line in open(KEY):
        o = json.loads(line).get("old_reviewer")
        if not o or o == "None":
            continue
        o = ast.literal_eval(o) if isinstance(o, str) else o
        if o["case"] in seen_cases:
            continue
        seen_cases.add(o["case"])
        views[o["view"]] += 1
    nums.update({"old-view-full": n(views["full"]),
                 "old-view-cut": n(views["cut by the display limit"]),
                 "old-view-first": n(views["first of several flagged replies only"]),
                 "old-view-gold": n(views["gold-word sentences only"])})
for k, v in list(nums.items()):
    if re.fullmatch(r"\d+ of \d+", v):
        nums[f"{k}-frac"] = v.replace(" of ", "/")
numbers = "".join(f"\\expandafter\\def\\csname ptwo@{k}\\endcsname{{{v}}}\n" for k, v in sorted(nums.items()))
numbers += "\\providecommand{\\ptwonum}[1]{\\ifcsname ptwo@#1\\endcsname\\csname ptwo@#1\\endcsname\\else\\textbf{??}\\fi}\n"
os.makedirs(a.out, exist_ok=True)
open(os.path.join(a.out, "adjudication_results.tex"), "w").write(tex)
open(os.path.join(a.out, "adjudication_numbers.tex"), "w").write(
    "% Generated by scripts/adjudication/render_p12.py from evidence/v3.14/adjudication/analysis/final/summary.json.\n"
    "% Use \\ptwonum{key}; a key not set yet prints a bold ??.\n" + numbers)
print("wrote", a.out, "with", len(nums), "macros")
