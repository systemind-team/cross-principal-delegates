#!/usr/bin/env bash
# Kernel check: reference cost per PAIR II session on the brief's route (gateway -> OpenRouter, pinned to
# Relace, deepseek/deepseek-v4-flash-0731), from the gateway ledger's provider-reported cash cost.
# Two earlier runs on that route used one key: the identity comparison (2026-10-02, including its stopped
# unpinned first launch, lanes pair2id + pair2id2) and the header ladder (2026-10-03, lane pair2told).
# Spend is split by UTC day; sessions are the lanes' run directories (retries included).
# Also prints the kernel-check key's own spend so far. Read-only (sqlite opened with mode=ro). No key is read.
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
R=<vm>/runs
n_id=$(( $(ls -d $R/pair2id/cfg/runs/*/ 2>/dev/null | wc -l) + $(ls -d $R/pair2id2/cfg/runs/*/ | wc -l) ))
n_told=$(ls -d $R/pair2told/cfg/runs/*/ | wc -l)
python3 - "$n_id" "$n_told" <<'PY'
import json, sqlite3, sys
n_id, n_told = int(sys.argv[1]), int(sys.argv[2])
c = sqlite3.connect("file:<vm>/gw/telemetry.sqlite?mode=ro", uri=True)
def window(key, a, b):
    n, usd = c.execute("select count(*), coalesce(sum(cash_cost_usd),0) from model_calls where key_id=? and started_at>=? and started_at<?", (key, a, b)).fetchone()
    return n, usd
idn, idusd = window("<key-id>", "2026-10-02T00:00:00Z", "2026-10-03T00:00:00Z")
tn, tusd = window("<key-id>", "2026-10-03T00:00:00Z", "2026-10-04T00:00:00Z")
kn, kusd = window("<key-id>", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
print(json.dumps({
    "identity_comparison_2026_10_02": {"calls": idn, "cash_usd": round(idusd, 4), "sessions": n_id,
                                        "usd_per_session": round(idusd / n_id, 5)},
    "header_ladder_2026_10_03": {"calls": tn, "cash_usd": round(tusd, 4), "sessions": n_told,
                                 "usd_per_session": round(tusd / n_told, 5)},
    "kernel_check_key_so_far": {"calls": kn, "cash_usd": round(kusd, 4)},
}, indent=1))
PY
