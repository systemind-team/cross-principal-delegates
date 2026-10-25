#!/usr/bin/env python3
"""P1-6: the gateway ledger's record of the dedicated key (read only, on the VM). The key id is passed as an
argument; the key itself is never read.

Usage (VM): python3 ledger_cost_vm.py <key id> [<ledger sqlite>] > ledger_cost.json
"""
import json
import sqlite3
import sys

KEY = sys.argv[1]
DB = sys.argv[2] if len(sys.argv) > 2 else "<vm>/gw/telemetry.sqlite"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
q = lambda sql: c.execute(sql, (KEY,)).fetchall()
calls, cash, first, last = q("select count(*), coalesce(sum(cash_cost_usd),0), min(started_at), max(ended_at) "
                             "from model_calls where key_id=?")[0]
out = {
    "key": "the dedicated P1-6 key (id passed on the command line, withheld here)",
    "calls": calls, "cash_usd": round(cash, 4), "first_call": first, "last_call": last,
    "by_served_model": {f"{p} | {m}": {"calls": n, "cash_usd": round(s or 0, 4)} for p, m, n, s in q(
        "select served_provider, served_model, count(*), sum(cash_cost_usd) from model_calls where key_id=? group by 1, 2")},
    "pinned": dict(q("select pinned, count(*) from model_calls where key_id=? group by 1")),
    "by_outcome": {str(o): n for o, n in q("select outcome, count(*) from model_calls where key_id=? group by 1")},
    "http_status_not_200": {str(h): n for h, n in q(
        "select http_status, count(*) from model_calls where key_id=? and coalesce(http_status, 0) != 200 group by 1")},
    "wasted": {str(w): {"calls": n, "cash_usd": round(s or 0, 4)} for w, n, s in q(
        "select wasted, count(*), sum(cash_cost_usd) from model_calls where key_id=? group by 1")},
}
json.dump(out, sys.stdout, indent=1, default=str)
print()
