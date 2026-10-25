#!/usr/bin/env bash
. <vm>/env.sh
L=<vm>/runs/pack1; cd <vm>/repos/SharedEval-a1
MAXC=${MAXC:-16}
live(){ pgrep -u <user> -af 'sharedeval-cli\.ts multi' 2>/dev/null | grep -o -- '--run-id PK[^ ]*' | sort -u | wc -l; }
for pass in 1 2 3; do
  for c in "$L"/cfg/PK*.json; do
    RID=$(basename "$c" .json)
    python3 -c "
import json,sys
try:
  s=json.load(open('$L/cfg/runs/$RID/multi/summary.json')); u=s.get('usage') or {}
  sys.exit(0 if s.get('evaluationRows')==s.get('selectedTasks') and (u.get('contactCalls') or 0)>0 else 1)
except Exception: sys.exit(1)" && continue
    while [ "$(live)" -ge "$MAXC" ]; do sleep 5; done
    rm -rf "$L/cfg/runs/$RID"
    setsid nohup npm run sharedeval -- multi --config "$c" --run-id "$RID" > "$L/logs/$RID.p$pass.log" 2>&1 < /dev/null &
    sleep 0.3
  done
  while [ "$(live)" -gt 0 ]; do sleep 20; done
done
touch $L/DONE
