# PAIR I supplement with Grok 4.6: reproduction and the paper's table

<user>'s run and analysis are in `../../v3.13/single-grid-grok/` (PR #17; `RESULTS.md`, `grok_supplement.json`) and
`scripts/single_grid/grok/`. Nothing there is modified.

| File | Script | What |
|---|---|---|
| `reproduce.json` | `scripts/single_grid/grok/reproduce.py` | `analyze.py` and `render_results.py` re-run in a temporary mirror of the repository from the frozen files: the 66,000 PAIR I rows from `../single-grid-tasks/tasks.jsonl.xz` (SHA-256 195f90e1…, the digest `common.py` fixes) and the grok run evidence. `grok_supplement.json` and `RESULTS.md` come out byte-identical. |
| `macros.json` | `scripts/single_grid/grok/render_tex.py` | every `\groknum{key}` value |
| `table4_measure.json` | `scripts/single_grid/grok/table4_measure.py` | the supplement under Table 4's total leak (refusal-channel echoes excluded), the pre-registered results kept primary: the random set's total-leak rates, F1, F2 and F3 on the pre-registered units, and the hard set that rule would have chosen |
| `grok_matches.jsonl.gz` | same, `--rebuild-matches` (runs `scripts/p11/match_pair1.mjs`) | the total-leak scoring matcher over every Grok 4.6 question row: the gold facts in the reply and in the context |

`render_tex.py` also writes `tables/single_grok.tex` (`tab:single-grok`) and `tables/grok_numbers.tex`. Rates print
half away from zero from their counts. Every printed p is recomputed as an exact McNemar p from the discordant counts
and Holm-adjusted within its pre-registered family (F1 12 tests, F2 18, F3 6); both are checked against `analyze.py`'s
values. Delivery and spend are counted as `render_results.py` counts them and checked against `RESULTS.md`.

Two statements in `RESULTS.md` are typed rather than computed. "F2 can only detect differences of about 20 points" is
the design note's approximation (`planning/2026-10-05-pair1-grok-supplement.md`, "Power"), so it has no macro; the
unit counts behind it do (`units-<R>-<tl|fr>`). "2 of its refusals carried a gold fact" is computed here from the
run's refusal scans (`refusal-gold`, `refused`).

Regenerate: `python3 scripts/single_grid/grok/reproduce.py && python3 scripts/single_grid/grok/render_tex.py`.

**The measure.** The supplement's pre-registered total leak counts a refusal as a leak when the refusal
scan (Appendix C.8's historical matcher) finds a gold fact in it, echoes included. Table 4's total leak counts a
refusal only when the scoring matcher finds a gold fact the context (policy plus request) does not already hold. The
pre-registered values stay primary. `table4_measure.py` first reproduces F1, F2 and F3 exactly under the pre-registered
measure and checks that each model's Table 4 total leak equals the total_disclosure flag on all 9,599 protected question rows of the
36 ladder cells. Under Table 4's measure, 7 of the 12 model entries at D2 in Table 30(a) fall; on the leave-one-out
pairs the three models leak 13.7%, 20.1% and 14.6% at D2 (DeepSeek V4.1 p = 0.41, GLM-5.3-Flash Holm p = 3.1×10⁻⁵,
GPT-5.6 p = 0.64); the smallest F2 Holm p is 0.28; Grok 4.6's own rates do not move (its refusal channel is 2 of 1,007
refusals under the scan and 0 under Table 4's measure); no Holm verdict changes. The hard-set rule picks 609 pairs under
the pre-registered measure and would pick 597 under Table 4's (16 only under the scan, 4 only under Table 4's).
