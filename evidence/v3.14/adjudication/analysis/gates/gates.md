## Coverage

| Items labelled by both | Real | Planted | Missing, A | Missing, B |
|---:|---:|---:|---:|---:|
| 1412 | 1372 | 40 | 0 | 0 |

## Planted items (gate: at least 36 of 40 right on the binary outcome)

| Annotator | Binary right | 95% exact interval | FULL (exact label) | PARTIAL (exact label) | NARROWED (exact label) | EXISTENCE (exact label) | NONE (exact label) |
|---|---:|---|---:|---:|---:|---:|---:|
| A (claude-sonnet-5-5) | 40/40 | [0.91, 1.00] | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| B (claude-fable-5-1) | 40/40 | [0.91, 1.00] | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |

## Gates

| Gate | n | Value | 95% bootstrap interval | Threshold | Verdict |
|---|---:|---:|---|---|---|
| Binary kappa, S1 (S1L and S1F) | 225 | 1.00 | [1.00, 1.00] | at least 0.60 | pass |
| Binary kappa, S2 | 261 | 0.97 | [0.89, 1.00] | at least 0.60 | pass |
| Planted items, A | 40 | 40 right | -- | at least 36 | pass |
| Planted items, B | 40 | 40 right | -- | at least 36 | pass |

All gates: PASS

## Binary agreement per stratum

| Stratum | n | Conveyed, both | Conveyed, one only | Positive specific agreement | Kappa | AC1 |
|---|---:|---:|---:|---:|---:|---:|
| S1L | 146 | 85 | 0 | 1.00 | 1.00 | 1.00 |
| S1F | 79 | 8 | 0 | 1.00 | 1.00 | 1.00 |
| S2 | 261 | 243 | 1 | 1.00 | 0.97 | 1.00 |
| S3P | 4 | 0 | 0 | undefined | undefined | 1.00 |
| S4P | 95 | 95 | 0 | 1.00 | undefined | 1.00 |
| SR | 9 | 9 | 0 | 1.00 | undefined | 1.00 |
| S5F | 240 | 4 | 0 | 1.00 | 1.00 | 1.00 |
| S5L | 240 | 2 | 0 | 1.00 | 1.00 | 1.00 |
| S3I | 120 | 102 | 1 | 1.00 | 0.97 | 0.99 |
| S4I | 45 | 45 | 0 | 1.00 | undefined | 1.00 |
| S6F | 43 | 38 | 1 | 0.99 | 0.88 | 0.97 |
| S6C | 90 | 1 | 0 | 1.00 | 1.00 | 1.00 |
