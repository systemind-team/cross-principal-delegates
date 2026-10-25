#!/usr/bin/env bash
# P2-3 pre-pilot checks (host). Every gate that must pass before the pilot freezes and launches. No model
# calls; all local or VM read-only. Run from the repository root:
# bash scripts/pair_multi/spoof/adaptive/pre_pilot_checks.sh [<path to a SharedEval file-memory.ts for V1>]
set -eu
D=scripts/pair_multi/spoof/adaptive
MEM=${1:-}

echo "== build_frozen --check (frozen heartbeats reproduce; scrub + plain-asking guards run here) =="
python3 "$D/build_frozen.py" --check

echo "== scrub: no internal reference in any model-visible prompt =="
python3 "$D/test_prompt_scrub.py"

echo "== export scrub: no internal reference in the supplement files =="
python3 "$D/test_export_scrub.py"

echo "== the two heartbeats differ only by the AD and CT blocks =="
python3 "$D/test_heartbeats_diff.py" | tail -1

echo "== route-name normalization (slug vs served display name) =="
python3 "$D/test_route_names.py"

echo "== delivery / gate / claim-rate self-tests =="
python3 "$D/delivery_adaptive.py" --selftest
python3 "$D/gate_attacker.py" --selftest
python3 "$D/claim_rate.py" --selftest

echo "== P1-6 acceptance (O2, gate drop, question writes, fresh-fact) =="
python3 "$D/test_analyze_p16.py" | tail -1

if [ -n "$MEM" ]; then
  echo "== V1: the runtime parser accepts the heartbeat rows and rejects [obtained] =="
  node "$D/test_heartbeat_status.mjs" "$MEM" 2>/dev/null
fi

echo "== attacker upstream pinned (not the placeholder) =="
python3 - <<'PY'
import json
c = json.load(open("evidence/v3.14/multi-adaptive/frozen/model_config.json"))
slug = c["attacker"]["providerRouting"]["only"][0]
assert slug != "<attacker upstream>", "attacker upstream is still the placeholder"
print(" attacker upstream:", slug, "| responder:", c["responder"]["providerRouting"]["only"][0])
PY

echo "ALL PRE-PILOT CHECKS PASSED"
