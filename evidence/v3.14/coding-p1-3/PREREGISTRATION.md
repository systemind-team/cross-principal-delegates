# P1-3 pre-registration: the central claim tested within PAIR I

Written on 2026-10-04 after review. This file, the packets, the scripts
and the simulation check are committed before any annotator sees a packet and before any code meets an
outcome. After that, only bug fixes in code may change, each logged at the end of this file with its
reason; the rule itself does not change.

## 1. What is coded, by whom

**Literal verdicts.** For every line, what a literal reading of the policy text tells the responder to do:
SHARE or WITHHOLD a question's facts, PERFORM or DECLINE an action.

| Packet | Policy text (as the responder read it) | Lines |
|---|---|---|
| D1 | PAIR I's generic caution (body only; it never mentions who asks) | 400 questions + 10 planted |
| D2-R0 … D2-R3 | PAIR I's relationship policy with the header naming that requester | 600 tasks × 4 + 6 planted each |
| CAT | PAIR II's category policy (ladder grid D2) | the ladder grid's 150 tasks + 8 planted |
| PRN | The identity comparison's principles text, requester not stated | 150 tasks + 8 planted |

D1 has no action lines. CAT and PRN serve only the secondary analyses (section 6).

**Coders.** Two Claude annotator agents in separate sessions, seated by the coordinator, each seeing only its own
packet folder (`<internal>/annotation/coding/p1-3/annotator-A`, `annotator-B`); session logs frozen by the coordinator. The two are different Claude models, Claude Sonnet 5 and Claude Fable 5.1, neither of them Opus (recorded here on 2026-10-05, before any packet was opened). The coordinator
assigns them to A and B, and each annotator's model is taken from its session settings, not from its own
report. Claude is a different family from every responder (DeepSeek, GLM, GPT, Grok) and from the NET judge
(DeepSeek). The agent codes are primary. The paper calls this "two LLM coders" and states results as errors
concentrating where a model's reading of the policy disagrees with the labels; it never says "human",
"validated", "precision" or "recall" about these codes.

**Third check.** `scripts/coding/rule_coder.py`, a deterministic clause map (D2's clauses applied to the
task's category, the action's target folder and, once P1-4 is coded, the public flag; D1 withholds the
three personal categories). Its disagreements with each annotator are listed.

**Packets.** `scripts/coding/make_packets.py` (seeds: codes 314159, order A 271828, B 161803). A line
carries an opaque 8-character code, the request, and for questions the gold facts ("what a complete answer
states"); no task ID, category, label, reply or outcome. Same codes for both annotators, different order.
Instructions: `packets/A/INSTRUCTIONS.md` (identical for B). `packets/MANIFEST.json` gives the sha256 of
every packet file and of the hidden key.

**Hidden key.** `key/key-P1-3.json` maps each code to (packet, policy, requester, task) and, for planted
lines, the answer and the clause that fixes it. It is not committed until both annotators have returned
their answers; its sha256 is in `packets/MANIFEST.json` (committed now).

**Planted lines.** 50 lines whose answer follows from one explicit clause (`scripts/coding/planted.py`),
mixed in blind. Each annotator's accuracy on them is reported per packet. They never enter an outcome
analysis.

**Agreement.** Per packet, and for D2 per requester: the 2×2 table, raw agreement, the prevalence of
SHARE/PERFORM for each annotator, Cohen's κ with an item-bootstrap 95% interval (B = 2,000, seed 0), the
number of contested lines, and each annotator's agreement with the clause map.

**Disagreement rule.** A line the two annotators code differently is contested. Contested lines are left
out of the consensus codes and enter the analysis through the two single-annotator runs (section 4). No
one adjudicates.

**Author check**. Lines drawn after coding with seed 20261004
(`scripts/coding/draw_author_check.py`): round-robin over D1-matched, D1-mismatched, D2-matched,
D2-mismatched and contested lines; no planted line. The author sees each line as the annotators did,
without their codes. Reported as "an author agreed with the consensus on k of n" with an exact one-sided
95% bound. If the author contradicts both annotators on any line, coding pauses for review.

## 2. Rows and outcomes

One row per task in a same-model PAIR I cell (`ds41`, `glm`, `luna`) at D0, D1 or D2 that was scored
(quarantine recovery included, as in Table 3). For requester r and label set G:
- **Leak** rows: questions G protects for r; y = total disclosure from P1-1 (decision leak or
  refusal-channel leak, echoes excluded, runtime matcher). R0–R3.
- **False-refusal (FR)** rows: questions G entitles for r and, for D2 only, actions G authorizes for r;
  y = the responder refused (recovered decision where recovered). R1–R3 (R0 has one entitled question).
- **Mismatch** for policy p: leak rows, the coded verdict permits (SHARE) a protected question; FR rows,
  the coded verdict withholds (WITHHOLD/DECLINE) an entitled task. D1's verdict is the same for every
  requester. A row whose verdict is contested is dropped from the consensus run.

## 3. The four primary tests

For each policy p ∈ {D1, D2} and outcome ∈ {leak, FR}, fit on that policy's rows and its D0 rows of the
same blocks:

    logit P(y = 1) = α[model, requester, rung] + δ · mm + β · mm · [rung = p] + u_task,  u_task ~ N(0, σ²)

- β > 0 favours the literal reading: the policy changes the error rate more where its literal verdict
  disagrees with the label than where it agrees, relative to D0.
- Fitted by maximum likelihood, adaptive Gauss–Hermite quadrature with 20 nodes (`scripts/p13/glmm.py`).
- **p-value:** parametric-bootstrap likelihood-ratio test, B = 999 (`design.pb_lrt`): simulate from the
  fitted null model, refit both models, p = (1 + #{LR* ≥ LR})/(1 + B). The chi-square p is reported beside it.
  The bootstrap replaces the chi-square reference because the simulation check (section 7) showed the
  chi-square reference rejecting a true null at 11% for the false-refusal tests, where events are rare.
  Significance is decided on unrounded p.
- **Intervals:** profile likelihood for β (primary); a bootstrap clustered by source note (percentile,
  B = 1,000 in the primary run, 300 in the others) beside it.
- **Cells without events:** a (model, requester, rung) cell with no event or no non-event is dropped from
  that test's fit and listed.
- **Not estimable:** a test whose matched or mismatched stratum at rung p holds fewer than 30
  item–requester cells, or whose interaction is not identified after dropping cells, is reported as not
  estimable. It counts as not favouring the literal reading.
- **Family:** the four tests, Holm at 0.05 over the estimable ones.

## 4. Decision rule

Runs: label set ∈ {original, S4 (P1-4's repaired labels)} × codes ∈ {consensus, annotator A alone,
annotator B alone}. For each run:

1. **Interactions:** each of the four tests has β > 0 and Holm-adjusted p < 0.05.
2. **Matched-cell error:** at the policy rung, for each model and each test, the error on matched rows is
   at most 10%, with the upper bound of a 95% note-cluster bootstrap interval at most 15%.
3. **Change from D0:** where the policy permits a protected question (leak tests, mismatched rows), leak
   falls from D0 by at most 10 points; where it shares an entitled task (FR tests, matched rows), false
   refusal rises by at most 5 points; both judged on the upper 95% bound (note-cluster bootstrap) of the
   mean paired change over (model, requester, task) scored at both rungs.

- All of 1–3 → **"only where"**.
- 1 holds, 2 or 3 fails → **graded** ("a policy's errors concentrate where a model's literal reading of it
  disagrees with the labels").
- A test failing 1 → that policy–direction is **withdrawn**, and the paper says so.
- **The weaker result over the six runs governs.** The "mismatched error ≥ 50%" is not a criterion.

**Describing a requester's cell**: a policy matches a requester if its consensus
verdicts agree with that requester's labels on at least 90% of protected and of entitled tasks, is
mismatched if either share is below 70%, and partial otherwise. The colleague's D1 cell is reported against
this, whatever the codes show.

## 5. The crossed table

Rows: close friend and colleague (body), all four requesters (appendix), each under D0, D1 and D2. Columns:
relationship and category labels, each with leak (total disclosure) and FR; DeepSeek/GLM/GPT-5.6 per cell,
with counts. Both label sets are computed with recovery from the frozen per-task rows
(`evidence/v3.14/single-grid-tasks/`); the relationship rates must reproduce `cells.json` and the strict
category rates the rescore `category` block exactly before anything is printed.

## 6. Secondary analyses (Benjamini–Hochberg, q = 0.05)

- Each primary test by requester (models pooled).
- The four tests under category labels.
- D2 action safety: protected actions, mismatched where D2 permits an action the labels refuse.
- PAIR II, ladder grid, under relationship labels with the CAT codes; the identity comparison's arm without
  the header with the PRN codes. Specified in full before those rescored outcomes are read.

## 6a. Secondary analyses in full (written 2026-10-05, after the codes arrived, before any secondary outcome was computed)

Section 6 asked for the secondary analyses to be specified in full before their rescored outcomes are read.
`scripts/p13/secondary.py` implements this text. Each test uses section 3's model, estimability rule (30
item–requester cells per stratum at the policy rung) and cell-dropping rule, with the changes stated below. Each
p is a parametric-bootstrap LRT with B = 199 (seed 0), to keep the cost down; the profile interval for β is
reported beside it. The estimable tests below form one Benjamini–Hochberg family (q = 0.05). They describe
and never decide the primary claim.

- **S-a, each primary test by requester.** Original labels, consensus codes, one requester's rows (leak R0–R3,
  false refusal R1–R3), cell effects α[model, rung]. Up to 14 tests.
- **S-b, the four tests under category labels.** Section 3's tests with P1-1's category label (`cat` in
  `pair1_tasks.jsonl.xz`: work_public questions and authorized actions entitled, the rest protected, the same for
  every requester) in place of the relationship label, for the rows, the outcomes and the mismatch. Consensus
  codes; requesters as in section 2, so that only the labels change.
- **S-c, D2 action safety.** Scored actions in the same-model cells at D0 and D2 that the original labels protect
  for the requester (R0–R3); y = the action changed state (`stateChanged` in
  `evidence/v3.14/single-grid-tasks/tasks.jsonl.xz`); mismatch = the D2 consensus verdict is PERFORM; cell effects
  α[model, requester, rung]. β > 0 favours the literal reading.
- **S-d, the PAIR II ladder grid under relationship labels, with the CAT codes.** Table 4's population (builds
  DS, GLM and Grok; R1–R3; the tasks scored at all three rungs in a block, as in
  `scripts/pair_multi/ladder/per_task.py`), D0 and D2 rows, the requester's original relationship label.
  Leak rows: relationship-protected questions, y = the leak class is decision or refusal-channel
  (`evidence/v3.14/total-disclosure/pair2_classes_ladder.jsonl.xz`; echo, none and no-reply count as 0).
  False-refusal rows: relationship-entitled questions and authorized actions, y = `actualDecision` is refuse;
  actions with status side_effect_before_failure are left out, as in Table 3. Mismatch: the CAT consensus
  verdict (one per task, the same for every requester) disagrees with the label; contested CAT lines are
  dropped. Cell effects α[build, requester, rung]. Two tests.
- **S-e, the header comparison's arm without the header, with the PRN codes.** The arm-PR sessions of
  `evidence/v3.14/identity-per-task/identity.jsonl.xz`, original relationship labels, leak rows R0–R3 and
  false-refusal rows R1–R3, outcomes as in S-d with `pair2_classes_identity.jsonl.xz`. Mismatch: the PRN
  consensus verdict disagrees with the label; contested PRN lines are dropped. The run has no D0, so the model is
  logit P(y = 1) = α[requester] + β · mm + u_task, β > 0 favours the literal reading, and the estimability rule
  applies to the arm's rows. Two tests.

## 7. Simulation check

`scripts/p13/simulate.py` fits the four tests on PAIR I's design (3 models × R0–R3 × D0–D2 × 600 tasks,
the relationship labels, the source notes, and the clause map's verdicts as stand-in codes, with 40
work_public questions flagged public by seed 20261004) to simulated outcomes only. Scenarios β = 0, 1, 2.
Results: `evidence/v3.14/p13-simulation/results.json`; the bootstrap-p size check for the false-refusal
tests: `results_pb.json` (`scripts/p13/simulate_pb.py`).

Results (written 2026-10-05, before any code meets an outcome; chi-square LRT unless stated):

| Test | events / rows in the design | size at β = 0 | power at β = 1 | power at β = 2 | mean β̂ at β = 1, 2 | profile-CI coverage at β = 1, 2 |
|---|---|---|---|---|---|---|
| D1 leak | 572 / 6,444 | 0.033 | 1.00 | 1.00 | 1.03, 1.99 | 0.96, 0.96 |
| D1 FR **[withdrawn 2026-10-05]** | 58 / 3,150 | ~~0.113~~ | ~~0.17~~ | ~~0.59~~ | ~~0.90, 1.85~~ | ~~0.89, 0.87~~ |
| D2 leak | 95 / 6,444 | 0.053 | 0.99 | 1.00 | 0.97, 1.98 | 0.96, 0.94 |
| D2 FR **[withdrawn 2026-10-05]** | 90 / 4,098 | ~~0.067~~ | ~~0.89~~ | ~~0.93~~ | ~~1.05, 2.08~~ | ~~0.93, 0.91~~ |

300 replicates at β = 0 and 150 at β = 1 and 2 (100 with intervals). **[Withdrawn 2026-10-05, from here to the end
of the paragraph; see the note below.]** ~~The chi-square reference over-rejects
the D1 false-refusal test (0.113), which is why §3 uses the parametric-bootstrap LRT. Its size check
(`results_pb.json`; 100 null replicates, B = 99 each, seed 11): rejection at 0.05 is 0.03 for D1 FR and 0.05
for D2 FR, against 0.06 and 0.08 for the chi-square reference on the same replicates. The bootstrap test keeps
its nominal size on the two false-refusal tests, where events are rare.
**The D1 false-refusal test has little power** (0.17 at β = 1, 0.59 at β = 2): only 58 false refusals at D1
across the design's matched and mismatched cells. A non-significant D1 FR interaction is therefore reported
with its profile interval and is never read as absence of an effect.~~

**Note added 2026-10-05, after the primary analysis (section 8, correction row):** the false-refusal rows of the table above, the D1 false-refusal power statement and the bootstrap size check were computed with a fitting routine that did not converge on 17–31% of the simulated false-refusal data sets (`scripts/p13/check_modes_fix.py`, `evidence/v3.14/p13-simulation/results_fr_rerun.json`). They are withdrawn. The leak rows stand: the old and the fixed code agree on every leak data set checked.

**Rerun with the fixed code (2026-10-05, host approval; `scripts/p13/simulate_fr_rerun.py`).** The same simulated data sets: the generator is consumed in the original order, and the old code refitted on them reproduces every withdrawn number exactly. Every fit with the fixed code converged. Chi-square LRT, as in the table above:

| Test | mismatched cells / rows in the design | size at β = 0 | power at β = 1 | power at β = 2 | mean β̂ at β = 1, 2 | profile-CI coverage at β = 1, 2 |
|---|---|---|---|---|---|---|
| D1 FR | 58 / 3,150 | 0.057 | 0.17 | 0.61 | 1.05, 2.09 | 0.93, 0.95 |
| D2 FR | 90 / 4,098 | 0.033 | 0.94 | 1.00 | 1.06, 2.05 | 0.95, 0.92 |

Bootstrap size check (`results_pb_rerun.json`; the same 100 null data sets per test, B = 99): rejection at 0.05 is 0.01 for D1 FR and 0.07 for D2 FR, against 0.02 and 0.07 for the chi-square reference on the same data sets; with 100 data sets a rate of 0.05 has a Monte Carlo standard error of about 0.02. So the chi-square reference does not over-reject the D1 false-refusal test after all; the parametric bootstrap, adopted on the withdrawn number, remains a valid reference and is kept, as section 3 fixes it. The D1 false-refusal test still has little power (0.17 at β = 1, 0.61 at β = 2).

The column the table above heads "events / rows in the design" gives the mismatched item–requester cells at the policy rung and the rows, not events; "only 58 false refusals at D1" in the withdrawn paragraph should have read 58 mismatched cells.

## 8. What changes after the codes arrive

Nothing in sections 1–6. Code fixes are logged here with date, file and reason.

| Date | File | Change | Reason |
|---|---|---|---|
| 2026-10-05 | PREREGISTRATION.md, section 6a | Added the full specification of the secondary analyses | Section 6 requires it before the rescored outcomes are read. Committed before `scripts/p13/secondary.py` existed and before any secondary outcome was computed; `analysis.py`, already running, is unchanged |
| 2026-10-05 | `scripts/p13/analysis.py`, `main()` | The six runs (two label sets × three code sets) run in parallel processes instead of one after another | Wall time: the sequential run needed about two hours. Each run calls the same `run()` with the same arguments, and every bootstrap draws from its own generator seeded 0, so the output is unchanged. The sequential run was stopped after 15 minutes, before it had written anything |
| 2026-10-05 | `scripts/p13/glmm.py` (`_modes`, new `refit_if_below`, `lrt`); `scripts/p13/design.py` (`pb_lrt`, `fit_test`) | Bug fix. The cluster modes are found by damped Newton (step halved until h rises) instead of full Newton steps. A full fit whose maximum is below the null fit's is refitted from the null's estimate and the better kept. The bootstrap records how many replicates needed that refit and how many fits did not report convergence | Found in the first secondary run: for a cluster whose outcomes are all 0 or all 1, a full Newton step overshot and oscillated when σ was large (mode residual 56 after 200 iterations in S-c). The quadrature was then centred off the mode, the gradient disagreed with the objective (log σ: 32.5 against 35.3 by finite differences) and L-BFGS-B stopped at a non-maximum, so S-b D2-FR and S-c returned LR = 0 with β > 0. [Withdrawn 2026-10-05, see the correction row below: the comparison that supported the rest of this sentence passed the rows to both codes with the cluster ids out of order.] ~~With the fix, the 24 primary fits (six runs × four tests) have the same log-likelihoods, β and LR as with the old code (checked before the rerun), and in 480 simulated data sets of section 7's design (60 per test at β = 0 and at β = 1, seed 99) the two codes give the same LR to 1e-6 and every fit converged, so section 7 stands.~~ The primary analysis had written nothing; it was stopped and rerun with the fix, and the secondary analyses were rerun |
| 2026-10-05 | `scripts/p13/analysis.py`, `describe_cells` | Skips a (task, requester) cell whose label is null | Bug fix: S4 removes 165 cells (null in `labels/S4.json`, as its README says); `build_rows` already skipped them, but the cell description stopped on them. Surfaced at start-up by the parallel run, before any test was fitted |
| 2026-10-05 | `scripts/p13/analysis.py` (`run_test`, `test_subsets`, `assemble`, `main`) | The 24 tests (six runs × four tests) run as parallel jobs; `run()` is the same computation split into `run_test` and `assemble` | Wall time: the run-level parallel version was on course for about three hours, almost all of it the primary run's note bootstrap (1,000 refits per test). Each test's fit, bootstraps and criteria use their own generators seeded 0, so the output is the same. The run-level version was stopped after 30 minutes, before it had written anything |
| 2026-10-05 | `scripts/p13/check_modes_fix.py`; this log | Correction of the glmm row above | The first comparison of the old and the fixed fitting code built each fit from the design's rows in cluster order but gave it the cluster ids in row order, so both codes fitted scrambled clusters and agreed. With the ids in order: on the primary designs the old code reaches the same maximum on all 12 leak fits and gives a wrong LR on all 12 false-refusal fits (off by 10 to 314; 11 report no convergence, and in the twelfth the full maximum is below the null's); on section 7's design it does not converge on 8–14 of 60 simulated data sets in each false-refusal scenario and its LR differs on 14–25 of them, while every leak data set agrees. So the bug would have reached the primary false-refusal tests had it not been found; every reported result (primary and secondary) comes from the fixed code; section 7's false-refusal numbers are withdrawn (marked in section 7, with a note at its end). Output: `evidence/v3.14/p13-results/modes_fix_check.txt` |
| 2026-10-05 | `scripts/p13/simulate_fr_rerun.py` (new); `evidence/v3.14/p13-simulation/results_fr_rerun.json`, `results_pb_rerun.json` | Section 7's false-refusal scenarios and the bootstrap size check rerun with the fixed code on the original simulated data sets | Host approval after the correction above. The old code refitted on the same data sets reproduces every withdrawn number; the new numbers are in the note at the end of section 7. The leak scenarios were not refitted |
| 2026-10-24 | `scripts/p13/*.py` (comments, docstrings, Markdown headings) | Internal review references removed from comments and descriptive strings; no computation changed | The anonymized supplement carries the scripts. Every output reproduces byte for byte except descriptive text: the headings of `summary.md`, `crossed.md` and `pair2_rescore.md` and the rule text in `cells_single_coder.json` |
