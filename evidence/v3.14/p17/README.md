# Corrected inference

`scripts/p17/inference.py` reads `evidence/v3.14/single-grid-tasks/`, `total-disclosure/` and `ladder-per-task/`
(and the filter's touched-task list in `evidence/v3.13/multi-table3/filter_loss.json`) and writes:
- `pair1_tests.json`: every PAIR I rung contrast per block, the requester swaps and the harness test, for total leak
  (`leak_TD`), decision leak (`leak_DL`), false refusal, action safety and action utility (`AU`, authorized actions
  not completed correctly);
- `pair2_tests.json`: every ladder-grid contrast per block with group sign-flip tests and group-bootstrap
  intervals, and the nine-block pooled tests;
- `families.json`: the Holm families of 48 (PAIR I) and 36 (PAIR II), the sensitivity family of 84, the same two
  families with decision leak in place of total leak (`*_family_DL`), and Benjamini–Hochberg q within each table
  (`pair1_bh`, `pair2_bh`, keyed by table: Table 24's 40 swap and harness leak and FR tests; their 33 action-utility
  and action-safety tests; the decision-leak version of Table 24; Table 27's nine D0→D2 utility tests; the pooled
  PAIR II tests; the remaining ladder tests of each study);
- `pair2_filter_sensitivity.json`: the 36 PAIR II family tests again without the 251 tasks Azure's prompt filter
  touched at any rung, with Holm over the 36 and whether any verdict changes (none does).

`scripts/p17/summary.py` writes the readable `summary.md`. `scripts/p17/render_macros.py` writes `macros.json` and
`tables/p17_numbers.tex` (`\psevennum{key}`): the largest p and Holm p of the tests the body states as one
bound (the close friend's D0→D1 false refusal on the three PAIR I models; the nine PAIR II D0→D2 total-leak tests),
as a value and rounded up, so a printed bound always holds; and Table 24's 40 requester-swap and harness tests (`swap-*`: largest paired difference 8.59 points of total leak and 9.43 of false refusal, printed as bounds 8.6 and 9.5; 16 of 20 and 10 of 20 intervals exclude 10 and 5 points). Design and families: the script's docstring.

Change on 2026-10-05: the first version applied one Benjamini–Hochberg correction to all 167 non-family PAIR I tests
together. The plan says "within each table", so q is now computed within each table. Within Table 24's 40 tests no
swap or harness difference is significant (smallest q = 0.10); the earlier global correction had called four of them
significant. Family tests, intervals and every p are unchanged.
