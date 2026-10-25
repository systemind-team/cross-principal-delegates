# PAIR I supplement: grok-4.6

Design and review questions: `planning/2026-10-05-pair1-grok-supplement.md`. Fixed inputs:
`evidence/v3.13/single-grid-grok/design/` (`hard_set.jsonl`, `random_set.json`, `run_plan.json`).

| Script | What it does |
| --- | --- |
| `common.py` | Per-row metric rules for both label sets, the hard-set rule, frozen-input digests, Wilson and exact McNemar. |
| `select_sets.py` | Draws the hard set, the random set, the run plan and the trial from the frozen rows; a rerun is byte-identical. |
| `make_configs.py` | Writes the twelve SharedEval configs (or the trial's, `--trial`) from the run plan; the endpoint is an argument. |
| `refusal_scan.mts` | Refusal-channel scan (gold fact inside a refused reply), part (a) of `../diag_scan.ts` with paths as arguments. |
| `cost.py` | Prices task-runs from the runner's per-request usage at Azure's grok-4.6 list price and projects the plan. |
| `analyze.py` | The analysis: gates, random-set rates and ladder, leave-one-out on the hard set, primary tests F1–F3. |
| `retry_list.py` | Lists the task-runs that Azure rate limiting killed (error, with a model request that ended in HTTP 429 after retries). |
| `render_results.py` | Writes `evidence/v3.13/single-grid-grok/RESULTS.md` from the analysis output and the run evidence. |
| `vm/lane.sh`, `vm/rescore.sh`, `vm/guard.py`, `vm/watch_grok.py` | What ran on the experiment VM (its paths): one run per cell with a `.done` marker; the rescore shim and scan; the budget guard; the outage watcher (stopped unused). |

## Reproduce

The frozen per-task rows (`tasks.jsonl`, 66,000 rows, SHA-256 `195f90e1…`) are not in git. They are in the
team's shared run directory under `analysis/out/`. Put them, `diag_scan.json`, `rescore-openrouter-82.json` and
`rescore-azure-28.json` in one directory and pass it as `--frozen`. The default is
`evidence/v3.13/single-grid/`, which has everything but `tasks.jsonl`.

```bash
python3 scripts/single_grid/grok/select_sets.py --frozen DIR
python3 scripts/single_grid/grok/make_configs.py --endpoint https://<resource>.cognitiveservices.azure.com/openai/v1 --out CONFIGS
# run each CONFIGS/grok-d<k>-r<j>.yaml with SharedEval 5aaa7f1 (runtime 40f4f01), SharedOS 3aa07e3:
#   tsx src/runner/v1/sharedeval-cli.ts single --config CONFIGS/<cell>.yaml --run-id <cell>
# lay each run out as CELLS/<cell>/root/{config.yaml, runs/<cell>} and rescore:
#   tsx scripts/experiments/rescore-relationship-grid.ts --cell <cell>=CELLS/<cell> ... \
#     --output GROK/rescore.json --detail-dir GROK/tasks --include-text --recover-quarantined-qa
SHAREDEVAL_DIR=<SharedEval checkout> npx tsx scripts/single_grid/grok/refusal_scan.mts GROK/scan.json GROK/tasks/*.tasks.jsonl
python3 scripts/single_grid/grok/analyze.py --frozen DIR --grok GROK --grok-scan GROK/scan.json
python3 scripts/single_grid/grok/cost.py CONFIGS/runs/*
# what produced RESULTS.md (run evidence under evidence/v3.13/single-grid-grok/run/):
python3 scripts/single_grid/grok/analyze.py --frozen DIR --grok evidence/v3.13/single-grid-grok/run/plan \
  --grok-scan evidence/v3.13/single-grid-grok/run/plan/scan.json --grok-retry evidence/v3.13/single-grid-grok/run/retry \
  --retry-list evidence/v3.13/single-grid-grok/run/retry_list_merged.json
python3 scripts/single_grid/grok/render_results.py
```

`python3 scripts/single_grid/grok/analyze.py --frozen DIR --dry-run luna` runs the whole analysis with the frozen
GPT-5.6 rows in grok's seat.

Checks done when the design was fixed:

- `select_sets.py` is byte-identical on rerun.
- `refusal_scan.mts` over the frozen rows reproduces `diag_scan.json`'s 878 `leak_in_refusal` hits exactly.
- The dry run passes every gate.
