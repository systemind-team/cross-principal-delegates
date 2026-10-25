# NET rerun: the grants each run held

The NET rerun (`../../v3.13/net-rerun/`, 2026-10-01, SharedEval d44e478) recorded each run's grants in its session
folder (`multi/.sharedeval-sharedos-session/grants.json`). This folder freezes them for all 720 runs, both models and
both arms, with the extraction they came from.

| File | Made by | What |
|---|---|---|
| `net_run_files.jsonl.gz` | `scripts/freeze/net_run_files/extract.py`, run read-only on the experiment VM | one line per run folder: grants.json as stored, the sha256 of every `POLICY.md` version the responder held, the sha256 of every responder reply; a final line with each policy text and every agent's `POLICY.md` and `grants.json` at d44e478 |
| `grants.jsonl.gz` | `scripts/freeze/net_run_files/freeze.py` | each run's grants.json as stored, with its sha256, keyed by model and run id |
| `summary.json` | same | the counts below |

Command: `ssh <host> "python3 - | gzip -9n" < scripts/freeze/net_run_files/extract.py > net_run_files.jsonl.gz`, then
`python3 scripts/freeze/net_run_files/freeze.py --extraction net_run_files.jsonl.gz`.

**Checks before anything is written.** Each of the 720 frozen contacts finds exactly one run folder with the same rung,
edge and arm, and no folder is left over. Each of the 1,306 judged replies finds its run's responder reply with the
same sequence and the recorded sha256. The d44e478 tree equals the frozen NET world's. Every `POLICY.md` version a
responder held is its rung's text: empty at D0, the 128-byte caution at D1, and at D2 the holder's own file at d44e478
(frozen in `../net-world/policies/`).

**Result.** Every run holds **16 grants** (9 for the responder, 7 for the requester), each with one capability of
**exact** scope. With grant ids, times and namespace ids dropped and the run's task id replaced by a placeholder, all
720 runs hold the **same** grant set. So the two arms of each of the 360 edge, rung and repetition pairs hold identical
grants up to the run's task identifier, and no grant's actions, namespaces, scopes or limits depend on who asks. The
task identifier itself names the asker (`NET-B-02--carlos_reyes--asked-by-<requester>`), so the two arms' task-scoped
grants point to differently named task resources. The paper's earlier "15 exact-scope grants per run" was one short.
