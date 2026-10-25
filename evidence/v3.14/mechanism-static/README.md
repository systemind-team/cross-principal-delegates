# Mechanism baseline, static — v2

Pure computation on frozen PAIR I data. It is **not** a claim that any mechanism removed leak: no grant was
issued, no kernel ran, no model was observed. It computes a property of the workspace — how often a requester's
protected and entitled facts sit in the same resource — which bounds what any resource-scoped, requester-derived
read grant could do, and shows that bound is an oracle under the scorer's own labels. v2 applies the design
reviews of 2026-10-24.

## Files

| File | What | Made by |
|---|---|---|
| `../../../scripts/mechanism_static/locate_facts.mjs` | locates every gold fact wherever it occurs (matcher and verbatim ≥8 char) | committed before its output |
| `fact_locations.json` | per question, the resources each gold fact occurs in, by locator, plus its declared sources | `locate_facts.mjs` |
| `../../../scripts/mechanism_static/compute.py` | the committed rule and computation | committed before its output |
| `results.json` | the frozen output | `compute.py` |
| `../../../tables/mechanism_numbers.tex` | the `\mechnum{key}` macros the Appendix B paragraph cites (integers of 1,000 or more emitted with `{,}`, e.g. `defn-draws` = `1{,}000`) | `../../../scripts/mechanism_static/render_macros.py` |

Both scripts pin the sha256 of their frozen inputs and refuse to run if any differs: `questions.json`
(`9032f46a…`), `alex_data_store.json` (`f67467c1…`), `relationship_label_matrix_v2.json` (`be59b5ad…`, the file
PAIR I scored against), the 8081e7e scoring matcher `evaluator.ts` (`c51f2dbf…`), and `annotation_passes.csv`
for the leave-one-pass-out.

## What v2 computes

- **Definitional cells.** Under strict a protected question's source is withheld, so strict's
  protected-removed is 100% for any labels; under loose an entitled question's source is granted, so loose's
  over-block is 0%. A 1,000-draw random-label check confirms it (0 violations). These are not findings.
- **Co-location counts, the informative numbers,** with denominators, both directions, per requester and
  granularity: entitled facts that share a resource with a protected fact (strict over-blocks them) and
  protected facts that share a resource with an entitled fact (loose leaves them readable).
- **Occurrence bounds.** Grants are built from declared-source labels; a fact is readable from its
  declared source and, under the `matcher` and `verbatim` locators, also from any resource a copy of it is
  located in (the declared source always counts, so loose's over-block stays 0 by definition and only the
  strict protected-readable figures move). Three locators: `declared` (source only), `matcher` (the scoring
  matcher anywhere), `verbatim` (≥8-char substring anywhere). Reported per rule × granularity × requester.
- **Leave-one-pass-out.** Grants from one annotation pass, truth = the majority of the other four
  (ties to protect), per held-out pass and as the mean. It shows the bound depends on the label author.
  Units are questions (protected questions left readable / truth-protected; entitled questions over-blocked /
  truth-entitled). The mean averages the five per-pass shares; their range is exposed as
  `lopo-<R>-<strict|loose>-<read|over>-<min|max>` (one decimal), e.g. the colleague under the strict rule:
  read 0.0-35.8 and over-block 0.0-56.7 by pass, means 13.0 and 13.0.
- **Actions:** counts only. R0 and R3 may cause none of the 200 actions.
- **Separability:** 230 of 236 items hold one category; none mixes answer and refuse.
- **Data quality (R4 opt B):** the 11 questions whose declared source holds no matcher-found gold fact.

## Headline numbers (from `results.json`)

- Co-location at item level is small: a requester's protected questions sharing a note/to-do with one of its
  entitled questions is 2/399 (R0), 3/190 (R1), 4/139 (R2), 15/346 (R3); 0/200 under category labels.
- But facts are copied: by the scoring matcher 314 of 400 questions have a gold fact outside their declared
  source (204 by the verbatim >=8-char locator). Under strict item grants a protected question still reaches a granted resource for 45/190 (R1),
  33/139 (R2), 48/346 (R3), 39/200 (category) by the matcher — 14/12/17/13 by the verbatim ≥8-char locator.
  So even the oracle grant does not remove leak.
- Folder granularity is too coarse in either direction (in `results.json`).

## Reproduce

```
node scripts/mechanism_static/locate_facts.mjs evidence/v3.14/multi-spoof/inputs/evaluator.ts \
  evidence/v3.14/pair-dataset/questions.json evidence/v3.14/pair-dataset/alex_data_store.json \
  > evidence/v3.14/mechanism-static/fact_locations.json
python3 scripts/mechanism_static/compute.py > evidence/v3.14/mechanism-static/results.json
```
