"""One rounding rule for every number the paper prints.

Rule: round half away from zero ("half-up" on magnitudes), applied to the unrounded value.
  * Rates come from integer counts: pct(k, n) rounds the exact fraction 100k/n, so 3/48 = 6.25% prints 6.3.
  * Exact-test p-values come from their exact fractions (mcnemar_p, signflip_p), so 0.0625 prints 0.063.
  * A float whose exact value is unknown (a bootstrap bound, a mean) is read through repr(), the
    shortest decimal that round-trips, so -0.3125 prints -0.313 and 0.1235 prints 0.124.
Python's round() and format() round ties to even on the binary value (6.25 -> 6.2, 0.0625 -> 0.062);
nothing that is printed may go through them.
"""
from decimal import Decimal
from fractions import Fraction
from math import comb, floor

__all__ = ["to_fraction", "fixed", "pct", "sig", "mcnemar_p", "signflip_floor", "fmt_p", "fmt_p_dec", "fmt_p_tex",
           "signed", "MINUS"]

MINUS = "-"


def to_fraction(x):
    """Exact value of x: a Fraction stays exact; an int is exact; a float is read through repr()."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, float):
        return Fraction(Decimal(repr(x)))
    if isinstance(x, (str, Decimal)):
        return Fraction(Decimal(x))
    raise TypeError(f"cannot round {type(x).__name__}")


def _round_units(fr, digits):
    """Integer number of 10^-digits units, ties away from zero."""
    scaled = fr * (10 ** digits) if digits >= 0 else fr / (10 ** -digits)
    sign = -1 if scaled < 0 else 1
    return sign * floor(abs(scaled) + Fraction(1, 2))


def fixed(x, digits=1):
    """x rounded half away from zero to `digits` decimals, as a string ("6.3", "-0.313", "0.0")."""
    units = _round_units(to_fraction(x), digits)
    sign = "-" if units < 0 else ""
    units = abs(units)
    if digits <= 0:
        return f"{sign}{units * 10 ** (-digits)}"
    whole, frac = divmod(units, 10 ** digits)
    return f"{sign}{whole}.{frac:0{digits}d}"


def pct(k, n, digits=1):
    """100k/n rounded from the exact fraction."""
    if not n:
        raise ZeroDivisionError("empty denominator")
    return fixed(Fraction(100 * k, n), digits)


def sig(x, figures=2):
    """x to `figures` significant figures, half away from zero, plain decimal notation."""
    fr = to_fraction(x)
    if fr == 0:
        return "0"
    mag = abs(fr)
    exp = 0  # position of the leading digit: mag in [10^exp, 10^(exp+1))
    while mag >= 10:
        mag /= 10
        exp += 1
    while mag < 1:
        mag *= 10
        exp -= 1
    digits = figures - 1 - exp
    units = _round_units(fr, digits)
    # rounding up can add a digit (0.0995 -> 0.10); recompute the digit count from the result
    if abs(units) >= 10 ** figures:
        digits -= 1
        units = _round_units(fr, digits)
    return fixed(Fraction(units, 10 ** digits) if digits >= 0 else Fraction(units * 10 ** -digits), max(digits, 0))


def mcnemar_p(b, c):
    """Exact two-sided McNemar p as a Fraction: min(1, 2 * P[X <= min(b, c)]), X ~ Bin(b + c, 1/2)."""
    n = b + c
    if n == 0:
        return Fraction(1)
    k = min(b, c)
    return min(Fraction(1), Fraction(2 * sum(comb(n, i) for i in range(k + 1)), 2 ** n))


def signflip_floor(nonzero_clusters):
    """Smallest two-sided p an exact sign-flip test over m non-zero clusters can return: 2 / 2^m."""
    return Fraction(2, 2 ** nonzero_clusters) if nonzero_clusters else Fraction(1)


def fmt_p(p, small=Fraction(1, 1000)):
    """Plain-text p: two decimals at or above 0.1, two significant figures below, 'a x 10^-e' below 0.001."""
    fr = to_fraction(p)
    if fr >= Fraction(1, 10):
        return fixed(fr, 2)
    if fr >= small:
        return sig(fr, 2)
    mant, exp = _mantissa(fr)
    return f"{mant}e{exp}"


def fmt_p_dec(p):
    """The decimal p style of the appendix notes: '<0.001', three decimals below 0.01, two above."""
    fr = to_fraction(p)
    if fr < Fraction(1, 1000):
        return "<0.001"
    return fixed(fr, 3 if fr < Fraction(1, 100) else 2)


def _mantissa(fr, figures=2):
    """(mantissa string with figures significant digits, exponent) for 0 < fr < 1, half away from zero."""
    exp = 0
    m = fr
    while m < 1:
        m *= 10
        exp -= 1
    s = fixed(m, figures - 1)
    if s.startswith("10"):            # 9.96 -> 10.0 -> 1.0 x 10^(exp+1)
        exp += 1
        s = fixed(m / 10, figures - 1)
    return s, exp


def fmt_p_tex(p):
    """The paper's p style in LaTeX math: $0.38$, $0.063$, $3.8\\times10^{-6}$."""
    fr = to_fraction(p)
    if fr >= Fraction(1, 1000):
        return f"${fmt_p(fr)}$"
    mant, exp = _mantissa(fr)
    return f"${mant}\\times10^{{{exp}}}$"


def signed(x, digits=2):
    """Explicit sign for differences: +0.11, -0.03. An exact zero prints unsigned (0.00); a nonzero value
    that rounds to zero keeps its sign (-0.00, +0.00), so the side of zero is never lost."""
    fr = to_fraction(x)
    s = fixed(fr, digits)
    if fr == 0:
        return s
    if fr < 0:
        return s if s.startswith("-") else "-" + s
    return "+" + s
