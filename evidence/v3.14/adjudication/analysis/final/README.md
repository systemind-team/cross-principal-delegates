# P1-2: the final analysis, after adjudication (2026-10-07; author block 2026-10-24)

Protocol v2 §9. Inputs: the frozen label sets (`labels/annotator-A`, `labels/annotator-B`), the adjudication mapped back to the
coders (`labels/adjudicator/mapped.jsonl`, sha256 ce161f32d047730b2de673204ece27fed329647fd7a6d9dfef24394ac1ace8b1), the sealed key
and planted answers (digests fixed before release in `packets/MANIFEST.json`, committed in `sealed/` once the author answered), the
author's labels (`labels/author/author_labels.jsonl`, sha256 b20df85e6ae27b5702313f875792770de49e8d06e18c2ec6f13ecd333c1af992),
`frame/cells.json` and `multi-probing-records/numbers.json`.

Commands, from the worktree root:

```
python3 scripts/adjudication/author_labels.py > evidence/v3.14/adjudication/labels/author/author_labels.jsonl
E=evidence/v3.14/adjudication
python3 scripts/adjudication/score.py --key $E/sealed/key.jsonl --planted $E/sealed/planted_answers.jsonl \
  --packets-a $E/packets/annotator-A --labels-a $E/labels/annotator-A \
  --packets-b $E/packets/annotator-B --labels-b $E/labels/annotator-B \
  --adjudication $E/labels/adjudicator/mapped.jsonl --author $E/labels/author/author_labels.jsonl \
  --cells $E/frame/cells.json --out $E/analysis/final
python3 scripts/adjudication/render_p12.py
```

- `score.py` is unchanged since 6f23dc2 (sha256 1ff5588060a2319854dbeee97945a73c6e7e896ffec0791dd124b1d53422dcf2).
- `render_p12.py` (sha256 c13e7d74a88859de44856f71c9441c9105e7e21cc988e1427ccd05a3cacc8b0c) was extended at e33b745, before it met
  this summary; 8fd5508 and c2e4ce9 changed wording only (captions, glossary terms, the system-name macro), and the numbers it renders
  are byte-identical.
- The coverage, planted-item, gate and agreement blocks equal `analysis/gates/gates.json`: `gates_report.py` on this summary
  reproduces those blocks and `gates.md` byte for byte.
- `summary.json` (sha256 78a43224496cf8d498000af7fc42de5738b6c4a7f6d8175f716ad331cbcd30a8) now carries the author block. score.py
  computes it last and draws no random number for it: every other block equals the summary of 2026-10-07 (sha256
  fdbd988e9621d21f2fecaf17c298b5e854dffdc9ac9ffa872de1c5aabf955e90), checked key by key.
- The author block: 20 replies; the binary reading matches the final label on 19 (two-sided 95% interval 75.1-99.9%) and the exact
  label on 19; the author contradicts both coders on one reply (CUNPP2, author-check item 12: FULL against both coders' NARROWED).
  It equals the author-check run of the same labels through these scripts (`../../../author-check/p1-2_pipeline_crosscheck.json`),
  and the seven `\ptwonum{author-*}` values equal `../../../author-check/macros.json`.
- Rerun check (2026-10-24): `score.py` with the arguments above, into a temporary folder, reproduces this `summary.json` byte for
  byte (sha256 78a43224…), and `render_p12.py` on it reproduces `tables/adjudication_numbers.tex` and
  `tables/adjudication_results.tex` byte for byte (the first-reply headline `\ptwonum{first-pct}` = 11.9). The 63 later
  exposures the frozen key records as not seen in full (`sealed/key.jsonl`, `old_reviewer.view`; make_packets.py's display
  rule, 1,800 characters for cases 1-8 and 900 for cases 9-64) hold both cases where the earlier review and the final labels
  differ: `later_exposures_79.old_reviewer_vs_new` has the 2 "old disclosure / new not conveyed" under "final / not full view"
  and none under "final / full view". Appendix F's clause rests on this frozen field, not on transcript lines.

Outputs: `tables/adjudication_results.tex` (agreement per stratum, the matchers, the earlier review against the new labels; unchanged by
the author block) and `tables/adjudication_numbers.tex` (the `\ptwonum` macros, now with the seven author keys), which
`appendix/adjudication_validation.tex` (Appendix F) cites.
