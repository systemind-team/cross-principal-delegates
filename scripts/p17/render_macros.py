#!/usr/bin/env python3
"""Corrected-inference numbers the body states as bounds, as \\psevennum{key} (tables/p17_numbers.tex).

Input: evidence/v3.14/p17/{families.json, pair1_tests.json, pair2_tests.json} (scripts/p17/inference.py). The sign-flip
and McNemar p of these tests are dyadic fractions, and Holm multiplies them by integers, so each is read exactly.

Keys (a family member is "<block>/<requester>/<contrast>/<metric>" in families.json):
  p1-family-n, p2-family-n          the Holm family sizes (PAIR I 48, PAIR II 36)
  p1-R3-FR-D0D1-*                   the close friend's false refusal, D0 to D1, on each of the three models (PAIR I)
  p2-TL-D0D2-*                      the total leak, D0 to D2, in each of the nine PAIR II blocks (sign-flip over groups)
  *-p-max, *-holm-max               the largest unadjusted and Holm-adjusted p, two significant figures, half away
                                    from zero (a value)
  *-p-max-up, *-holm-max-up         the same rounded up (a bound the text may print after "<=" or "at most")
  *-p-max-up1, *-holm-max-up1       rounded up to one significant figure (a bound after "<"; "10^{-4}" when it is a
                                    power of ten)
  *-n                               the number of tests the bound covers
  swap-*                            the 40 requester-swap and harness tests of Table 24 (families.json pair1_bh
                                    swap_harness_leak_FR; 20 total leak, 20 false refusal): the largest paired
                                    difference |b - a| in points, exactly from the discordant counts, as a value
                                    (swap-{tl,fr}-max) and rounded up (swap-{tl,fr}-max-up: "moves ... by at most");
                                    the comparisons whose 95% interval excludes differences above 10 points of total
                                    leak (swap-tl-within10) and above 5 points of false refusal (swap-fr-within5)
Every bound is checked to hold: each test's p (or difference) is at most the printed bound.
Writes tables/p17_numbers.tex and evidence/v3.14/p17/macros.json.  Usage: python3 scripts/p17/render_macros.py
"""
import json
import math
import pathlib
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, fmt_p_tex, to_fraction  # noqa: E402

P = ROOT / "evidence/v3.14/p17"


def exact(x):
    """A p stored as a float of a dyadic fraction (2 / 2^m times an integer) is exact in binary."""
    fr = Fraction(x)
    assert fr.denominator & (fr.denominator - 1) == 0, f"{x} is not dyadic"
    return fr


def up_sig(x, figures):
    """(LaTeX string, Fraction) of x rounded up to `figures` significant figures."""
    fr = to_fraction(x)
    e = math.floor(math.log10(fr))
    while Fraction(10) ** e > fr:
        e -= 1
    while Fraction(10) ** (e + 1) <= fr:
        e += 1
    scale = Fraction(10) ** (e - figures + 1)
    units = math.ceil(fr / scale)
    val = units * scale
    if units == 10 ** figures:                 # 9.96 -> 10.0: one more digit
        e, units = e + 1, 10 ** (figures - 1)
    if val >= Fraction(1, 1000):
        return fixed(val, max(0, figures - 1 - e)), val
    mant = Fraction(units, 10 ** (figures - 1))
    if figures == 1 and units == 1:
        return f"10^{{{e}}}", val
    return f"{fixed(mant, figures - 1)}\\times10^{{{e}}}", val


def bounds(prefix, ps, holms, m):
    m[f"{prefix}-n"] = str(len(ps))
    for kind, xs in (("p", ps), ("holm", holms)):
        top = max(xs)
        m[f"{prefix}-{kind}-max"] = fmt_p_tex(top).strip("$")
        for fig, suffix in ((2, "up"), (1, "up1")):
            s, val = up_sig(top, fig)
            assert all(x <= val for x in xs), (prefix, kind, suffix)
            m[f"{prefix}-{kind}-max-{suffix}"] = s


def main():
    fam = json.loads((P / "families.json").read_text())
    t1 = json.loads((P / "pair1_tests.json").read_text())
    t2 = json.loads((P / "pair2_tests.json").read_text())
    f1, f2 = fam["pair1_family"], fam["pair2_family"]
    m = {"p1-family-n": str(len(f1)), "p2-family-n": str(len(f2))}
    k1 = sorted(k for k in f1 if k.split("/")[1:] == ["R3", "D0->D1", "FR"])
    assert len(k1) == 3
    for k in k1:
        assert exact(t1[k]["p"]) == Fraction(t1[k]["p_exact"])
    bounds("p1-R3-FR-D0D1", [exact(t1[k]["p"]) for k in k1], [exact(f1[k]["holm"]) for k in k1], m)
    k2 = sorted(k for k in f2 if k.split("/")[2:] == ["D0->D2", "leak_TD"])
    assert len(k2) == 9
    bounds("p2-TL-D0D2", [exact(t2[k]["signflip_p"]) for k in k2], [exact(f2[k]["holm"]) for k in k2], m)
    # Table 24's requester swaps and harness: the body's "moves ... by at most" bounds, rounded up so they hold
    q = fam["pair1_bh"]["swap_harness_leak_FR"]["q"]
    m["swap-tests"] = str(len(q))
    for metric, short, margin in (("leak_TD", "tl", 10), ("FR", "fr", 5)):
        ks = [k for k in q if k.endswith("/" + metric)]
        gaps = [abs(Fraction(100 * (t1[k]["improved_worsened"][1] - t1[k]["improved_worsened"][0]), t1[k]["n"]))
                for k in ks]
        for k, g in zip(ks, gaps):
            assert abs(float(g) - abs(100 * t1[k]["diff"])) < 1e-9, k
        top = max(gaps)
        s_up = fixed(Fraction(math.ceil(top * 10), 10), 1)
        assert all(g <= Fraction(s_up) for g in gaps)
        within = sum(t1[k]["null_reading"] == f"no difference larger than {margin} points" for k in ks)
        m.update({f"swap-{short}-n": str(len(ks)), f"swap-{short}-max": fixed(top, 1), f"swap-{short}-max-up": s_up,
                  f"swap-{short}-within{margin}": str(within)})
    (P / "macros.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    (ROOT / "tables/p17_numbers.tex").write_text(
        "% Generated by scripts/p17/render_macros.py from evidence/v3.14/p17. Do not edit.\n"
        "% Use \\psevennum{key}; the p keys hold \\times10^{..} and go in math mode. Keys and values in "
        "evidence/v3.14/p17/macros.json.\n"
        + "".join(f"\\expandafter\\def\\csname pseven@{k}\\endcsname{{{v}}}\n" for k, v in sorted(m.items()))
        + "\\providecommand{\\psevennum}[1]{\\ifcsname pseven@#1\\endcsname\\csname pseven@#1\\endcsname"
          "\\else\\textbf{??}\\fi}\n")
    print(json.dumps(m, indent=1))


if __name__ == "__main__":
    main()
