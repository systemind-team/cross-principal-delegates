# PAIR I per-task rows (the replies behind every PAIR I cell)

`tasks.jsonl.xz` (xz; 66,000 rows, 75.0 MB uncompressed) is the merge of the 110 per-cell detail files written by
SharedEval's offline rescore (`scripts/experiments/rescore-relationship-grid.ts --include-text --recover-quarantined-qa`).
One row per task and cell: request text, the responder's reply text (cut at 2,000 characters; 6 of 44,000 question
replies are cut, none of them a refused protected one), status, decision, fact match, the category and relationship
expectations, the relationship leak flag and, for recovered tasks, the recovery record.

Source, read-only on the experiment VM (2026-10-04):
- `<vm>/work/rescore-v41-recovered/tasks/*.tasks.jsonl` (82 OpenRouter cells); `rescore.json` beside them
  has sha256 f51dc60e…, identical to `evidence/v3.13/single-grid/rescore-openrouter-82.json`;
- `<vm>/work/rescore-luna/tasks/*.tasks.jsonl` (28 Azure GPT-5.6 cells); `rescore.json` sha256 9d1ef6d9…,
  identical to `rescore-azure-28.json`.
The commands that produced them are `run-rescore-v41-recovered.sh` and `run-rescore-luna.sh`. `per_cell_sha256.json` gives
each source file's sha256.

Check: the uncompressed `tasks.jsonl` has sha256 195f90e18034a6d989ae014171a730be8d84b84baf52aada73435ba6689a75b1, the
digest `evidence/v3.13/single-grid/manifest.json` records for the merged file the C.8 scan and `stats.py` used. It is
rebuilt byte for byte by `scripts/single_grid/build_cells.py`'s merge (sources in that order, files sorted, `json.dumps`
per row with the cell fields added).

Regenerate: copy the two `tasks/` folders, run the merge, `xz -9e`.
