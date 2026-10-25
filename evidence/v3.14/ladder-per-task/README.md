# Ladder grid per-task records (Table 4, Table 27)

- `ladder.jsonl.xz`: one line per session slot (build × rung × requester × group, 1,350), from
  `scripts/freeze/pair2_runs/extract.py ladder`, run read-only on the experiment VM over
  `<vm>/runs/t3simple/cfg/runs/S4-<build>-<rung>-<requester>-<group>[-x2]/multi`
  (2026-09-28 run; SharedEval 8081e7e). Each line: the run folder chosen by `analyze_s4.py`'s rule (first attempt if
  valid, else the `-x2` retry if valid, else none), each task's `publicEvaluation` and status, every message of the
  session in ledger order (sender, task, text), and the sha256 of the POLICY.md the responder read. The last line holds
  each policy text once.
- `s4_rescore_blocks.json`: the leak class of every scored protected question (decision, refusal-channel, echo, none,
  no-reply), copied from `t3simple/s4_rescore_blocks.json` (written by `rescore_classify_s4.py` on 2026-09-28 with the
  runtime matcher `containsPactPairFactV1`, in the same run as `evidence/v3.13/multi-table3/s4_rescore_table.json`,
  whose VM copy is byte-identical to the frozen one, sha256 02695e01…).
- `s4_rescore_in.json.xz`, `s4_rescore_out.json.xz`: the matcher's input (every protected question's messages, gold
  facts, policy) and output (the facts found in each reply and in its context), sha256 of the uncompressed files
  3532611c… and 3592ce82…; the scripts that wrote them are in `evidence/v3.13/multi-table3/scripts/`.
- `d2_leaks.json`: `scripts/pair_multi/ladder/per_task.py`. It first rebuilds every cell's scored count and every
  block's task count of `table3s.json` and every block's decision and refusal-channel counts of
  `s4_rescore_table.json` exactly (it stops otherwise), then lists the D2 leaks by task: 14 decision leaks on 3
  distinct questions (Q258 nine times, Q354 four, Q293 once) and 5 refusal-channel leaks (DeepSeek only) on 3.
