# Identity comparison per-task records (Table 30 in the reviewed PDF, Appendix D.4)

- `identity.jsonl.xz`: one line per session slot (arm PR = without the header, ID = with it; R0–R3; 50 groups;
  400), from `scripts/freeze/pair2_runs/extract.py identity`, read-only over
  `<vm>/runs/pair2id2/cfg/runs/I2-<arm>-<requester>-<group>[-x2]/multi` on the experiment VM
  (run 2026-10-02; SharedEval 8081e7e). Same fields as `../ladder-per-task/ladder.jsonl.xz`.
- `split.json`: `scripts/pair_multi/identity_rerun/per_task.py`. It reproduces every per-requester AS and Leak count
  and discordant pair of `evidence/v3.13/multi-identity/summary.json` exactly (asserted), then gives the split the
  panel asked for: each protected action changed in one arm only, typed as canonically refused or withheld from this
  requester, the ladder grid's 50 actions by type per requester, and the trajectory-exposure ("Leak") count by
  question category per arm.
