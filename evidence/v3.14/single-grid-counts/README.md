# PAIR I delivery counts for Appendix C.2

`macros.json` is written by `scripts/single_grid/counts.py` with `tables/single_grid_numbers.tex` (`\sgnum{key}`).
Inputs: `evidence/v3.13/single-grid/cells.json` (per cell: error codes, recovered and declined questions, tasks
scored), `evidence/v3.13/single-grid/rescore-azure-28.json` (the Azure rescore's own recovery counts, checked equal)
and `evidence/v3.14/single-grid-tasks/tasks.jsonl.xz` (the Azure grid's error rows by kind).

In the Azure grid 503 tasks ended quarantined (`INDETERMINATE_EXTERNAL_OPERATION`), 400 of them in the close friend's
cells: 431 questions, of which the rescore recovered 413 and declined 18 (11 with no request in the session ledger,
7 with no reply), and 72 actions, which are never recovered. The OpenRouter grids had 29 quarantined tasks and 4
recovered questions, so 417 tasks were recovered in all; 64,646 tasks were scored at run time. The script checks that
the Azure grid's quarantined tasks equal its recovered and declined questions plus all of its action error rows.
No frozen file gives the earlier text's "476".

Regenerate: `python3 scripts/single_grid/counts.py`
