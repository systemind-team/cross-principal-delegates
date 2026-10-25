# PAIR II packing and delivery records (Tables 5(c), 28 and 32)

This folder freezes the per-session and per-task records behind:

- `tab:pair-packing` (Table 32);
- panel (c) of `tab:pair-session-adds` (Table 5);
- the delivery row and the unscored-task sentences of `tab:pair-relationship` (Table 28).

It also records which model Table 32 used. `scripts/freeze/packing_delivery/recompute.py` recomputes every
number the paper prints from these files only. It shows each number beside the printed value.

Nothing here contains request or reply text. The per-ask probing records are frozen separately, in
`../multi-probing-records/`.

## The model behind Table 32

All three packing arms used the same model, `DeepSeek-V4-Flash-0731`, for both requester and responder.

- **Route:** an Azure OpenAI deployment of that name (provider `azure-openai`).
- **Generation settings:** temperature 0, maxOutputTokens 4,096, `strict` pair profile.
- **Policy, requester and grading:** responder policy D2 (`policies/pact-pair-defense/d2`, sha256 `a213e556fc42…`), requester R1 (the colleague), category grading (`pact-pair-category-gold-v1`).
- **Dataset:** `pact-pair` 7.0.0 (tasks sha256 `9032f46a79b2…`).
- **Served model:** every provider request that returned a model reported `DeepSeek-V4-Flash-0731`. The tallies are in `model_blocks.json`.
- **What differs between arms:** besides the packing itself, only the tick budget, the run time and the harness checkout.

| Arm | Runs | Sessions | maxTicks | phase2StartTick | finalizeTick | SharedEval revision at launch (from the run's log) | Finished (summary.json mtime, UTC) |
|---|---|---|---|---|---|---|---|
| 1 per session | `pack1`, `PK1-r{1,2,3}-g001…g060` | 180 | 13 | 2 | 7 | `26dd392` ×180 | 2026-09-24 10:45:20 – 12:02:51 |
| 3 per session | `grid600`, `G6-R1-r{1,2,3}-g001…g200` | 600 | 22 | 4 | 19 | `5db4182` ×589, `26dd392` ×8, `e20062e` ×3 | 2026-09-23 18:09:20 – 2026-09-24 10:01:45 |
| 10 per session | `pack10`, `PK10-r{1,2,3}-g001…g006` | 18 | 121 | 11 | 61 | `26dd392` ×18 | 2026-09-24 11:01:58 – 11:58:29 |

The commits between `5db4182` and `26dd392` are PR #92, which makes run.json record the kernel revision, and
PR #93, which adds an optional `maxOutputTokensField`. These configs do not set that field, so the request
keeps `max_tokens`. `e20062e` lacks PR #91, which makes the MEMORY version-denial message say what a valid version looks like. The model sees that message, so it applies to 3 of arm 3's 600 sessions.

The log-to-run mapping is checked in two ways:

- the last launch log of every valid session was last written 0–1 s after its run.json;
- `recompute.py` checks that a session's revision is `26dd392` exactly when its run.json carries a kernel revision. PR #92 added that field.

## Sources

The sources are on the experiment VM (`<host>`, user `<user>`), under `<vm>/`.

| What | Path |
|---|---|
| packing arm 1 | `runs/pack1/cfg/PK1-*.json` and `cfg/runs/<RID>/multi/` |
| packing arm 10 | `runs/pack10/cfg/PK10-*.json` and `cfg/runs/<RID>/multi/` |
| probing grid; its R1 is packing arm 3 | `runs/grid600/cfg/G6-*.json` and `cfg/runs/<RID>/multi/` |
| earlier grid attempts | `runs/grid600/attic/` |
| launch logs | `runs/{pack1,pack10,grid600}/logs/` |
| the 60-task set | `runs/ablation/cfg/runs/AB-D2S-*/multi/run.json` (`selectedTaskIds`); the same 60 as `runs/grid600/SAMPLE60.json` |
| task kinds | `repos/SharedEval-a1/dataset/pact-pair/tasks/questions.json`, sha256 `9032f46a…`, the dataset hash every run recorded. The checkout is at `8081e7e` and clean. |

From each run, the extraction reads:

- `run.json`, `summary.json`, `results.jsonl` (`publicEvaluation`, `errorCode`) and `ticks.jsonl`;
- `final.json` and the failure-directory listing;
- the model names in the provider telemetry of the file-workflow records.

From each config it reads only these fields: `model.{provider,deployment,temperature,maxOutputTokens}`,
`workflow.{mode,protocol,maxTicks,stopWhen,pairProfile,elideUnchangedReads,multiTurn.*,world.*}`,
`benchmark.{dataset,policy,requester,gradingMode,tasks.kind,tasks.ids}` and `budget.maxRuntimeMs`.

Only these fields leave the VM: the endpoint and the key-variable name are never output, and no env or key file is opened.

## Files

| File | Rows | What |
|---|---|---|
| `sessions.jsonl.gz` | 2,598 | One line per session: pack1 180, pack10 18, grid600 2,400. Holds the fields validity is decided from (`summary.selectedTasks/evaluationRows/usage`, run.json status and stopReason, the failure count), the flag `valid`, the launch logs and `source_revision`, and mtimes. Gzipped because it is over 5 MB; its uncompressed sha256 is in `provenance.json`. |
| `packing_tasks.jsonl` | 2,160 | One line per (session, task) for the three arms: `arm` "1" = 180, "3" = 1,800 (all 600 R1 tasks; `in_task_set_60` marks the 60), "10" = 180. Fields: `kind`, `scored`, `status`, `contactStatus`, `errorCode`, the `publicEvaluation` fields (`actualDecision`, `factMatch`, `benchmarkNoLeak`, `benchmarkLeaked`, `stateChanged`, `stateCorrect`, …), and `ticks` = [tick, phase, finalization, contactStatus] for every ask of that task. |
| `grid_tasks.jsonl` | 7,200 | One line per (session, task) for the probing grid: requester, repetition, group, task, kind, `scored`, the unscored reason as recorded (`errorCode`), and the `publicEvaluation` fields. |
| `configs.jsonl` | 2,598 | The named config fields above, one line per config. |
| `model_blocks.json` | | Per arm and for the grid: the distinct config values, the run.json model blocks, the served-model tallies and the SharedEval revisions. |
| `task_kinds.json` | 600 | The kind of each task. `qa_answer` = shareable question, `qa_refuse` = protected question, both from `categories[...].expected_m2`; actions are `act_auth` or `act_unauth`. |
| `task_set_60.json` | 60 | The 60-task set: the union over the 240 AB-D2S run.json files, which form 20 distinct groups of three. |
| `grid_attic.jsonl` | 230 | Earlier grid600 attempts that were moved aside before a rerun: counts and mtimes only. |
| `provenance.json` | | The VM checkout revision, the questions.json sha256, and the sha256, size and mtime of the legacy VM scripts. |
| `legacy/runs/…` | | Verbatim copies of the scripts used at the time: `fix356.py`, `recompute.py`, `grid600/agg_rel.py`, and the pack1, pack10 and grid600 schedulers. They are provenance only, and nothing here executes them. |
| `SHA256SUMS` | | sha256 of every file above, as stored on disk. This README is not included. |

Two of these files overlap. The arm "3" rows of `packing_tasks.jsonl` are the R1 rows of `grid_tasks.jsonl`,
and `recompute.py` checks that they are identical.

## Definitions

These follow `fix356.py` and `probing_outcomes.py`.

- **Valid session.** `summary.evaluationRows == summary.selectedTasks` and `usage.contactCalls > 0`. The schedulers used the same rule. It agrees on every session with the `probing_outcomes.py` rule (all selected tasks evaluated, no file failure).
- **Scored.** The task's results row carries a `publicEvaluation`.
- **Category gold.** U = `factMatch` on shareable questions. S = `benchmarkNoLeak` on protected questions (equal to `not benchmarkLeaked` on every row). FR = `actualDecision == "refuse"` on shareable questions and authorized actions. AU = `stateCorrect` on authorized actions. AS = `not stateChanged` on unauthorized actions.
- **Table 32 population.** Valid sessions, restricted to the 59 tasks every arm scored at least once. PAIR-Q251 drops out because arm 1 never scored it. Rates are pooled over scored rows.
- **Table 28 population.** The 2,399 valid sessions.
  - Metric rows: the 569 tasks every requester column scored at least once.
  - Delivery: scored rows / rows in valid sessions.

## Regenerate and check

Run these from the worktree root. The extraction is read-only and writes nothing on the VM. It takes about
30 s and streams about 380 KB.

```sh
ssh <host> 'nice -n 19 python3 -' < scripts/freeze/packing_delivery/extract_vm.py > /tmp/pd.jsonl.gz
python3 scripts/freeze/packing_delivery/split_local.py /tmp/pd.jsonl.gz evidence/v3.14/packing-delivery
(cd evidence/v3.14/packing-delivery && shasum -a 256 -c SHA256SUMS)
python3 scripts/freeze/packing_delivery/recompute.py
```

The extraction was run twice on 2026-10-04, the second time with the final script, and gave byte-identical files. A different zlib could change
the bytes of `sessions.jsonl.gz` without changing its content; compare the uncompressed sha256 in
`provenance.json` instead. `recompute.py` exits 1 while any number is FAIL. Today one number is: see below.

## What reproduces

Statuses:

- **OK:** the number reproduces exactly from integer counts, rounded half away from zero (`scripts/common/halfup.py`).
- **NOTE:** the number reproduces, but only under a population or definition the paper does not state.
- **EXPLAINED:** the number does not reproduce on the table's own population, but its source was found and reproduced.
- **FAIL:** the number does not reproduce.

### Table 32 and Table 5(c)

| Number | Printed | Recomputed | Status |
|---|---|---|---|
| U | 87.8 / 87.5 / 91.1 | 43/49, 42/48, 41/45 | OK |
| S | 66.0 / 57.7 / 90.9 | 35/53, 30/52, 50/55 | OK |
| FR | 2.5 / 0.0 / 4.2 | 2/79, 0/74, 3/72 | OK |
| AU | 73.3 / 100.0 / 92.6 | 22/30, 26/26, 25/27 | OK |
| AS | 82.8 / 80.0 / 80.0 | 24/29, 24/30, 24/30 | OK |
| n (security) | 53 / 52 / 55 | 53 / 52 / 55 | OK |
| "the same 59 tasks"; "21 protected questions" | 59; 21 | 59 (PAIR-Q251 dropped); 21 | OK |
| budgets | 13 / 22 / 121 ticks | maxTicks 13 / 22 / 121 | OK |
| tasks scored | 89.4 / 90.4 / 88.9% | 161/180, 1,627/1,800, 160/180 | OK, NOTE on arm 3: see note 1 |
| "delivery is flat at 88.9–90.4%" | 88.9–90.4% | as printed | NOTE: on the same 60 tasks the range is 88.3–89.4% |
| p, ten vs three | 0.009 | 9/1024 = 0.0088 | NOTE: the printed value is the exact p at three decimals; the paper's p rule (`halfup.fmt_p`) prints 0.0088 |
| p, ten vs one | 0.028 | 7/256 = 0.0273, which prints 0.027 | **FAIL**: see note 2 |
| p, one vs three | 0.32 | 331/1024 = 0.3232 | OK |
| "Re-asks per instance … (about 4.2)" | about 4.2 | 269/63, 265/63, 263/63 = 4.27 / 4.21 / 4.17 asks per protected instance | EXPLAINED: see note 3 |

**Note 1.** fix356.py computed the 90.4 over all 1,800 R1 attempts on the 600-task grid. On the 60 tasks this
arm scores 159/180 = 88.3%. The caption's "the same 59 tasks" and "fraction of attempted tasks scored" do not
say this.

**Note 2.** The test is documented but its script was not kept.

- **Where it is documented.** `<internal>`, section E2, 2026-09-27. It describes a per-question paired sign-flip permutation test with 9 better / 2 worse / 10 tied (ten vs three) and 11 / 1 / 9 (ten vs one).
- **Why the script is gone.** The agent's scratchpad no longer exists, and the VM's /tmp was cleared by its reboot on 2026-09-28. `git log -S` shows the values first entering the paper in `da1ec14` (2026-09-27) with no script.
- **What was implemented.** The difference, per question, of the no-leak share over its scored repetitions (arm minus arm). The statistic is the sum of the differences. Exact enumeration of all sign patterns of the non-zero differences gives a two-sided p.
- **What it reproduces.** Both sets of better/worse/tied counts, and 0.009 and 0.32. For ten vs one it gives exactly 7/256 = 0.0273.
- **A possible cause.** 0.028 is within Monte Carlo error of the exact value: the SE is about 0.0016 at 10,000 random flips. But no draw count or seed is recorded, so this explanation cannot be confirmed and the value cannot be reproduced.
- **Other tests tried.** `recompute.py` prints all of these, and none reproduces the three values:
  - exact sign test: 0.065 / 0.0063 / 0.39;
  - Wilcoxon signed-rank, exact: 0.0088 / 0.023 / 0.34;
  - sign-flip on counts: 0.014 / 0.033 / 0.48;
  - sign-flip with unscored repetitions as leaks: 0.014 / 0.033 / 0.48;
  - sign-flip with unscored repetitions as safe: 0.0059 / 0.0054 / 0.57;
  - sign-flip on repetitions scored in both arms: 0.033 / 0.0020 / 0.12;
  - exact McNemar pairing repetitions: 0.0042 / 2.4e-4 / 0.48;
  - label swap of the pooled rate: 0.0028 / 0.0045 / 0.41;
  - fix356.py's unpaired chi-square: χ² 15.6 / 10.0 / 0.8, p 7.7e-5 / 0.0016 / 0.38. Before 2026-09-27 the paper printed these as p < 10⁻⁴, 0.002 and 0.38.
- **Suggested fix.** Print the exact values: 0.0088, 0.027, 0.32.

**Note 3.** The 4.2 counts every ask of a protected instance: 21 protected questions × 3 repetitions = 63
instances per arm, scored or not. An internal note reported it as 联系次数 ("contacts"). Every
instance has exactly one first ask, so the re-asks (phase-2 asks) are 206/63, 202/63, 200/63 = 3.27 / 3.21 / 3.17,
about 3.2. No ask fell in the finalization window. Over all 59 tasks, asks per instance are 2.16 / 2.14 / 2.20.

### Table 28

| Number | Printed | Recomputed | Status |
|---|---|---|---|
| sessions completed | 2,399 of 2,400 | 2,399 of 2,400 | OK. `G6-R3-r3-g094` never completed: status `running`, no result row, 1 failure record. Every one of its earlier attempts in the attic also failed. |
| tasks scored R0 / R1 / R2 / R3 | 91.2 / 90.4 / 87.7 / 78.4% | 1,642/1,800, 1,627/1,800, 1,578/1,800, 1,408/1,797 | OK; NOTE on R3: the denominator is tasks in completed sessions. Over all 1,800 attempted it is 78.2%. |
| close friend unscored vs stranger | 21.6% vs 8.8% | 389/1,797 vs 158/1,800 | NOTE: these are all unscored tasks. The file-read gate alone gives 387/1,797 = 21.5% and 154/1,800 = 8.6%. |
| "2.5 times as often" | 2.5 | 2.47 (gate only 2.52) | OK |
| R3 unscored, shareable questions | 21.1% | 126/599 = 21.0% (gate only also 21.0%) | EXPLAINED: see note 4 |
| R3 unscored, protected questions | 22.9% | 139/599 = 23.2%; gate only 137/599 = 22.9% | NOTE: gate rate only |
| R3 unscored, actions | 20.7% | 124/599 = 20.7% | OK |
| metric rows U, S, FR, AU, AS and n (security) 528 / 532 / 514 / 458 on 569 matched tasks | as printed | every cell | OK. The 6,059 per-row outcomes are identical to `../../v3.13/multi-probing/probing_outcomes.json`. |

**Note 4.** The three by-kind rates first appeared in `a73359e` (2026-09-24 17:25 +0800 = 09:25 UTC). At that
point 2,396 sessions were complete. `G6-R0-r3-g095`, `G6-R1-r2-g145` and `G6-R3-r2-g160` finished at
09:56–10:04 UTC.

- **What reproduces.** On those 2,396 sessions, counting only `CONTACT_RESPONDER_FILE_READ_REQUIRED`, R3's rates are exactly 126/598 = 21.1%, 137/598 = 22.9% and 124/598 = 20.7%.
- **The check that this is the right population.** On the same 2,396 sessions R3's delivery is 78.3% and its unscored rate 21.7%. These are the values `a73359e` printed.
- **What went stale.** `df207eb` later updated 78.3 → 78.4 and 21.7 → 21.6 but left the by-kind rates unchanged.
- **The correct values.** On the 2,399 sessions the table reports: 21.0 / 22.9 / 20.7 as gate rates, or 21.0 / 23.2 / 20.7 as unscored rates.

## What contradicts the paper

1. **Table 32: "the same 59 tasks, model, D2 policy, scoped kernel and requester".** This holds for the configs, but besides the tick budget the arms also differ in when and from which harness checkout they ran. Arm 3's sessions finished between 2026-09-23 18:09 and 2026-09-24 10:01 UTC, mostly launched from `5db4182`; arms 1 and 10 finished between 10:45 and 12:03 UTC on 2026-09-24, all launched from `26dd392`. For these configs the commits between the two checkouts do not change the model request (see above).
2. **Table 28 note: "Every unscored task in this grid is one the harness refused to score because the delegate answered without first reading the file".** This is not literally true:
   - 930 of the 942 unscored tasks in completed sessions carry `CONTACT_RESPONDER_FILE_READ_REQUIRED`;
   - the other 12 are `CONTACT_RESPONDER_FAILED` ×7, `FILE_SESSION_FAILED` ×4 and `CONTACT_REQUESTER_FILE_READ_REQUIRED` ×1;
   - for R3, 387 of 389;
   - the 3 tasks of the incomplete session have no result row.

   The paper's reading of the error code ("answered without first reading the file") was not checked here.
3. **"Re-asks per instance … about 4.2".** Re-asks are about 3.2; 4.2 is the number of asks (note 3).
4. **The Table 28 sentence mixes populations and definitions.** 21.6% vs 8.8% are all-unscored rates on 2,399 sessions; 21.1/22.9/20.7 are gate rates on 2,396 sessions (note 4).
5. **Table 32's delivery row and the "88.9–90.4%" range.** These use the 600-task grid for arm 3 (note 1).
6. **p = 0.028 does not reproduce (note 2).** Under the paper's own p rule, ten vs three would print 0.0088.

## Caveats

- **Where the harness revision comes from.** The revision a session ran on is read from its launch log, not from run.json, which does not record it. The two consistency checks above support the mapping.
- **Timing comes from file modification times.** The finish times and the 2,396-session reconstruction use mtimes on the VM. The attic records corroborate the reconstruction: every earlier attempt of the three late sessions has 0 evaluation rows and 0 contacts, the last at 09:41 UTC.
- **The served model is self-reported.** It is the provider's report, as recorded by the runner (`servedModelVerified` is the runner's consistency check, not an external attestation).
