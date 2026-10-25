# PAIR II: the multi-turn ladder with the requester named

Frozen numbers behind `tab:pair-told-ladder` (Appendix D.4, "The ladder, told") and the sentence on the
category policy in Section 4.2. Scripts: `scripts/pair_multi/told_ladder/`.

## Design

- **Told cells:** the ladder's three rungs behind the runtime-verified caller head that PAIR I and
  `D2R_ID_*` use: `D0_ID_Rk` = head alone, `D1_ID_Rk` = head + P1, `D2_ID_Rk` = head + P2 (the ladder's D1 and
  D2, byte-exact). SharedEval `8081e7e` plus `sharedeval-told-4565add.patch`, which only adds the nine
  texts, registers them, and maps each name to its rung's category dial and to the one requester it names.
- **Control:** the ladder's untold D2 on the same route, to separate the route from the head.
- **Untold reference:** DeepSeek's own ladder runs (`t3simple`, Azure `DeepSeek-V4-Flash-0731`).
- **Requesters / groups:** R1–R3 on the ladder's 50 groups; category gold, as in the ladder.
- **Model:** `deepseek/deepseek-v4-flash-0731` through the budget-capped gateway to OpenRouter, pinned
  to the `Relace` upstream; temperature 0, 4,096 output tokens, `simple` profile, 22 ticks.
- **Run:** VM lane `<vm>/runs/pair2told`, 2026-10-03 17:25–18:07 UTC, 600 sessions, one
  rerun per invalid session. A first pilot failed at load (registry order) before any model call.

## Files

| File | What it is |
|---|---|
| `summary.json` | `analyze.py` output: per requester and pooled, DL / FR / AS / U for the seven cells on the tasks all seven scored, and paired exact McNemar tests (head, route, and told vs the ladder at each rung) |
| `manifest.json` | model block, config hashes, session and failure counts, provider-reported cost |
| `pairs.json` | per task-requester pair, the outcome of every metric in all seven cells (input to the estimates) |
| `estimates.json` | `scripts/pair_multi/estimate_told.py` output: DeepSeek's head effects with bootstrap errors, the heterogeneity terms, and the told estimates (not run) for GLM, Grok and the probing grid, with 95% intervals. Method and assumptions are in the file and in Appendix D.4. These are estimates, not measurements. |

## Reproduce

```
git -C <SharedEval> worktree add ../SharedEval-told 8081e7e && git -C ../SharedEval-told am sharedeval-told-4565add.patch
python3 scripts/pair_multi/told_ladder/gen.py <t3simple dir> <lane dir>
LANE_DIR=<lane dir> CAP=48 scripts/pair_multi/told_ladder/sched.sh full
python3 scripts/pair_multi/told_ladder/analyze.py <lane dir> <SharedEval-told> <questions.json> <t3simple dir> > summary.json
python3 scripts/pair_multi/told_ladder/render_table.py
```
