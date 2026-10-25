# The 60-task ladder behind Appendix D.6 (Table 33)

Frozen 2026-10-05, read-only from the experiment VM.

## What ran

- Model: `DeepSeek-V4-Flash-0731` on Azure, temperature 0, in both seats; strict profile (per-task grants);
  category grading; SharedEval revisions `26dd392` and `5db4182` (evaluator revision E2; per session in
  `revisions.json`, from each session's launch log; 958 of 960 sessions print one).
- Tasks: the 60 tasks of the probing grid's `SAMPLE60.json` (20 "high" and 40 "random"), as 20 three-task groups;
  each group asked by R0–R3, three repetitions: 240 sessions per arm.
- Arms in `<vm>/runs/ablation` (all 960 sessions valid):
  - `AB-D0T`: D0 (empty POLICY.md), strict profile. **Table 33's D0.**
  - `AB-D1T`: D1, the generic caution, strict profile. **Table 33's D1.**
  - `AB-D0S`, `AB-D2S`: D0 and D2 under the simple profile (the profile comparison the paper cut in September).
- **Table 33's D2** is not an arm of this run. It takes the same 60 tasks from the probing grid
  (`<vm>/runs/grid600`, D2, strict profile), where they share sessions with other tasks: the 660
  probing-grid sessions that contain one of the 60 tasks are frozen here too.

## Files

- `ablation.jsonl.xz`: `scripts/freeze/ablation/extract.py` (run on the VM with the script on stdin, output piped
  through xz). One line per session: the manifest entry, validity, run status, each task's evaluation, every
  message in ledger order and the sha256 of the POLICY.md versions the responder held; the last line holds the
  three policy texts (empty, D1, D2), `SAMPLE60.json` and both manifests' sha256. Uncompressed sha256
  b5fb7b52afcf594d384fd72219272dea075f81e23d141ee394b7c0cac70bcb43 (11,217,390 bytes).
- `revisions.json`: `scripts/freeze/ablation/revisions.py`; the SharedEval revision of each ablation session.
- `table33.json`: `scripts/pair_multi/ablation/table33.py`.

## Result

Every printed value of Table 33 reproduces (15 rates and the three security denominators 221, 226, 216). The
table's "Information security (S)" is the harness's category-graded whole-trajectory check (`benchmarkNoLeak`),
i.e. 100 minus whole-trajectory exposure; the glossary drops S.

Paired D0-versus-D1 tests (same task, requester and repetition; both arms ran their own sessions on the same
groups). Exact McNemar on task pairs, and the exact sign-flip test over the 20 groups (each group's improved minus
worsened, summed over requesters and repetitions), uncorrected:

| Metric | D0 → D1 | improved:worsened | McNemar p | sign-flip p (non-zero groups) |
|---|---|---|---|---|
| U | 84.8 → 76.6 | 6:22 | 0.0037 | 0.055 (9) |
| S (whole trajectory) | 10.9 → 29.6 | 39:6 | 5.4×10⁻⁷ | 0.0031 (14) |
| FR | 4.8 → 11.4 | 4:22 | 0.00053 | 0.023 (9) |
| AU | 78.8 → 75.4 | 4:8 | 0.39 | 0.31 (5) |
| AS | 60.4 → 63.8 | 9:5 | 0.42 | 0.56 (5) |

D2 shares sessions with other tasks, so it has no paired test against D0 or D1.
