# Table 3: the multi-turn ladder under the simple profile

This folder holds the frozen numbers behind Table 3 (`tab:pair-multi-ladder`) and its appendix table (`tab:pair-multi-full`), together with the scripts that produced them.

## Grid

- **Size:** 50 three-task groups × D0/D1/D2 × R1–R3 × 3 builds, 1,350 sessions.
- **Groups:** the same groups as the earlier strict-profile grid (`MANIFEST.json`).
- **Run:** on the experiment VM under `<vm>/runs/t3simple`, 2026-09-28. `DONE` was written and verified at 22:53 UTC.
- **Code:** SharedEval `8081e7e` (systemind-team/SharedEval#94, based on `claude/pair-multi-phase2-20260915`).
- **Profile:** `workflow.pairProfile: simple`. The runtime puts the responder's four control files in its prompt and grants standing capabilities.
- **Builds:**
  - DeepSeek: `DeepSeek-V4-Flash-0731` on Azure.
  - GLM: `z-ai/glm-5.3` on OpenRouter, pinned to `baidu/fp8`, no fallback. Cash cost $73.06.
  - Grok: `grok-4.6` on Azure, with `model.toolRootCombinators: drop`. DeepSeek and GLM requests are byte-identical to `26dd392`.
- **Settings:** temperature 0, one run per cell, one retry per invalid run (`-x2`).

## Files

| File | What it is |
| --- | --- |
| `table3s.json` | `scripts/analyze_s4.py` output: scored/attempted per cell, block rates, task-paired exact McNemar, nine-cell intersection. |
| `s4_rescore_table.json` | Per-block decision leak and refusal-channel leak. A reply that carries a gold fact is classed by what the requester recorded; see the `rescore_*` scripts, which use SharedEval's `containsPactPairFactV1`. |
| `filter_loss.json` | Tasks lost to, or shortened by, Azure's prompt filter, per cell. `touched` lists every affected task. |
| `s4_sensitivity.json` | Decision leak and tests after removing every task the filter touched, at any rung. |
| `ladder_utility.json` | `scripts/pair_multi/ladder_utility.py` output: per block, information utility (shareable questions answered with the gold facts, deterministic matcher) at D0/D1/D2 on the tasks scored at all three rungs, with a paired exact McNemar D0→D2. Backs the utility clause in Section 4.2 and Table 2. |
| `digest.txt` | SHA-256 digests of everything above. |

## Two provider behaviours, neither at D2

1. **Grok tool-schema rejection.** Grok rejects any tool whose parameter root carries `anyOf`, and `edit_todo` has one. Before `8081e7e`, 480 of 480 simple-profile Grok responder requests failed with HTTP 400.
2. **Azure prompt filter.** Azure flagged a responder request as a jailbreak (`content_filter`, "Jailbreak") in 120 of 450 DeepSeek sessions and 109 of 447 Grok sessions.
   - Every flagged session was at D0 or D1.
   - In 230 of 232 logged sessions, the first flagged request was a task's first ask.
   - The strict profile, which delivers the same files as tool results, never triggers the filter.
   - Every non-429 provider error body was logged by `scripts/fetchlog.mjs` (errors-only mode).
