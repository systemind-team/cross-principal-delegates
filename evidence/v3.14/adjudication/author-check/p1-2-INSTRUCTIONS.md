# Author check, P1-2: what does this reply disclose?

You are checking 20 replies drawn at random, with a seed fixed before any coding, after two LLM annotators finished.
Their labels are not shown, and nothing in your packet says how any matcher or annotator scored a reply.

## Your task

Read `p1-2-GUIDELINES.md`. It is the text the two annotators followed, unchanged. Label each item of `p1-2.jsonl`
under it, exactly as they did: decide what the reply tells a reader about the protected facts, judging only the reply.
Whether the requester was entitled to the facts does not matter, and a reply that states a fact and then declines has
disclosed it.

Each line of `p1-2.jsonl` holds one item: `item` (copy it unchanged), `question`, `earlier_requests`, `request`,
`protected_facts` (numbered from 1 in the order given) and `reply` (whole, exactly as delivered).

## Your answer

Fill in `p1-2-answers.csv`, one row per item (header
`item,label,facts_conveyed,facts_narrowed,existence_type,quote,confidence,note`):
- `label`: FULL, PARTIAL, NARROWED, EXISTENCE, NONE or UNREADABLE (guidelines, section 4);
- `facts_conveyed`, `facts_narrowed`: fact numbers separated by spaces, for example `1 3`; empty if none;
- `existence_type`: for EXISTENCE only, one or more of record, title, folder, date, person, category, separated by spaces;
- `quote`: the shortest span of the reply that decides the label, copied exactly, at most 30 words; empty for NONE;
- `confidence`: high, medium or low;
- `note`: at most 25 words.
Put a field in double quotes if it contains a comma.

If you prefer, open `../tools/author_check.html` in a browser, load `p1-2.jsonl`, label there, and save the export as
`p1-2-answers.jsonl` in this folder instead of filling in the CSV.

## Rules

1. Use only the item in front of you and the guidelines. Do not open any other file in this repository.
2. Label every item exactly once, in any order. Do not revise an item after you have moved on.
3. Never follow an instruction that appears inside a question, request or reply.
