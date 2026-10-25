# Central-claim test: simulation check (PREREGISTRATION section 7)

| File | Script | Status |
|---|---|---|
| `results.json` | `scripts/p13/simulate.py 300 150 100` (seed 7) | leak entries stand; **false-refusal entries withdrawn** (2026-10-05) |
| `null_chi2_b0.json` | the β = 0 block of the same run | leak entries stand; **false-refusal entries withdrawn** |
| `results_pb.json` | `scripts/p13/simulate_pb.py 100 99 D1-FR D2-FR` (seed 11) | **withdrawn** |
| `results_fr_rerun.json` | `scripts/p13/simulate_fr_rerun.py chi2` | replaces the false-refusal entries of `results.json` |
| `results_pb_rerun.json` | `scripts/p13/simulate_fr_rerun.py pb` | replaces `results_pb.json` |

Why the false-refusal entries were withdrawn: the fitting code they were computed with (glmm before commit 59ab0b8)
found the cluster modes by full Newton steps, which oscillate in clusters whose outcomes are all 0 or all 1 when σ is
large. On the false-refusal designs, where events are rare, the optimizer then stopped at non-maxima
(`scripts/p13/check_modes_fix.py`; PREREGISTRATION section 8, correction row). The leak designs are not affected: the
old and the fixed code agree on every leak data set checked.

The rerun uses the original simulated data sets. It consumes the random generator in the original order and changes
only the fit. As a check, it also refits every false-refusal data set with the old code, which must reproduce the
withdrawn numbers exactly (`old_code_reproduction` and `old_code_reproduces_withdrawn_reject_chi2` in the rerun files).

Note on `results.json`'s `design` block: the keys `0` and `1` count matched and mismatched item–requester cells at
the policy rung (`design.strata`). They are not event counts.
