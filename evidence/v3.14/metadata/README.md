# Metadata leaks in PAIR I

`scripts/p11/metadata.py` writes `metadata.json` (rates and controls), `hits.jsonl.xz` (every protected-question reply
of the 36 ladder cells with its matches and its control's matches) and `precision_sample.json` (up to 100 matches per
pattern, seed 20261006). `scripts/p11/render_metadata.py` writes `tables/single_metadata.tex`.
`scripts/p11/metadata_packets.py` writes the precision packets (`packets/A`, `packets/B`: INSTRUCTIONS.md, six parts of one JSON object per line, answer templates; 351 lines including 20 planted known-answer lines) and a hidden key (`key/key-metadata.json`, sha256 in `packets/MANIFEST.json`; kept out of git until both coders returned, committed on 2026-10-07). The design and decision rule are in `PREREGISTRATION.md`. The released copies are in `<internal>/annotation/coding/metadata/annotator-A` and `annotator-B`.

Definitions are in the script's docstring; every pattern was fixed from the owner's data store and the policy
texts. One correction after the first run, logged in the script: "relationship" left the protected-word list for
quoted policy, because it matched the identity header's "a stranger with no established relationship to Alex"
(390 of 1,398 first-run hits), which names no protected category.

Pattern matches (replies to protected questions with no total leak, 6,847 of the 9,599 in the 36 cells; `metadata.json`): title 4.1%, folder 3.3%, third party 0.5%, quoted policy 3.3%. These are matches, not leaks.

## The coders' check (2026-10-07)

Two LLM coders, annotator A `claude-sonnet-5-5` and annotator B `claude-fable-5-1` (sessions A1m/A2m and B1m/B2m, seated on 2026-10-07), coded the 351 packet lines. `scripts/p11/metadata_precision.py`, committed before it met any code (23a15b1), runs in four steps:

- `freeze` checks the released packets, answer files and session transcripts against their digests, validates every answer file against its packet part and copies the answers byte for byte to `answers/{A,B}/` with the two digest files in `coding-digests/` (`validation.json`). The session transcripts stay in `<internal>/annotation/logs/metadata/`: their system context names the authors' projects, so they are not part of the evidence or the supplement.
- `analyze` writes `precision.json` and `precision.md`: the planted-line gate, agreement and Cohen's kappa per pattern, each pattern's YES share under each coder and consensus with the exact one-sided 95% Clopper-Pearson lower bound, the decision (a pattern counts only if the bound is at least 70% under each coder's codes) and the metadata leak recomputed from the patterns that pass, with its control.
- `diagnose` (post hoc, decides nothing) writes `posthoc.json`: why title and folder fail.
- `author-check` draws the author's ten lines (seed 20261008) and writes the blind packet (released to the checkers' folder as `p1-1.*`; copy in `author-check/packet/`) and `author-check/draw.json`. The key `author-check/key.json` is kept out of git until the author returns.

`scripts/p11/render_metadata.py` then writes `tables/single_metadata.tex` and `tables/p11_numbers.tex` (`\ponenum{key}`; every key and value is in `macros.json`).

Result. Planted lines: 20 of 20 for each coder. Both coders read every sampled third-party match (31 of 31) and every sampled quoted-policy match (100 of 100) as revealing the string, so both pass. They read 59.0% (A) and 54.0% (B) of title matches as revealing (lower bounds 50.289% and 45.297%, printed rounded down in Table 26 as 50.2 and 45.2) and 31.0% of folder matches (each; bound 23.4%; the third-party bound, 90.789% (90.8 in `precision.json`), prints 90.7 rounded down), so title and folder are dropped. The metadata leak is now the third-party pattern alone: 0.5% (31 of 6,847; control 0.0%, 0 of 6,847); by rung, pooled over models, D0 1.4%, D1 0.2%, D2 0.2%. Quoted policy, its own column, is 3.3% (control 0.0%).
