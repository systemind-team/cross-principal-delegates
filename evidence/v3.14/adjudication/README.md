# P1-2: two LLM annotators read the protected replies (frame, draw, packets)

Protocol v2: `protocol/p1-2-protocol.md`. Status
(2026-10-07): the authors chose the fallback family. Annotator A (claude-sonnet-5-5) and annotator B (claude-fable-5-1)
each labelled all 1,412 items; both label sets are validated and frozen in `labels/`, with every session recorded in
`packets/MANIFEST.json`.

| Path | What | Made by |
|---|---|---|
| `frame/runtime_hits.jsonl.gz` | the scoring matcher's verdict on all 10,651 protected replies of the probing grid (gold facts in the reply and in the conversation) | `scripts/adjudication/runtime_hits.mjs` |
| `frame/pair2_frame.jsonl.gz`, `frame/pair1_frame.jsonl.gz` | every unit with its frame cell and stratum | `scripts/adjudication/frame.py` |
| `frame/cells.json` | every cell's count, every stratum's population and draw size (posted before the draw) | same |
| `frame/seeds.json` | the draw seed and the author-check seed, read off the sha256 of `cells.json` | same |
| `packets/annotator-A/`, `packets/annotator-B/` | the 1,412 items (1,372 drawn, 40 planted) in each annotator's own order, 15 files each, as released | `scripts/adjudication/make_packets.py` |
| `packets/GUIDELINES.md` | guidelines version 2, as released | authors |
| `packets/MANIFEST.json` | digests of every packet file, the guidelines, and the sealed files | `make_packets.py` |
| `protocol/p1-2-protocol.md` | the protocol as committed before labelling | authors |
| `labels/annotator-A/`, `labels/annotator-B/` | both label sets as returned, 15 files each, frozen 2026-10-07 (`labels/SHA256SUMS`) | the annotators |
| `labels/validation.txt` | `validate_labels.py` on all 30 files against their packets | `scripts/adjudication/validate_labels.py` |
| `author-check/` | the 20-item blind author packet, its instructions and the empty answer template, as released to `<internal>/annotation/author-check/` (the id key stays sealed) | `draw_author_check.py`, `author_packet.py` |
| `analysis/gates/` | the gates and the agreement per stratum, before adjudication (no rate) | `score.py`, `gates_report.py` |
| `analysis/final/` | the full pre-registered analysis after adjudication (`summary.json`); the author block follows the authors' answers | `score.py`, `render_p12.py` |
| `pre-adjudication/` | `score.py`'s full output before adjudication (`summary.json`, sha256 7baf29c8…, status "not usable yet"; `score_stdout.json`; empty `score_stderr.txt`), committed 2026-10-24. It records that the gates and agreement were computed, and the rate block was sealed and unread, before the adjudication ran; `analysis/gates/gates.json` records this summary's sha256 as its source. The gate, agreement and coverage blocks equal `analysis/final/summary.json`; the rate blocks are the pre-adjudication values (first-reply 11.79% against the final 11.88%). | `score.py` (before `--adjudication`) |
| `packets/adjudicator/adjudication.jsonl` | the blind adjudication packet as released to `<internal>/annotation/p1-2/adjudicator/`, one line per label disagreement (the X/Y map stays sealed) | `make_adjudication.py` |
| `labels/adjudicator/` | the adjudicator's answers as returned (claude-haiku-4-5-20251001) and mapped back to A and B, with `SHA256SUMS` | the adjudicator; `make_adjudication.py map` |
| `labels/author/author_labels.jsonl` | the author's labels on the 20 author-check replies (checker 1 of Appendix C.1), in `score.py --author`'s format | `scripts/adjudication/author_labels.py` |
| `sealed/` | the files kept sealed until the author answered, committed 2026-10-24 byte for byte (below) | authors |

Sealed until the author spot check returned, and committed in `sealed/` on 2026-10-24, byte for byte, each digest equal to
the one fixed in `packets/MANIFEST.json` before release or when the file was made: `key.jsonl` (item to stratum, frame
flags, inclusion probability, run, task, model, the old reviewer's verdict and view), `drawn.jsonl`, the planted items'
`planted_bases.jsonl`, `planted_edits.json`, `planted_items.jsonl` and `planted_answers.jsonl`, the adjudication's X/Y
map (`adjudication_map.jsonl`, with `adjudication_build.json`), and the author check's draw record and id key
(`author_check_draw.json`, `author_check_drawn.jsonl`, `author_check_key.json`, `author_packet_build.json`). They were
kept outside the repository until the author had answered, so the author could not meet them there. None of them
names a checker. The two build records still carry the paths the files had while sealed. The pre-adjudication run's
full output (`score.py` before the adjudication, whose rate block was not read; its gate block is `analysis/gates/`)
is committed under `pre-adjudication/` (above).

The author answered in chat through the combined author-check tool, not in `p1-2-answers.csv`, so
`author_packet.py collect` had nothing to read. `author_labels.py` builds the same rows from the anonymous parse of
the answers (`../author-check/answers.json`, bound by digest to the verbatim record, which names the checker and is
never read by this pipeline), checks every label rule a label and its fact numbers can break, maps the packet ids to
the annotators' item ids with `sealed/author_check_key.json`, and stops unless its rows equal the independent expansion in
`../author-check/results.json`. The chat answers carry no quote, confidence or note, so those rules are not applied;
`score.py`'s author block reads only the label and the facts conveyed.

Scripts: `draw.py` (the draw and the planted items' base replies), `planted.py` (edits applied and checked; 8 items per
label), `validate_labels.py`, `score.py` (the pre-specified analysis, tested on synthetic labels only),
`draw_author_check.py` (10 items, or 20 under the fallback), `gemini_runner.py` (the scripted annotator for option (c),
written and dry-run, not run).

Regenerate the frame and the draw:
```
gzip -dc evidence/v3.14/multi-probing-records/contacts.jsonl.gz | node scripts/adjudication/runtime_hits.mjs \
  evidence/v3.14/multi-spoof/inputs/evaluator.ts evidence/v3.14/multi-spoof/inputs/questions.json \
  evidence/v3.14/pair-dataset/policies/PAIR-II_ladder_D2_category.md > runtime_hits.jsonl
python3 scripts/adjudication/frame.py runtime_hits.jsonl evidence/v3.14/adjudication/frame
python3 scripts/adjudication/draw.py <sealed dir>
python3 scripts/adjudication/planted.py <sealed dir>
python3 scripts/adjudication/make_packets.py <sealed dir> <annotation dir> <GUIDELINES.md>
```
