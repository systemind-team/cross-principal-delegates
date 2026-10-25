# PAIR II counts for Appendix D's hand-written tables

`macros.json` is written by `scripts/pair_multi/counts.py` with `tables/pair_multi_numbers.tex` (`\multinum{key}`).
Inputs: `../probing-strategy-order/order.json` and `../packing-delivery/` (with the session-validity and scoring rules
of `scripts/freeze/packing_delivery/recompute.py`). Keys:

- `order-*`, `repeat-pos*`: the prober's follow-up order (Table 37's note). Exactly the four
  non-repeat strategies in order in 1,721 of the 2,004 instances followed up; began with them in 1,898 (then repeat
  in 176, an unlabelled request in 1); repeat's 265 uses by position 21 / 3 / 1 / 54 / 186.
- `pack-*`: the packing study (Table 43). The 60-task set; 59 tasks every arm scored at least once (Q251, a
  protected question the one-task arm never scored, is left out); 21 protected questions among the 59, 22 among the 60.
- `rel-*`: the probing grid's delivery per requester (Table 36), over the tasks in the 2,399 completed
  sessions (the base Table 36 prints: R3 78.4%, unscored 21.6%, 942 unscored tasks in all) and over all attempted
  tasks (`-att`: R3 78.2%, 21.8%, 945 in all; the 3 more are the failed session's tasks). R0–R2 are the same on both
  bases.

Regenerate: `python3 scripts/pair_multi/counts.py`
