#!/usr/bin/env bash
# PAIR II told-ladder scheduler (the identity rerun's, with the checkout, lane and run prefix as parameters).
#   sched.sh pilot  -> pilot.txt, terminal marker PILOT_DONE
#   sched.sh full   -> jobs.txt,  terminal marker DONE
# * At most CAP sessions in flight, counted by this lane's config directory only.
# * Cash guard before every launch: the gateway ledger's provider-reported spend on this lane's
#   key; at STOP_USD no further session starts (the key's own hard cap is $20).
# * Pass 2 retries once ("<id>-x2") each pass-1 run that is invalid
#   (evaluationRows != selectedTasks or contactCalls == 0).
# * Never deletes anything; skips a run id whose run directory exists.
set -u
MODE=${1:?pilot or full}
L=${LANE_DIR:-<vm>/runs/pair2told}
SE_DIR=${SE_DIR:-<vm>/repos/SharedEval-told}
SE_REV=${SE_REV:-4565add}
PREFIX=${PREFIX:-T3-}
KEY_FILE=<vm>/gw/pair_key.txt
KEY_ID=<key-id>
CAP=${CAP:-16}
STOP_USD=${STOP_USD:-18}
case "$MODE" in pilot) LIST=pilot; MARK=PILOT_DONE;; full) LIST=jobs; MARK=DONE;; *) echo "bad mode"; exit 2;; esac
. <vm>/env.sh >/dev/null 2>&1
cd "$SE_DIR" || exit 1
[ "$(git rev-parse --short=7 HEAD)" = "$SE_REV" ] || { echo "SharedEval is not at $SE_REV"; exit 2; }
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "dirty tracked checkout, abort"; exit 2; fi
mkdir -p "$L/logs"
log(){ echo "$(date -u +%FT%TZ) $*" >> "$L/sched.log"; }
inflight(){ pgrep -u <user> -af "sharedeval-cli\.ts multi --config $L/cfg/" 2>/dev/null | grep -o -- "--run-id $PREFIX[^ ]*" | sort -u | wc -l; }
spent(){ python3 - "$KEY_ID" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:<vm>/gw/telemetry.sqlite?mode=ro", uri=True)
print(round(c.execute("select coalesce(sum(cash_cost_usd),0) from model_calls where key_id=?", (sys.argv[1],)).fetchone()[0], 4))
PY
}
over_budget(){ python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) >= float(sys.argv[2]) else 1)' "$(spent)" "$STOP_USD"; }
is_valid(){ python3 -c '
import json,sys
try:
    s=json.load(open(sys.argv[1])); u=s.get("usage") or {}
    sys.exit(0 if s.get("evaluationRows")==s.get("selectedTasks") and (u.get("contactCalls") or 0)>0 else 1)
except Exception: sys.exit(1)' "$L/cfg/runs/$1/multi/summary.json"; }
launch(){ local RID=$1 BASE=${1%-x2}
  local C="$L/cfg/$BASE.json"
  [ -f "$C" ] || { log "no config for $RID"; return 1; }
  [ -e "$L/cfg/runs/$RID" ] && return 1
  ( export SHAREDEVAL_MODEL_API_KEY="$(cat "$KEY_FILE")"
    setsid nohup bash -c '
      s=$(date +%s.%N)
      npm run sharedeval -- multi --config "$1" --run-id "$2" > "$3" 2>&1 < /dev/null
      rc=$?
      printf "%s\t%s\t%s\t%s\n" "$2" "$s" "$(date +%s.%N)" "$rc" >> "$4"
    ' _ "$C" "$RID" "$L/logs/$RID.log" "$L/times.tsv" > /dev/null 2>&1 < /dev/null & )
  log "started $RID"
}
run_pass(){ local PASS=$1 n=0 RID
  while read -r RID; do
    [ -z "$RID" ] && continue
    if [ "$PASS" = 2 ]; then
      [ -e "$L/cfg/runs/$RID" ] || continue
      is_valid "$RID" && continue
      RID="$RID-x2"
    fi
    if over_budget; then log "cash guard: \$$(spent) >= \$$STOP_USD, pass $PASS stops launching"; touch "$L/COSTGUARD"; break; fi
    while [ "$(inflight)" -ge "$CAP" ]; do sleep 5; done
    if launch "$RID"; then n=$((n+1)); sleep 1; fi
  done < "$L/$LIST.txt"
  while [ "$(inflight)" -gt 0 ]; do sleep 20; done
  log "pass $PASS finished ($n launched, spent \$$(spent))"
}
log "scheduler start mode $MODE pid $$ rev $(git rev-parse --short HEAD)"
echo $$ > "$L/SCHED.pid"
run_pass 1
[ -e "$L/COSTGUARD" ] || run_pass 2
echo "$(date -u +%FT%TZ) spent \$$(spent)" > "$L/$MARK.tmp" && mv -f "$L/$MARK.tmp" "$L/$MARK"
log "terminal marker $MARK written"
