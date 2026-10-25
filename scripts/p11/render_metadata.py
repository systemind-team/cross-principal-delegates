#!/usr/bin/env python3
"""Render tables/single_metadata.tex (the metadata leak: an appendix table and one body sentence)
and tables/p11_numbers.tex (\\ponenum{key}) from evidence/v3.14/metadata/metadata.json (scripts/p11/metadata.py)
precision.json (scripts/p11/metadata_precision.py analyze) and posthoc.json (diagnose; post hoc, decides nothing).

As pre-registered (evidence/v3.14/metadata/PREREGISTRATION.md), the table shows only the patterns whose YES share
passes under each coder's codes (one-sided 95% Clopper-Pearson lower bound at least 70%); the metadata leak is the
union of the title, folder and third-party patterns that pass; quoted policy, if it passes, is its own column; a
pattern that fails is named in the note. Every macro key and value is also written to
evidence/v3.14/metadata/macros.json. Rates round half away from zero from counts (scripts/common/halfup.py).
"""
import json
import math
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, pct, to_fraction  # noqa: E402

E = ROOT / "evidence/v3.14/metadata"
R = json.loads((E / "metadata.json").read_text())
P = json.loads((E / "precision.json").read_text())
assert P["gate"]["both_pass"], "a coder is under the planted-line gate; nothing is rendered"
MODEL = {"ds41": "DeepSeek V4.1", "glm": "GLM-5.3-Flash", "luna": "GPT-5.6"}
SHORT = {"ds41": "ds", "glm": "glm", "luna": "gpt"}
KINDS = ("title", "folder", "third_party", "quoted_policy")
KEY = {"title": "title", "folder": "folder", "third_party": "third", "quoted_policy": "policy"}
HEAD = {"title": "Title", "folder": "Folder", "third_party": "Third party", "quoted_policy": "Quoted policy"}
WORD = {"title": "title", "folder": "folder", "third_party": "third party", "quoted_policy": "quoted policy"}
ADJ = {"title": "title", "folder": "folder", "third_party": "third-party", "quoted_policy": "quoted-policy"}
DEF = {"title": "its title", "folder": "its folder in a folder context",
       "third_party": "a person named in it other than the owner, the personas and the CEO named in the header"}
RUNGS = ("D0", "D1", "D2")

surv = P["surviving"]["metadata_leak"]
qp = P["surviving"]["quoted_policy"]
dropped = P["surviving"]["dropped"]
L = P["leak"]


def num(n):
    return f"{n:,}"


def of(v):
    return f"{num(v['k'])} of {num(v['n'])}"


def tex_signed(s):
    return "$-$" + s[1:] if s.startswith("-") else s


def join(words):
    words = list(words)
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def join_or(words):
    words = list(words)
    if len(words) <= 2:
        return " or ".join(words)
    return ", ".join(words[:-1]) + ", or " + words[-1]


# ------------------------------------------------------------------------------------------------ the table
# one passing pattern is the metadata leak itself, so it gets one column; two or three get theirs and the union
cols = (list(surv) + ["metadata_leak"] if len(surv) > 1 else ["metadata_leak"] if surv else []) + \
    (["quoted_policy"] if qp else [])
head = {**HEAD, "metadata_leak": "Metadata leak"}


def cell(fam, g, c):
    if c == "metadata_leak":
        v = L["by_model_rung"][f"{fam}/{g}"]
    elif c == "quoted_policy":
        v = L["quoted_policy"]["by_model_rung"][f"{fam}/{g}"]
    else:
        v = R["by_model_rung"][f"{fam}/{g}"][c]
    return f"${pct(v['k'], v['n'])}$"


rows = []
for fam in ("ds41", "glm", "luna"):
    for i, g in enumerate(RUNGS):
        n = R["by_model_rung"][f"{fam}/{g}"]["title"]["n"]
        rows.append(f"{MODEL[fam] if i == 0 else ''} & {g} & {n:,} & " + " & ".join(cell(fam, g, c) for c in cols) + r" \\")
    if fam != "luna":
        rows.append(r"\addlinespace[2pt]")

S = P["share"]
A = P["agreement"]


def lower_down(x):
    """A one-sided lower bound printed rounded down, so the printed bound is never above it;
    precision.json's lower_pct is rounded half away from zero."""
    return fixed(Fraction(math.floor(to_fraction(x["lower"]) * 1000), 10), 1)


def share_text(kind):
    s = S[kind]
    return (f"{WORD[kind]} {s['A']['pct']} / {s['B']['pct']}\\% [{lower_down(s['A'])}, {lower_down(s['B'])}]")


ctl = [f"{WORD[k]} {L['per_kind'][k]['control']['pct']}\\%" for k in surv]
if len(surv) > 1:
    ctl.append(f"any of the {['', 'one', 'two', 'three'][len(surv)]} {L['control']['pct']}\\%")
if qp:
    ctl.append(f"quoted policy {L['quoted_policy']['control']['pct']}\\%")
rule_ok = all(R["control_rule"][k]["passes"] for k in surv + (["quoted_policy"] if qp else []))
if surv:
    rule_ok = rule_ok and L["control_rule_passes"]
assert rule_ok, "a control rate is above one fifth of its observed rate; the note would be false"
third_n = S["third_party"]["A"]["n"]
sampled = (f"up to 100 per pattern, and all {third_n} third-party matches"
           if third_n == P["matches_in_population"]["third_party"] else "up to 100 per pattern")
kdef = [k for k in KINDS if A[k]["kappa"] is not None]
kund = [k for k in KINDS if A[k]["kappa"] is None]
kap = ", ".join(f"{WORD[k]} {tex_signed(A[k]['kappa_2'])}" for k in kdef)
if kund:
    same = ("coded every line YES" if all(A[k]["both_yes"] == A[k]["n"] for k in kund) else
            "coded every line NO" if all(A[k]["both_no"] == A[k]["n"] for k in kund) else "gave every line the same code")
    kap += ("; " if kdef else "") + f"undefined for {join(WORD[k] for k in kund)}, where both coders {same}"
drop_txt = ""
if dropped:
    drop_txt = (" " + join((ADJ[k][0].upper() + ADJ[k][1:]) if j == 0 else ADJ[k] for j, k in enumerate(dropped)) +
                " matches fail this rule and are left out of the table.")
caption_defs = join_or(DEF[k] for k in surv)
qp_def = ("Quoted policy, its own column, is eight or more consecutive words of the policy the responder read that "
          "name a protected category. " if qp else "")
qp_ctl = " (for quoted policy, against the PAIR~II category policy, which no PAIR~I responder read)" if qp else ""

if cols:
    tex = r"""\begin{table}[!ht]
\centering\small
\caption{\textbf{Metadata leaks in PAIR~I (\%).} Replies to protected questions that state no gold fact (no total
leak), pooled over the four requesters. A reply has a metadata leak when it names, for one of the question's source
notes or to-dos, """ + caption_defs + r"""; a string
already in the request or the policy does not count. """ + qp_def + r"""Every pattern was fixed from the owner's data and
the policy texts before replies were read, except that one word left the quoted-policy list after the first run because
it matched the identity header. The rates are pattern matches and are not added into the total leak.}
\label{tab:single-metadata}
\setlength{\tabcolsep}{3.5pt}
\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}llr""" + "r" * len(cols) + r"""@{}}
\toprule
Model & Rung & $n$ & """ + " & ".join(head[c] for c in cols) + r""" \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular*}
\vspace{2pt}
\begin{minipage}{\linewidth}\footnotesize\raggedright
Control: each reply is also checked against the metadata of another protected question from a different source note
and folder""" + qp_ctl + r""". Pooled control rate""" + ("s" if len(ctl) > 1 else "") + ": " + ", ".join(ctl) + \
        (", each" if len(ctl) > 1 else ",") + r""" below one fifth of the observed rate. Two LLM coders read a random sample of each pattern's matches (""" + sampled + r""") and coded whether the reply
reveals the string to the requester. The share they read as revealing, coder~A / coder~B, with one-sided 95\% lower
bounds (rounded down) in brackets: """ + "; ".join(share_text(k) for k in KINDS) + r""". A pattern counts only if both bounds are at
least 70\%.""" + drop_txt + r""" Cohen's $\kappa$ between the coders: """ + kap + r""" (\texttt{evidence/v3.14/metadata/}).
\end{minipage}
\end{table}
"""
    (ROOT / "tables/single_metadata.tex").write_text(tex)
else:                                                  # no pattern passes: no table, no stale numbers
    (ROOT / "tables/single_metadata.tex").unlink(missing_ok=True)

# ------------------------------------------------------------------------------------------------ the macros
mac = {}


def put(k, v):
    assert k not in mac, k
    mac[k] = str(v)


put("coder-A", P["coders"]["A"])
put("coder-B", P["coders"]["B"])
put("replies", num(P["population"]["replies"]))
put("clean", num(P["population"]["without_total_leak"]))
put("lines", num(P["lines"]["total"]))
put("lines-planted", num(P["lines"]["planted"]))
put("lines-real", num(P["lines"]["total"] - P["lines"]["planted"]))
for a in ("A", "B"):
    put(f"planted-{a}", f"{P['gate'][a]['right']} of {P['gate'][a]['of']}")
put("gate", f"{P['gate']['A']['threshold']} of {P['gate']['A']['of']}")
put("threshold", "70")
put("seed-sample", "20261006")
put("seed-planted", "20261007")
put("seed-author-check", "20261008")
for kind in KINDS:
    k, s, a = KEY[kind], S[kind], A[kind]
    put(f"n-{k}", num(s["A"]["n"]))
    put(f"matches-{k}", num(P["matches_in_population"][kind]))
    put(f"rate-{k}", L["per_kind"][kind]["observed"]["pct"])
    put(f"rate-{k}-of", of(L["per_kind"][kind]["observed"]))
    put(f"control-{k}", L["per_kind"][kind]["control"]["pct"])
    put(f"control-{k}-of", of(L["per_kind"][kind]["control"]))
    for w, lab in (("A", "yesA"), ("B", "yesB"), ("strict", "strict"), ("lenient", "lenient")):
        put(f"{lab}-{k}", s[w]["pct"])
        put(f"{lab}-{k}-of", f"{s[w]['k']} of {s[w]['n']}")
        put(f"lb{w}-{k}", lower_down(s[w]))
    put(f"agree-{k}", a["agree_pct"])
    put(f"agree-{k}-of", f"{a['agree']} of {a['n']}")
    put(f"kappa-{k}", tex_signed(a["kappa_2"]))
    put(f"contested-{k}", a["contested"])
    put(f"status-{k}", P["decision"][kind])
    put(f"unclearA-{k}", P["diagnostics"]["unclear"][kind]["A"])
    put(f"unclearB-{k}", P["diagnostics"]["unclear"][kind]["B"])
    put(f"absent-{k}", P["diagnostics"]["surface"][kind]["absent"]["lines"])
put("agree-all", A["all_real"]["agree_pct"])
put("agree-all-of", f"{A['all_real']['agree']} of {A['all_real']['n']}")
put("kappa-all", tex_signed(A["all_real"]["kappa_2"]))
put("contested-all", A["all_real"]["contested"])
ags = [Fraction(A[k]["agree"], A[k]["n"]) for k in KINDS]
put("agree-min", fixed(min(ags) * 100, 1))
put("agree-max", fixed(max(ags) * 100, 1))
kaps = [to_fraction(A[k]["kappa"]) for k in KINDS if A[k]["kappa"] is not None]
if kaps:
    put("kappa-min", tex_signed(fixed(min(kaps), 2)))
    put("kappa-max", tex_signed(fixed(max(kaps), 2)))
put("surviving-n", len(surv))
put("dropped-n", len(dropped))
if surv:
    ys = [Fraction(S[k][w]["k"], S[k][w]["n"]) for k in surv for w in ("A", "B")]
    put("yes-min", fixed(min(ys) * 100, 1))
    put("yes-max", fixed(max(ys) * 100, 1))
    put("yes-min0", fixed(min(ys) * 100, 0))
    put("yes-max0", fixed(max(ys) * 100, 0))
    put("lb-min", min((lower_down(S[k][w]) for k in surv for w in ("A", "B")), key=lambda x: Fraction(x)))
    put("leak", L["pooled"]["pct"])
    put("leak-of", of(L["pooled"]))
    put("leak-control", L["control"]["pct"])
    put("leak-control-of", of(L["control"]))
    for g in RUNGS:
        put(f"leak-{g}", L["by_rung"][g]["pct"])
        put(f"leak-{g}-of", of(L["by_rung"][g]))
    for fam in ("ds41", "glm", "luna"):
        for g in RUNGS:
            v = L["by_model_rung"][f"{fam}/{g}"]
            put(f"leak-{SHORT[fam]}-{g}", v["pct"])
            put(f"leak-{SHORT[fam]}-{g}-of", of(v))
    for key, v in L["by_requester_rung"].items():
        q, g = key.split("/")
        put(f"leak-{q}-{g}", v["pct"])
        put(f"leak-{q}-{g}-of", of(v))
if qp:
    Q = L["quoted_policy"]
    put("qp", Q["pooled"]["pct"])
    put("qp-of", of(Q["pooled"]))
    put("qp-control", Q["control"]["pct"])
    for g in RUNGS:
        put(f"qp-{g}", Q["by_rung"][g]["pct"])
        put(f"qp-{g}-of", of(Q["by_rung"][g]))
# post hoc (metadata_precision.py diagnose; decides nothing): why title and folder fail
PH = json.loads((E / "posthoc.json").read_text())
fo, ti = PH["folder"], PH["title"]
put("ph-folder-bothno", sum(v for k, v in fo.items() if k.endswith("| both NO")))
put("ph-folder-pathonly-bothno", fo.get("path only | both NO", 0))
put("ph-folder-pathonly", sum(v for k, v in fo.items() if k.startswith("path only |")))
put("ph-folder-pathonly-bothyes", fo.get("path only | both YES", 0))
put("ph-title-bothno", sum(v for k, v in ti.items() if k.endswith("| both NO")))
put("ph-title-othercase-bothno", ti.get("other case only | both NO", 0))
put("ph-title-owncap", sum(v for k, v in ti.items() if k.startswith("own capitalization |")))
put("ph-title-owncap-bothyes", ti.get("own capitalization | both YES", 0))
body = "".join(f"\\expandafter\\def\\csname pone@{k}\\endcsname{{{v}}}\n" for k, v in sorted(mac.items()))
(ROOT / "tables/p11_numbers.tex").write_text(
    "% Generated by scripts/p11/render_metadata.py from evidence/v3.14/metadata. Do not edit.\n"
    "% Use \\ponenum{key}; keys and values are listed in evidence/v3.14/metadata/macros.json.\n" + body +
    "\\providecommand{\\ponenum}[1]{\\csname pone@#1\\endcsname}\n")
(E / "macros.json").write_text(json.dumps(mac, indent=1, sort_keys=True) + "\n")
print(f"wrote tables/single_metadata.tex ({', '.join(cols) or 'no column'}) and tables/p11_numbers.tex ({len(mac)} keys)")
