# The central claim tested within PAIR I: results

The pre-registration is `../coding-p1-3/PREREGISTRATION.md` (sections 1–7 committed before any coder opened a
packet; section 6a before any secondary outcome was computed; every later code change is in its section 8 log).
Inputs: the coders' answers, the frozen sessions and the key in `../coding-p1-3/`, the label sets in `../labels/`,
the total-leak per-task outcomes in `../total-disclosure/`, and the PAIR II per-task records in `../ladder-per-task/` and
`../identity-per-task/`.

| File | Script | What |
|---|---|---|
| `results.json` | `scripts/p13/analysis.py` | agreement and planted lines; the four tests, criteria 2 and 3 and the decision for each of the six runs (original and S4 labels × consensus, annotator A, annotator B); the weaker result, which governs; the pre-registered cell descriptions |
| `summary.md` | `scripts/p13/summarize.py` | the decision (the pre-registered run-level rule, and the same criteria per policy-direction) and every criterion's numbers, from `results.json` |
| `secondary.json` | `scripts/p13/secondary.py` | section 6a's tests S-a to S-e, BH over the estimable ones |
| `crossed.json`, `crossed.md` | `scripts/p13/crossed.py` | section 5's crossed table, after reproducing 216 frozen numbers |
| `pair2_rescore.json`, `.md` | `scripts/p13/rescore_pair2.py` | the PAIR II ladder grid under the relationship labels and the header comparison under the category labels, after reproducing the published numbers; the splits by the CAT and PRN verdicts |
| `macros.json` | `scripts/p13/render_tables.py` | every `\pthreenum{key}` the paper prints (`tables/p13_numbers.tex`), with the tables `p13_*.tex` and `pair2_rescore.tex`; shares and rates from their counts, half away from zero; a `-up` key is the same bound rounded towards +infinity |
| `cells_single_coder.json` | `scripts/p13/render_tables.py` | the pre-registered cell description with the consensus codes (equal to `results.json`) and with each coder's codes alone: the same status in all 8 cells on the original labels; on S4, coder A alone makes the stranger's D2 cell mismatched (4 of 6 entitled tasks shared) |
| `modes_fix_check.txt` | `scripts/p13/check_modes_fix.py` | the old and the fixed fitting code side by side: they agree on every leak fit; the old code gives a wrong LR on all 12 primary false-refusal fits and on 14–25 of 60 simulated data sets per false-refusal scenario (PREREGISTRATION section 8, correction row) |

Regenerate (about an hour on eight cores for `analysis.py`):

```
python3 scripts/p13/analysis.py && python3 scripts/p13/summarize.py
python3 scripts/p13/secondary.py
python3 scripts/p13/crossed.py
python3 scripts/p13/rescore_pair2.py
python3 scripts/p13/render_tables.py
```

The codes come from two LLM coders (Claude Sonnet 5.5 and Claude Fable 5.1; the paper's Appendix C.9 describes their sessions).
They are agent codes, not human annotation.
