# Single-request grid: analysis scripts

Frozen inputs live in `evidence/v3.13/single-grid/`:

- `rescore-openrouter-82.json`, `rescore-azure-28.json`: offline relationship-v2 rescore reports (SharedEval
  `scripts/experiments/rescore-relationship-grid.ts --recover-quarantined-qa`, commit 5aaa7f1 on the
  `feat/azure-reasoning-max-completion-tokens` lineage). Strict rates in the OpenRouter report are byte-identical to the
  frozen `rescore-final-82.json` snapshot of 2026-09-16.
- `cells.json`: the 110-cell merge produced by `build_cells.py` (needs the per-cell `tasks/*.tasks.jsonl` detail
  files, 75 MB, kept on the experiment server; digests in `manifest.json`).
- `stats.json`: Wilson intervals and exact paired McNemar tests (`stats.py`).
- `diag_scan.json`: matcher-based diagnostic scans (`diag_scan.ts`, run inside the SharedEval checkout).
- `pools.json`: Files QA (Q1--Q200) versus States QA (Q201--Q400) per cell, with recovery: counts, Wilson intervals, the States-minus-Files gap and a two-sided Fisher exact p-value (`pools.py`; the script first re-derives every cell's pooled QA numerators and denominators from the per-task rows and stops on any mismatch).
- `review/`: stratified trace sample (`sample_traces.py`), rubric, AI verdicts (`ai_verdicts.jsonl`, `summary.json`), the seeded 54-trace author subset (`human_subset.jsonl`) and the author verdicts over it (`human_verdicts.jsonl`; fields and rules in `HUMAN_VERDICTS.md`).

`tables.py` regenerates `tables/single_*.tex`; `figures.py` regenerates `figures/single_grid/*` (matplotlib, numpy).
`proposed_figures.py` draws the draft visual alternatives in `proposed_graph/` from the same data; the paper does not use them.
The paper build does not call these scripts; the rendered assets are committed.
