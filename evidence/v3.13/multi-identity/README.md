# PAIR II with and without the requester's identity

Frozen numbers behind `tab:pair-identity` (Appendix D.4) and the paragraph "Telling the delegate who
asks improves both" in Section 4.2, with the scripts that produced them
(`scripts/pair_multi/identity_rerun/`).

## Design

- **Groups:** the multi-turn ladder's 50 three-task groups (`t3simple/MANIFEST.json`), 100 questions and 50 actions.
- **Arms:** `D2R_ID_<R>` (a head the runtime verifies names the requester and its relationship, then the
  principles body) against `D2R_PRINCIPLES` (the same body, nothing naming the requester). The head is
  the only difference; requester, grants, model and budget are shared.
- **Requesters:** R0 stranger, R1 colleague, R2 executive's delegate, R3 close friend.
- **Grading:** each requester's relationship labels (`relationship_label_matrix_v2.json`), as in PAIR I.
- **Model:** `deepseek/deepseek-v4-flash-0731` (the ladder's build) through the budget-capped research
  gateway to OpenRouter, pinned to the `Relace` upstream with no fallback; temperature 0, 4,096 output
  tokens, `simple` profile, 22 ticks, multi-turn phases at ticks 4 and 19.
- **Code:** SharedEval `8081e7e`.
- **Run:** VM lane `<vm>/runs/pair2id2`, 2026-10-02 19:48–20:59 UTC; one session per group,
  requester and arm (400), one rerun per invalid session (`-x2`).

## Files

| File | What it is |
|---|---|
| `summary.json` | `analyze.py` output: per requester and pooled, each metric's counts per arm on the tasks both arms scored, discordant pairs and exact McNemar p |
| `manifest.json` | model block, config hashes, session and failure counts, provider-reported cost from the gateway ledger |
| `unpinned_launch.json` | the first launch without a pinned upstream, stopped after 118 sessions: per-upstream call outcomes and per-requester harness failures. Nothing from it is reported |

## Reproduce

```
python3 scripts/pair_multi/identity_rerun/gen.py <t3simple dir> <lane dir>
LANE_DIR=<lane dir> CAP=32 scripts/pair_multi/identity_rerun/sched.sh full
python3 scripts/pair_multi/identity_rerun/analyze.py <lane dir> <SharedEval checkout> > summary.json
python3 scripts/pair_multi/identity_rerun/render_table.py
```
