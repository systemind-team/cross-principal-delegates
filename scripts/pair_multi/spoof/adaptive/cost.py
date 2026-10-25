#!/usr/bin/env python3
"""P2-3 adaptive-attacker arm: per-session cost and the stop table. v2, after the reviews of 2026-10-24
. Design numbers only, no spend.

Two concurrent arms, both with Gemini 2.5 Flash as the attacker and DeepSeek V4 Flash as the responder, on the
same 50 groups and replicates: the adaptive arm, and a degenerate-attacker control that asks
each item plainly under the same heartbeat. The 10-05 P1-6 arms are the drift check and cost nothing new. So
the full run is 2 arms x 50 groups x R replicates of Gemini sessions, plus a pilot.

Per-session anchor from P1-6's frozen ledger ($12.51, 718 folders, provider mean $0.017381/folder): the
responder (DeepSeek, unchanged) costs the frozen mean; the attacker seat's frozen DeepSeek token volume is the
context anchor, repriced at Gemini's gateway rate with a x2 completion markup for a model that reasons over the
dialogue, with caching and without (the bracket; the gateway's cache pass-through for a cross-model requester
is not guaranteed). The degenerate control's attacker writes less, so it is at most the adaptive cost; both are
priced at the adaptive rate here, conservatively.

Stop table (, deterministic): the full-run default is 50 groups x 1 replicate per arm, which fits
under $15 with caching; 50 groups x 2 replicates per arm needs the $25 cap that has been requested. The pilot
runs under the existing $15 approval. The re-sizing order is fixed: keep Gemini and run 1 replicate if 2 do not
fit; switch to gemini-2.5-flash-lite (new pilot) only if 1 replicate does not fit.

Inputs (frozen): p16-anchor-tokens.jsonl.xz, prices.json.
Usage: python3 cost.py > ../../../../evidence/v3.14/multi-adaptive/cost.json
"""
import hashlib
import json
import lzma
import pathlib
import statistics as st

ROOT = pathlib.Path(__file__).resolve().parents[4]
ANCHOR = ROOT / "evidence/v3.14/multi-adaptive/p16-anchor-tokens.jsonl.xz"
PRICES = ROOT / "evidence/v3.14/multi-adaptive/prices.json"
HEADER_ARMS = ("A0h", "C1h", "C2h") # the D2R_ID_R0 arms = the attacker arm's primary condition
RESPONDER_MODEL = "deepseek/deepseek-v4-flash-0731"
COMPLETION_MARKUP = (1.0, 2.0, 4.0)
CAP_EXISTING = 15.0
CAP_REQUESTED = 25.0
STOP_LINE = 13.40
KILL = 14.40
PILOT_SESSIONS = 10

prices = json.loads(PRICES.read_text())["prices"]
rows = [json.loads(l) for l in lzma.open(ANCHOR, "rt")]
anchor_sha = hashlib.sha256(ANCHOR.read_bytes()).hexdigest()

hdr = [r for r in rows if r["folder"].split("-")[1] in HEADER_ARMS]
req = [r["actors"].get("requester", {}) for r in hdr]
resp = [r["actors"].get("responder", {}) for r in hdr]


def mean(xs):
    return st.mean(xs)


anchor = {
    "header_sessions": len(hdr),
    "responder_cost_usd_mean": round(mean(a.get("costUsd", 0) for a in resp), 6),
    "attacker_seat_prompt_tokens_mean": round(mean(a.get("promptTokens", 0) for a in req)),
    "attacker_seat_cached_tokens_mean": round(mean(a.get("cachedTokens", 0) for a in req)),
    "attacker_seat_uncached_tokens_mean": round(mean(a.get("promptTokens", 0) - a.get("cachedTokens", 0) for a in req)),
    "attacker_seat_completion_tokens_mean": round(mean(a.get("completionTokens", 0) for a in req)),
}
prompt = anchor["attacker_seat_prompt_tokens_mean"]
cached = anchor["attacker_seat_cached_tokens_mean"]
uncached = anchor["attacker_seat_uncached_tokens_mean"]
base_completion = anchor["attacker_seat_completion_tokens_mean"]
resp_cost = anchor["responder_cost_usd_mean"]


def attacker_cost(price, completion, use_cache):
    cin = price.get("cached_input")
    if use_cache and cin is not None:
        tok = uncached * price["input"] + cached * cin
    else:
        tok = prompt * price["input"]
    return (tok + completion * price["output"]) / 1_000_000


candidates = {}
for mid, price in prices.items():
    if mid == RESPONDER_MODEL:
        continue
    by_mk = {}
    for mk in COMPLETION_MARKUP:
        comp = round(base_completion * mk)
        wc = attacker_cost(price, comp, True)
        nc = attacker_cost(price, comp, False)
        by_mk[f"completion_x{mk:g}"] = {
            "session_cost_with_cache_usd": round(wc + resp_cost, 6),
            "session_cost_no_cache_usd": round(nc + resp_cost, 6),
        }
    candidates[mid] = {"price_per_1m": price,
                       "family": "SAME AS RESPONDER (avoid)" if "deepseek" in mid else "different-family",
                       "by_completion_markup": by_mk}

REC = "google/gemini-2.5-flash"
LITE = "google/gemini-2.5-flash-lite"
rec_cache = candidates[REC]["by_completion_markup"]["completion_x2"]["session_cost_with_cache_usd"]
rec_nocache = candidates[REC]["by_completion_markup"]["completion_x2"]["session_cost_no_cache_usd"]
lite_cache = candidates[LITE]["by_completion_markup"]["completion_x2"]["session_cost_with_cache_usd"]
lite_nocache = candidates[LITE]["by_completion_markup"]["completion_x2"]["session_cost_no_cache_usd"]


def stop_table(session_cost):
    pilot = PILOT_SESSIONS * session_cost
    out = {"pilot_sessions": PILOT_SESSIONS, "pilot_cost_usd": round(pilot, 2)}
    for label, reps in (("2_replicates_per_arm", 2), ("1_replicate_per_arm", 1)):
        sessions = 2 * 50 * reps # two arms x 50 groups x reps
        total = sessions * session_cost # the pilot's sessions are inside the 100/200 (as in P1-6)
        out[label] = {
            "gemini_sessions": sessions,
            "projected_total_usd": round(total, 2),
            "fits_under_stop_line_13_40": total <= STOP_LINE,
            "fits_under_existing_cap_15": total <= CAP_EXISTING,
            "fits_under_requested_cap_25": total <= CAP_REQUESTED,
        }
    return out


out = {
    "inputs": {"anchor": str(ANCHOR.relative_to(ROOT)), "anchor_sha256": anchor_sha,
               "prices": str(PRICES.relative_to(ROOT))},
    "caps": {"existing_usd": CAP_EXISTING, "requested_usd": CAP_REQUESTED, "stop_line_usd": STOP_LINE,
             "kill_switch_usd": KILL},
    "design": "two concurrent Gemini arms (adaptive + degenerate-attacker control), 50 groups x R replicates "
              "each; the 10-05 P1-6 arms are the drift check (no new cost).",
    "anchor": anchor,
    "candidates": candidates,
    "recommended_attacker": REC,
    "budget_fallback_model": LITE,
    "stop_table": {
        "gemini-2.5-flash_with_cache": stop_table(rec_cache),
        "gemini-2.5-flash_no_cache": stop_table(rec_nocache),
        "gemini-2.5-flash-lite_with_cache": stop_table(lite_cache),
        "gemini-2.5-flash-lite_no_cache": stop_table(lite_nocache),
    },
    "resizing_order": [
        "1. Run 50 groups x 2 replicates per arm with gemini-2.5-flash if the pilot-projected total <= the "
        "stop line under the authors' cap (needs the $25 cap).",
        "2. Else run 50 groups x 1 replicate per arm with gemini-2.5-flash if that projected total <= the "
        "stop line (fits under $15 with caching).",
        "3. Else switch to gemini-2.5-flash-lite, run a fresh 10-session pilot, discard the old pilot, and "
        "apply the same table.",
        "The decision, the pilot's provider-reported mean per session, and the chosen size are recorded in "
        "manifest.json before any scored run.",
    ],
    "guard": {
        "note": "Recompute the in-flight cap for the new per-session cost: cap sessions in flight so "
                "that the stop line plus in-flight sessions at the pilot's maximum session cost stays below the "
                "kill switch. At the no-cache session cost ($%.3f) and the $%.2f stop line, the kill switch "
                "$%.2f is reached by %d in-flight sessions, so cap in-flight at that minus a margin."
                % (rec_nocache, STOP_LINE, KILL, max(1, int((KILL - STOP_LINE) / rec_nocache))),
        "max_in_flight_suggested": max(1, int((KILL - STOP_LINE) / rec_nocache) - 1),
    },
}
print(json.dumps(out, indent=1))
