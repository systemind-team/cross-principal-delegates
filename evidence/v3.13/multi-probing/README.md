# PAIR II probing grid: what the requester says about itself

`self_intro.json` backs the note under `tab:pair-relationship` (Appendix D). In this grid the
responder is never told who asks: each persona's name and relationship reach only the requester's
own task queue, the kernel envelope names every requester `requester`, and D2, grants and grading are
the same for all four. The only identity the responder can see is what the requester writes.

The file counts, per requester, the messages that give the persona's own name, and splits the
stranger's false refusals by whether its first message on a task names it. Population and rules follow
the table: valid sessions only, tasks scored at least once in every column (569), false refusal as
the runner's `falseRefusalRate` (shareable questions and authorized actions refused).

Produced on the VM with `scripts/pair_multi/self_intro.py <grid600 runs dir> <questions.json>`
over `<vm>/runs/grid600` (SharedEval run artifacts of 2026-09-23/24).

`refusal_example.json` is the reply quoted in Section 4.2 ("one reply scored as a refusal opens …"):
run `G6-R1-r1-g001`, task `PAIR-Q155`, the responder's delivered reply copied verbatim from the
SharedOS message record, with its `publicEvaluation` (decision `refuse`, `leaked: true`).

`probing_outcomes.json` holds, per (requester, repetition, task) on the matched set, the five outcomes
behind the table (`scripts/pair_multi/probing_outcomes.py`); it reproduces every published cell and is
the untold baseline for the told estimates in `../multi-told/estimates.json`.
