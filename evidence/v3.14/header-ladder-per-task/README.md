# Header ladder per-task records (Table 31 in the reviewed PDF)

- `told.jsonl.xz`: one line per session slot (TOLD D0/D1/D2 and CTRL D2 × R1–R3 × 50 groups; 600), from
  `scripts/freeze/pair2_runs/extract.py told`, read-only over
  `<vm>/runs/pair2told/cfg/runs/T3-<arm>-<rung>-<requester>-<group>[-x2]/multi` on the experiment VM
  (run 2026-10-03; SharedEval 8081e7e + `scripts/pair_multi/told_ladder/sharedeval-told-4565add.patch`). Same fields
  as `../ladder-per-task/ladder.jsonl.xz`. Input to the total-leak rescore of the header ladder.
