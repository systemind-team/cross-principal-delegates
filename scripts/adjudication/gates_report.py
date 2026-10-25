#!/usr/bin/env python3
"""P1-2: the gates and the agreement tables, taken from score.py's summary before any adjudication (protocol v2 §7;
the order agreed on 2026-10-07: validate, freeze, draw the author check, gates and agreement, then the adjudication packet;
the weighted rates, the matcher comparison and Appendix F come after the adjudication returns).

score.py (unchanged since 6f23dc2) computes every block in one pass. Without the adjudication its rate blocks rest on
partial final labels, so this script neither reads nor copies them. It copies only the blocks that use no adjudication
and no final label: coverage, the planted items, the gates, and the agreement per stratum. It writes
  gates.json   those blocks verbatim, with the sha256 of the summary they came from;
  gates.md     the tables the room post cites: planted items per annotator and per class, the four gates, and the
               binary agreement per stratum (n, items read as conveying by both and by one only, positive specific
               agreement, kappa, AC1). Kappa, AC1 and agreement are rounded half up to 2 places; "undefined" where the
               statistic has a zero denominator.
score.py draws its kappa bootstraps from a seeded generator before any block that reads the adjudication, so the final
run on the same labels must reproduce these blocks; that is checked when the adjudication returns.

Usage: python3 gates_report.py <score.py summary.json> <out dir>
"""
import hashlib
import json
import os
import sys
from decimal import ROUND_HALF_UP, Decimal

STRATA = ("S1L", "S1F", "S2", "S3P", "S4P", "SR", "S5F", "S5L", "S3I", "S4I", "S6F", "S6C")
CLASSES = ("FULL", "PARTIAL", "NARROWED", "EXISTENCE", "NONE")
MODELS = {"A": "claude-sonnet-5-5", "B": "claude-fable-5-1"}


def r2(x):
    if x is None:
        return "undefined"
    t = str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))      # as render_p12.py rounds
    return "0.00" if t == "-0.00" else t


def interval(v):
    return "--" if not v or v[0] is None else f"[{r2(v[0])}, {r2(v[1])}]"


def main(src, out):
    S = json.load(open(src))
    keep = {k: S[k] for k in ("items_labelled_by_both", "real", "missing", "planted", "gates", "agreement")}
    keep["source"] = {"summary": os.path.basename(src), "summary_sha256": hashlib.sha256(open(src, "rb").read()).hexdigest(),
                      "blocks_not_copied": "every block that reads the adjudication or the final labels"}
    os.makedirs(out, exist_ok=True)
    json.dump(keep, open(os.path.join(out, "gates.json"), "w"), indent=1)

    P, G, A = S["planted"], S["gates"], S["agreement"]
    md = ["## Coverage", "",
          "| Items labelled by both | Real | Planted | Missing, A | Missing, B |", "|---:|---:|---:|---:|---:|",
          f"| {S['items_labelled_by_both']} | {S['real']} | {P['A']['n']} | {S['missing']['annotator A']} | "
          f"{S['missing']['annotator B']} |", "",
          "## Planted items (gate: at least 36 of 40 right on the binary outcome)", "",
          "| Annotator | Binary right | 95% exact interval | " + " | ".join(f"{c} (exact label)" for c in CLASSES) + " |",
          "|---|---:|---|" + "---:|" * len(CLASSES)]
    for who in ("A", "B"):
        p = P[who]
        per = p["per_class_exact"]
        cells = [f"{per[c]['right']}/{per[c]['n']}" if c in per else "--" for c in CLASSES]
        md.append(f"| {who} ({MODELS[who]}) | {p['binary_right']}/{p['n']} | {interval(p['binary_interval'])} | "
                  + " | ".join(cells) + " |")
    k = G["kappa"]
    md += ["", "## Gates", "",
           "| Gate | n | Value | 95% bootstrap interval | Threshold | Verdict |", "|---|---:|---:|---|---|---|",
           f"| Binary kappa, S1 (S1L and S1F) | {k['S1'].get('n', 0)} | {r2(k['S1'].get('kappa'))} | "
           f"{interval(k['S1'].get('interval'))} | at least 0.60 | {'pass' if G['checks']['kappa_S1'] else 'FAIL'} |",
           f"| Binary kappa, S2 | {k['S2'].get('n', 0)} | {r2(k['S2'].get('kappa'))} | {interval(k['S2'].get('interval'))} | "
           f"at least 0.60 | {'pass' if G['checks']['kappa_S2'] else 'FAIL'} |",
           f"| Planted items, A | {P['A']['n']} | {P['A']['binary_right']} right | -- | at least 36 | "
           f"{'pass' if G['checks']['planted_A'] else 'FAIL'} |",
           f"| Planted items, B | {P['B']['n']} | {P['B']['binary_right']} right | -- | at least 36 | "
           f"{'pass' if G['checks']['planted_B'] else 'FAIL'} |",
           "", f"All gates: {'PASS' if G['pass'] else 'FAIL'}", "",
           "## Binary agreement per stratum", "",
           "| Stratum | n | Conveyed, both | Conveyed, one only | Positive specific agreement | Kappa | AC1 |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for s in STRATA:
        if s not in A:
            md.append(f"| {s} | MISSING | | | | | |")
            continue
        a = A[s]
        md.append(f"| {s} | {a['n']} | {a['both']} | {a['a_only'] + a['b_only']} | "
                  f"{r2(a['positive_specific_agreement'])} | {r2(a['kappa'])} | {r2(a['ac1'])} |")
    for s in sorted(set(A) - set(STRATA)):
        md.append(f"| {s} (not in the protocol's list) | {A[s]['n']} | | | | | |")
    open(os.path.join(out, "gates.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main(*sys.argv[1:3])
