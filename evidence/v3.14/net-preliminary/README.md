# Table 41 and the "16 of the 53" from the preliminary run's trace dump

`instruments.json` and `verdicts.json` are written by `scripts/net_preliminary/instruments.py` from `summary/net_traces.txt` (the text
dump of the 149 judged replies on the eight edges the NET string matcher can decide; four lanes: DeepSeek V4 Flash
at D0, D1 and D2, GLM at D2). `verdicts.json` holds the 149 per-reply verdicts of both instruments as structured rows (run, holder, requester, arm, rung, model, the LLM judge's verdict and unanimity, the NET string matcher's hits). The script reproduces every printed value of Table 41 (`tables/net_instruments.tex`, now one sentence in Appendix F: judge 51, matcher 18, both 16, neither 96; 112 of 149 agree, 75.2%):
- lower block: both flag 16, judge only 35, matcher only 2, both clean 96; agreement when either fires 16 of 53;
- upper block: per rung, over the six non-borderline edges delivered at that rung (D0: five), the share of edges
  with at least one flagged reply on the forbidden (L_w) and permitted (L_p) arm, by judge and matcher. Of the 28
  six-edge subsets of the eight edges, only the six non-borderline ones (borderline flags from
  `evidence/v3.14/net-world/paired_edges_24.json`; B-02 and N-08 are borderline) reproduce the printed values.

Not reproducible from frozen inputs: Table 40 (15 edges) and E.4's inline table (24 edges). The dump covers only the
eight matcher-decidable edges, and the preliminary run's per-reply judgments are not frozen anywhere in the
repository.
