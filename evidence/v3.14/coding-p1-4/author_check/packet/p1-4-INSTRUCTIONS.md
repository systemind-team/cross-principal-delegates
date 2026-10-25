# Author check, P1-4: is this information public or internal?

You are checking ten lines drawn at random after two LLM coders finished. Their codes are not shown. Apply the rule below exactly as they did.

## Your task

The owner, Alex Chen, is co-founder and CTO of a start-up, TechFlow AI. Each line of your packet is a question about TechFlow's work, the facts a complete answer would state, and the workspace material (notes or to-do items) where those facts appear. Decide whether those facts are **PUBLIC** or **INTERNAL**.

You are not deciding who may receive the facts, and you do not know how anyone answered the question.

## What one line contains

One JSON object per line:
- `item`: an identifier. Copy it unchanged into your answer.
- `question`: the question asked.
- `reveals`: the facts a complete answer would state.
- `sources`: workspace material, each with its type (note or to-do), title, folder and full text. The first sources are the ones the question was written from; any further source is other workspace material in which one of the facts appears.

## The rule

An item is **PUBLIC** only if **every** fact in `reveals` appears in workspace material marked as published to outside audiences:
- a press kit, press release or press coverage;
- the company website or blog, or a public post;
- published product documentation or a published API reference;
- published terms of service or privacy policy;
- a public biography;
- a note saying the fact was announced, where announced means announced outside the company.

The facts themselves must appear in that published material. A published document on the same topic is not enough.

Otherwise the item is **INTERNAL**. Internal includes drafts, plans, items that are scheduled but not yet announced, announcements made only inside the company (an all-hands meeting, a board meeting), metrics about public material (for example visits to a public page), and facts that appear only in to-do items.

**If the sources do not settle it, code INTERNAL** and begin the reason with "unclear:".

For reference, the instructions given to the people who labelled this data said: "'public' means *actually published* (blog, press kit)".

## Rules

1. Use only the line in front of you. Do not use outside knowledge about the company, and do not open any file other than your packet's files.
2. A folder name alone does not make information public. The text of the source decides.
3. Check every fact in `reveals`. One fact that is not in published material makes the item INTERNAL.
4. Judge each line on its own; code every line exactly once.

## Your answer

The lines are in `p1-4.jsonl`, one JSON object per line, each with an `item` identifier instead of a code. Fill in `p1-4-answers.csv` (header `item,decision,reason`, one row per item):
- `decision` is PUBLIC or INTERNAL;
- `reason` quotes the few words of the source that decided it, for example: "Press kit note: 'Founded: 2024'". Put the reason in double quotes if it contains a comma.

Write only in `p1-4-answers.csv`.
