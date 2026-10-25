# The prober's follow-up order in the PAIR II probing grid

`order.json` is written by `scripts/pair_multi/probing_order/strategy_order.py` from the frozen per-ask records,
`../multi-probing-records/contacts.jsonl.gz` (its sha256 is recorded in `order.json` and equals the entry in that
folder's `SHA256SUMS`). For each of the 2,396 protected question instances with per-ask records (run × task, category
gold `refuse`), the script lists the follow-up requests (`isRetry`) in tick order with the strategy the prober claimed.
Before writing, it checks that the per-strategy counts reproduce the Asks column of Table 37 (2,004 / 2,001 / 1,999 /
1,984 / 265).

Fields: `instances` (2,396) and `instances_reasked` (2,004, at least one follow-up); `asks_by_strategy`;
`position_by_strategy` (strategy → follow-up position → count; `repeat` was the fifth follow-up in 186 of its 265 uses,
the fourth in 54, the first in 21, the second in 3 and the third in 1); `most_common_sequences` (the ten most common
full sequences); `exactly_the_four_in_order` (1,721: the follow-ups are exactly business justification, urgency,
social appeal and decomposition, in that order); `began_with_the_four_in_order` (1,898: the first four follow-ups are
those four in that order) and `after_the_four` (what came fifth in those: nothing 1,721, repeat 176, an unlabelled
request 1). The paper cites these through `\multinum{order-*}` and `\multinum{repeat-pos*}`
(`scripts/pair_multi/counts.py`).

Regenerate: `python3 scripts/pair_multi/probing_order/strategy_order.py`
