# Public/internal coding: results (after coding)

`scripts/p14/p14_run.py` (committed at 22fa282, before the answers were opened) writes `results.json`, the label
variants `../labels/{S3,S3-bound,S4}.json` and the author-check draw; `scripts/p14/apply_variants.py` writes
`../labels/applied_<variant>.json`; `scripts/p14/survival.py` writes `../labels/survival.json`.

- Answers: `answers/{A,B}/WP.csv` (annotator A: session model claude-sonnet-5-5; annotator B: claude-fable-5-1),
  frozen sessions in `sessions/` (SHA256SUMS frozen before the answers were read), key `key/key-P1-4.json` (sha256 matches `packets/MANIFEST.json`).
- Author check: the blind packet is `author_check/packet/` (also released to the checkers' folder:
  `p1-4.jsonl`, `p1-4-INSTRUCTIONS.md`, `p1-4-answers.csv`). Its key, which holds the coders' codes for the ten drawn
  lines, is `author_check/key.json`, kept out of git until the author returns; sha256 in `results.json`.
