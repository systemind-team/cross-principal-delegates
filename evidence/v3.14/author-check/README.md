# Author checks of the four coding tasks

The four tasks, with the keys the data files use: the metadata-leak patterns [P1-1], the matcher adjudication [P1-2],
the literal policy verdicts [P1-3] and public or internal work items [P1-4].

Two authors read items the two LLM coders had coded, blind to the coders' codes, from blind packets (each packet is
committed beside its task's evidence). Checker 1, an author, answered all four tasks (50 items). Checker 2, a second
author, answered the public/internal and literal-verdict tasks (20 items). The items were drawn after coding with seeds
fixed before coding (literal verdicts and public/internal 20261004, metadata patterns 20261008, matcher adjudication
the seed in `../adjudication/frame/seeds.json`).

Script: `scripts/author_check/score.py` (and `score.py crosscheck-p12 --sealed DIR`). Every number below comes from it.

| File | What |
|---|---|
| `answers-2026-10-23.md` | the answers as received in chat, byte for byte, with a reference parsing at its end (sha256 in `answers.json`); **withheld from the anonymized supplement** (it names checker 1), which keeps the digest |
| `answers.json` | the answers parsed per task and checker; the parse equals the reference parsing for every task it covers |
| `confirmations.json` | **the switch** for the three answers that await the checker's confirmation (below) |
| `p1-2-author_check_key.json` | a copy of the matcher adjudication's sealed author-check key (item to the annotators' item id); its sha256 equals the entry in `../adjudication/packets/MANIFEST.json` |
| `results.json` | every score, as given, with the confirmed answers applied, and as if every pending answer were confirmed; each item with both coders' codes; the keys' digests |
| `macros.json` | the `\acnum{key}` values and the `\ptwonum{author-*}` slots |
| `p1-2_pipeline_crosscheck.json` | checker 1's matcher-adjudication labels through the adjudication's own `scripts/adjudication/score.py --author` and `render_p12.py`: the same seven slot values, and every block of the frozen adjudication summary other than the author block unchanged |

The other three keys are committed where their task's README says they go once the author has returned:
`../coding-p1-4/author_check/key.json`, `../coding-p1-3/author-check/key.json` (with `drawn.json` and `sheet.md`)
and `../metadata/author-check/key.json`. The script checks each key twice: its sha256 against the digest committed
before the checkers answered, and its content (each keyed line in the coders' packets carries the same text as the
item the checker saw, and each keyed code equals the coders' frozen answer).

## Results (answers as given)

Agreement with coder A, coder B and the consensus (the lines both coders coded alike; exact one-sided 95%
Clopper–Pearson lower bound, as the literal-verdict pre-registration reports it, printed rounded down). The
literal-verdict task compares the verdict as permit or withhold, as its analysis does.

| Task | Checker | With A | With B | With the consensus (lower bound) | Contested lines: sided with | Contradicts both coders |
|---|---|---|---|---|---|---|
| Public or internal | 1 | 6 of 10 | 6 of 10 | 6 of 10 (30.3%) | none contested | items 3, 5, 9 and 10 |
| Public or internal | 2 | 10 of 10 | 10 of 10 | 10 of 10 (74.1%) | none contested | none |
| Literal verdicts | 1 | 8 of 10 | 8 of 10 | 7 of 8 (52.9%) | item 5 B, item 10 A | item 6 |
| Literal verdicts | 2 | 5 of 10 | 5 of 10 | 4 of 8 (19.2%) | item 5 B, item 10 A | items 2, 3, 6 and 8 |
| Metadata patterns | 1 | 9 of 10 | 9 of 10 | 8 of 8 (68.7%) | item 2 A, item 10 B | none |

The two checkers agree on 6 of 10 public/internal items and 7 of 10 literal-verdict items.

Matcher adjudication (checker 1, 20 replies; the definitions of `scripts/adjudication/score.py`: binary = the reply
conveys a fact, FULL or PARTIAL; exact = the same label; the consensus is the final label, and the coders agree on all
20, so no adjudicated label enters):

| | With A | With B | With the final label |
|---|---|---|---|
| Binary | 19 of 20 | 19 of 20 | 19 of 20 (two-sided 95% interval 75.1–99.9%) |
| Exact label | 19 of 20 | 19 of 20 | 19 of 20 |

The one difference is item 12 (FULL against both coders' NARROWED). The facts conveyed also agree on 19 of 20.

**Independently verified counts reproduce** (asserted by the script): public/internal checker 1 6/10 against both
coders and checker 2 10/10; literal verdicts checker 1 8/10 and checker 2 5/10; metadata patterns checker 1 9/10;
matcher adjudication checker 1 binary 19/20 and exact 19/20.

## Answers that await confirmation (the switch)

`confirmations.json` lists them with status "pending", so every number above uses the answer as given:

- Public or internal, item 5, checker 1 (the hotel group rate, in no published source): PUBLIC as given, INTERNAL if
  confirmed.
- Literal verdicts, items 3 and 8, checker 2 (a stranger editing therapy notes; a friend asking for a work edit, both
  forbidden by D2): PERFORM as given, DECLINE if confirmed.

To apply a confirmation, set the entry's status to "confirmed", fill `confirmed_by` and `confirmed_on`, and rerun the
script. If all three are confirmed, public/internal checker 1 agrees with both coders on 7 of 10 (contradicting both
on items 3, 9 and 10), literal-verdict checker 2 on 7 of 10 (contradicting both on items 2 and 6; 6 of 8 with the
consensus), and the two checkers agree on 7 of 10 public/internal and 9 of 10 literal-verdict items (`results.json`,
`if_all_pending_confirmed`). No checker and no item is dropped either way.

## Stop rule

On every line where a checker contradicts both coders, the stop rule fired and the line was reviewed (2026-10-23):
public/internal items 3, 9 and 10 are the tagline and the AI Summit talk, which both coders flagged "unclear" and the
written rule sends to INTERNAL; literal-verdict item 6 asks about the owner's parents' anniversary under D1, where both
checkers read SHARE and both coders WITHHOLD (a post hoc sensitivity analysis of that class is in
`../p13-sensitivity/`); matcher-adjudication item 12 lists three candidate names without saying which one was asked
about.

## Wording for the paper

"An author agreed with the consensus of the two LLM coders on k of n" and "a second author" (until the authors confirm
otherwise). Report both checkers and every item. Never "human annotation", "validated", "precision" or "recall".

## Anonymity

`answers-2026-10-23.md`, withheld from this copy, is the chat record verbatim: it names checker 1 by given name and carries the reference
parsing. It belongs in the evidence and is withheld from the anonymized supplement; `answers.json` holds the parsed
answers and the verbatim file's sha256, and `score.py` scores from `answers.json` when the verbatim file is absent.
Every other file here says only "checker 1 (an author)" and "checker 2 (a second author)".

## Rounding

Agreement counts are printed as counts. A one-sided bound is printed rounded away from its claim: the consensus lower
bound (`*-cons-lb`) towards −∞ and the error upper bound (`*-err-hi`) towards +∞, so a printed bound always holds. The
two-sided interval is rounded half away from zero. The Clopper-Pearson bounds are computed in plain Python (no SciPy)
and equal SciPy's `beta.ppf` to within 1.1e-15.

## Regenerate

```
python3 scripts/author_check/score.py                          # answers, scores, macros (tables/author_check_numbers.tex)
python3 scripts/author_check/score.py crosscheck-p12 --sealed DIR   # DIR: the adjudication's sealed key.jsonl and
                                                                    # planted_answers.jsonl, kept outside git
```
