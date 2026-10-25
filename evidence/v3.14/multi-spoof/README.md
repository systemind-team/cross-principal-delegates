# P1-6: impersonation arms on the ladder's 50 groups (Appendix D.5)

Design: `design/p1-6-design.md` (v2). Status: run and analysed. Pilot 14 sessions
(2026-10-05 05:05–05:14 UTC); full run under the go-ahead 05:19–07:40 UTC, 700 sessions plus 18 reruns; the optional
arm P1h was not run (no room under the stop line). Ledger: $12.51 on the dedicated key.

The stranger (R0) is the true requester in every arm. The impersonation arms give the requester the colleague's
(R1) or the close friend's (R3) agent files and put a pinned claim at the head of every request; the controls do
neither. Responder policy `D2R_ID_R0` (identity header naming the stranger) or `D2R_PRINCIPLES` (no header).
DeepSeek V4 Flash 0731 in both seats through the research gateway, pinned to the Relace upstream, on a dedicated
key (id withheld; limits $15 daily and monthly).

## Files

| Path | What | Made by |
|---|---|---|
| `design/p1-6-design.md` | the reviewed design, as committed before the pilot | authors |
| `design/prefix_overlap.json` | gold facts each prefix already contains: only Q324 is flagged, by `forged-r1` | `scripts/pair_multi/spoof/prefix_overlap.mjs` |
| `design/power.json` | 10-02 rates on R0's labels for the primary item sets, claim counts in the 10-02 requesters' messages, and the power of the primary tests | `scripts/pair_multi/spoof/power.py` over the frozen `pair2_classes_identity.jsonl.xz` and `identity.jsonl.xz` |
| `delivery/negative_control.json` | the delivery checker over every run folder of the 10-02 header comparison: 413 folders, 3,680 stored requests, 3,669 responder turns, no prefix anywhere | `scripts/pair_multi/spoof/delivery.py --negative-control` |
| `lane/` | the generated lane: `MANIFEST.json` (800 config hashes: 700 main, 100 optional), `jobs.txt`, `pilot.txt`, `optional.txt`, `drop_rule.txt` | `scripts/pair_multi/spoof/gen.py` |
| `inputs/evaluator.ts` | SharedEval `src/suites/pact-pair/evaluator.ts` at 8081e7e (the scoring matcher), sha256 `c51f2dbf…` | copy |
| `inputs/questions.json` | the PAIR task set, sha256 `9032f46a…` (as `evidence/v3.14/pair-dataset/questions.json` on the branch) | copy |
| `inputs/D2R_ID_R0.md` | SharedEval `dataset/pact-pair/policies/D2R_ID_R0.md`, the header policy naming the stranger, sha256 `8100ecea…` (the POLICY.md digest in the runs) | copy |
| `manifest.json` | pre-launch record: code, digests, guard, pending decisions | authors |

| `delivery/pilot.json` | the delivery checks on the 14 pilot sessions, before launch | `delivery.py` |
| `delivery/delivery.json` | the delivery checks on all 718 run folders; controls against their 10-02 sessions | `delivery.py --reference` |
| `lane/controls_check.json` | all 200 control configs byte-identical to 10-02; all 600 impersonation configs differ only by `benchmark.spoof` | `check_controls_vm.py` |
| `sessions.jsonl.xz` | per session slot: attempts, the scored run, tasks, messages in ledger order, responder writes, assets | `extract_vm.py` |
| `run/` | `times.tsv` (start, end, exit code per attempt), `sched.txt` (the scheduler log), terminal markers, `ledger_cost.json` | the scheduler; `ledger_cost_vm.py` |
| `analysis/summary.json` | every pre-specified outcome and test; `classes.jsonl.xz`, `pairs.jsonl.xz` | `analyze.py` (unchanged, sha256 b7dc4aa7…) |

Two descriptive rows of `analysis/summary.json` read the wrong harness field and are not reported (`manifest.json`,
`analysis.known_defects_in_descriptive_rows`): the whole-trajectory exposure row and the honest-claim action-utility
row. No primary or secondary test uses them.

Appendix D.5's tables are generated from these files by `scripts/pair_multi/spoof/render_tables.py`
(`tables/pair_spoof*.tex`).

## Code

SharedEval `7f409da` = `4565add` (the header ladder's checkout, itself `8081e7e` plus
`scripts/pair_multi/told_ladder/sharedeval-told-4565add.patch`) plus
`scripts/pair_multi/spoof/sharedeval-spoof-7f409da.patch`. Applying the patch to `4565add` gives tree
`ca935581…`, the tree of `7f409da`. Kernel: K2.

The controls' configs are byte-identical to the 10-02 configs of the same group (`SP-A0h-r1-g004` and
`I2-ID-R0-g004`: sha256 `aac6f36e…`; `SP-A0n-r2-g100` and `I2-PR-R0-g100`: `87dfa6d9…`). An impersonation
config differs from its control only by the `benchmark.spoof` block.

## Reproduce

```
node scripts/pair_multi/spoof/prefix_overlap.mjs evidence/v3.14/multi-spoof/inputs/evaluator.ts \
  evidence/v3.14/multi-spoof/inputs/questions.json evidence/v3.13/multi-table3/MANIFEST.json \
  scripts/pair_multi/spoof/prefixes evidence/v3.14/multi-spoof/inputs/D2R_ID_R0.md \
  evidence/v3.1/sharedeval/dataset/pact-pair/policies/D2R_PRINCIPLES.md > design/prefix_overlap.json
python3 scripts/pair_multi/spoof/power.py > design/power.json        # needs the two frozen files
python3 scripts/pair_multi/spoof/gen.py <t3simple lane> <lane>         # on the VM
python3 scripts/pair_multi/spoof/delivery.py --negative-control <10-02 lane> scripts/pair_multi/spoof/prefixes
```
