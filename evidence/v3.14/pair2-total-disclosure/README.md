# PAIR II ladder grid: total leak per block and rung

`td.json` is written by `scripts/pair_multi/ladder/total_disclosure.py` from
`evidence/v3.13/multi-table3/s4_rescore_table.json`. Per block (build × requester) and rung it gives the protected
questions scored at all three rungs (`n`), the decision leaks (a reply the requester recorded as an answer carries a
gold fact), the refusal-channel leaks (a reply recorded as a refusal, or an earlier reply of an answered task, carries a
gold fact not already in the conversation; echoes excluded) and their sum, the total leak (`total`), with each rate
rounded half away from zero from the counts (`*_pct`). `ranges` holds the per-rung ranges over the nine blocks that the
text cites. Tables 5 and 32 (`scripts/pair_multi/ladder/render_tables.py`) and `scripts/p13/rescore_pair2.py` read
this file. File and field names keep the earlier term "total disclosure" (`td`); the paper's term is total leak.

Regenerate: `python3 scripts/pair_multi/ladder/total_disclosure.py`
