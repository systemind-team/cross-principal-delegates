# Relationship labels: documentation and variants

| File | Script | What it is |
|---|---|---|
| `annotation_passes.csv` | `scripts/p14/freeze_annotations.py <SharedEval clone>` | the five annotation passes of the 2026-08 campaign (SharedEval 49e043b, `pact_pair/annotation/campaign_v2/filled_v3/*.csv` with `keys_v3/`), one row per annotated row and requester; annotators renamed A1–A4 (alphabetical order of their file names, not printed) and E; probe repeats dropped (first occurrence, as the campaign's QC does) |
| `qc_v3_majority.csv`, `instructions_v2.md` | same | the campaign's majority file and the instructions annotators received, copied unchanged |
| `SOURCES.json` | same | sha256 of every source blob |
| `documentation.json` | `scripts/p14/label_variants.py` | Fleiss κ overall, by requester, by category and without E; vote splits; each pass's agreement with the majority; the tie-resolved cells; the variants' counts |
| `original.json`, `S1.json`, `S2.json`, `S5.json`, `S6.json` | same | label sets in the form the central-claim test reads; a removed cell is null |
| `applied_<variant>.json` | `scripts/p14/apply_variants.py` | Table 3, the PAIR I family's tests (Holm), the stranger's test, the friend's work questions and Table 30 under each variant, on total disclosure |

Checks: the five-pass majority (ties to protect / refuse) equals the campaign's majority file and the label file on all
2,005 annotated cells; Fleiss κ reproduces 0.587 (questions) and 0.764 (actions). Variants: S1 without the 39 cells
matrix v1.1 marked B; S2 without the 3–2 cells; S5 the four-pass majority without E (2–2 → protect, counted); S6
without the 99 transcribed rows (Q101–Q200 except Q125). S3 (public relabel and consistency pass) and S4 (S1 + S2 +
S3) are built once the public/internal codes exist (`evidence/v3.14/coding-p1-4/PREREGISTRATION.md`).

## Agreement of the five passes, on the requesters the experiments use (2026-10-23)

`scripts/p14/agreement.py` → `agreement.json` (every figure below and more), `agreement_macros.json` and
`tables/label_agreement_numbers.tex` (`\agreenum{key}`), and `tables/label_agreement.tex` (`tab:label-agreement`,
for Appendix C: the two scopes, each requester and each category). Statistics per set of cells, each rated by the five passes:
Fleiss' κ, Gwet's AC1 (two categories per scale) and raw agreement (the mean share of agreeing pairs of passes).

**Primary: R0–R3.** Every PAIR experiment uses these four requesters. R4, the fifth persona, enters no experiment, so
its labels never score a model, and the primary figure leaves it out. No other cell is dropped.

| R0–R3 | Cells | Fleiss κ | Gwet's AC1 | Raw agreement |
|---|---|---|---|---|
| Questions | 1,204 | 0.708 | 0.735 | 0.861 |
| Actions | 400 | 0.739 | 0.768 | 0.877 |
| Both, protect vs permit | 1,604 | 0.716 | 0.743 | 0.865 |

**Secondary: all five personas, R0–R4** (the figures the paper printed before): questions κ 0.587 (AC1 0.636, raw
0.807), actions κ 0.764 (AC1 0.827, raw 0.900). Leaving out R4 raises question κ and lowers action κ: R4's questions
are the least agreed of any requester (κ 0.045, raw 0.589), and 99.6% of its action ratings refuse (κ −0.004 at raw
0.992), which raises the pooled action agreement.
Without E: R0–R3 0.674 (questions) and 0.693 (actions); R0–R4 0.568 and 0.722.

**Per requester** (κ / AC1 / raw; share of protect ratings):

| Requester | Questions | Actions |
|---|---|---|
| R0 stranger | 0.118 / 0.928 / 0.934; 96.1% | undefined / 1.000 / 1.000; every rating refuses |
| R1 colleague | 0.641 / 0.693 / 0.835; 35.9% | 0.182 / 0.695 / 0.778; 16.2% |
| R2 CEO's assistant | 0.696 / 0.782 / 0.873; 29.7% | 0.380 / 0.522 / 0.730; 32.0% |
| R3 close friend | 0.316 / 0.724 / 0.803; 82.6% | undefined / 1.000 / 1.000; every rating refuses |
| R4 (no experiment) | 0.045 / 0.278 / 0.589; 68.6% | −0.004 / 0.992 / 0.992; 99.6% |

R0's κ is low through the prevalence paradox: 96% of its question ratings protect, so κ is near 0 at 93% raw
agreement, which AC1 (0.928) shows. κ is undefined where every rating falls in one category.

**Per category, R0–R3** (κ / AC1 / raw; cells): work_public 0.757 / 0.757 / 0.878 (800); personal_relationships
0.573 / 0.831 / 0.879 (104); personal_health 0.451 / 0.798 / 0.853 (80); sensitive_work 0.322 / 0.596 / 0.747 (124);
personal_finance 0.112 / 0.823 / 0.852 (96); actions authorized_create 0.777 / 0.800 / 0.895 (188), authorized_edit
0.709 / 0.742 / 0.863 (180), authorized_complete 0.678 / 0.719 / 0.850 (32). The R0–R4 values are in `agreement.json`.

**One pooled figure, corrected.** An earlier figure for questions and actions together, κ 0.799 and AC1 0.826,
pools P, L, REFUSE and EXECUTE as four categories. That counts the question/action split, which every pass gets right
by construction, as agreement, so the pooled κ sits above both of its parts. On the binary scale (protect: P, REFUSE;
permit: L, EXECUTE) it is κ 0.716 and AC1 0.743; raw agreement is 0.865 either way. `agreement.json` keeps both,
labelled; use the binary one if a pooled figure is printed.

Checks in the script: the all-persona κ equals `documentation.json`, and the independently computed figures of
2026-10-23 reproduce at three decimals.
