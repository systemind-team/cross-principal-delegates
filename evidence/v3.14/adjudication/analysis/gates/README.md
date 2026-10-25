# P1-2: gates and agreement, before adjudication (2026-10-07)

Protocol v2 §7. Inputs: the two frozen label sets in `labels/` (`labels/SHA256SUMS` sha256 b10ef3edbdafc952dbccafdc6fde267e46336a1e9e0666cac9b4bbe5414a100c),
the sealed key and planted answers (digests fixed before release in `packets/MANIFEST.json`), and `frame/cells.json`.

Commands, from the worktree root, with `<sealed>` = `<internal>`:

```
python3 scripts/adjudication/score.py --key <sealed>/key.jsonl --planted <sealed>/planted_answers.jsonl \
  --packets-a evidence/v3.14/adjudication/packets/annotator-A --labels-a evidence/v3.14/adjudication/labels/annotator-A \
  --packets-b evidence/v3.14/adjudication/packets/annotator-B --labels-b evidence/v3.14/adjudication/labels/annotator-B \
  --cells evidence/v3.14/adjudication/frame/cells.json --out <sealed>/pre-adjudication
python3 scripts/adjudication/gates_report.py <sealed>/pre-adjudication/summary.json evidence/v3.14/adjudication/analysis/gates
```

- `score.py` is unchanged since 6f23dc2 (sha256 1ff5588060a2319854dbeee97945a73c6e7e896ffec0791dd124b1d53422dcf2).
- `gates_report.py` (sha256 bc73c0ff0f0bb38069234ee64d7d265073470b67e1a35c654b13fa406bb9cd3f) was committed at 5e9a1d1, before it met the labels.
- Without the adjudication, score.py's rate blocks rest on partial final labels. They were not read and are not copied here. The full
  summary (sha256 7baf29c88ded6a6b42a6c93ad057770ecc0da35be39257b9e706c54bf89e5a60) stays in the sealed folder. The final run after
  adjudication replaces it, and its gate and agreement blocks must equal `gates.json`.

| File | What |
|---|---|
| `gates.json` | coverage, planted items (binary and per class), the four gates, and per stratum the 2×2 table, raw agreement, prevalence, kappa with its bootstrap interval, positive specific agreement, AC1, six-class and weighted kappa, and the label pairs that disagree |
| `gates.md` | the tables the room post cites |
