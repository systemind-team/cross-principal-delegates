#!/usr/bin/env bash
# P1-6 impersonation arms: scheduler (the identity comparison's, with a dedicated key, a kill switch and a
# watchdog).
#   sched.sh pilot     -> pilot.txt,    terminal marker PILOT_DONE    (no rerun pass)
#   sched.sh full      -> jobs.txt,     terminal marker DONE          (one rerun per invalid session)
#   sched.sh optional  -> optional.txt, terminal marker OPTIONAL_DONE (one rerun per invalid session)
# A session is valid when every task was evaluated, it made at least one contact, and every provider call was
# served by Relace (extract_vm.py uses the same rule to pick the attempt it scores).
#
# Required environment: SPOOF_KEY_ID (the dedicated key's id, read from the ledger, never the key itself),
# STOP_USD and KILL_USD (absolute spend on that key at which launching stops, and at which every session of
# this lane is ended; the key's own cap is the last stop).
# * The key file is read only inside each session's own environment; nothing prints it.
# * PATH is set to the VM's Node toolchain explicitly; the repository's .env is not sourced, so no other
#   credential enters the run. SHAREDEVAL_SHAREDOS_DIR names the pinned kernel checkout (K2).
# * At most CAP sessions in flight, counted by this lane's config directory only.
# * A watchdog ends any session running longer than MAX_SESSION_S; a monitor ends every session of the lane
#   and writes KILLED once the key's spend reaches KILL_USD.
# * Never deletes anything; skips a run id whose run directory exists.
set -u
MODE=${1:?pilot, full or optional}
L=${LANE_DIR:-<vm>/runs/pair2spoof}
SE_DIR=${SE_DIR:-<vm>/repos/SharedEval-spoof}
SE_REV=${SE_REV:?SharedEval revision (7 characters)}
KEY_FILE=${KEY_FILE:-<vm>/gw/spoof_key.txt}
KEY_ID=${SPOOF_KEY_ID:?the dedicated key id}
STOP_USD=${STOP_USD:?spend at which launching stops}
KILL_USD=${KILL_USD:?spend at which every session is ended}
CAP=${CAP:-24}
MAX_SESSION_S=${MAX_SESSION_S:-2400}
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:/usr/local/bin:/usr/bin:/bin
export SHAREDEVAL_SHAREDOS_DIR=${SHAREDEVAL_SHAREDOS_DIR:-<vm>/repos/SharedOS-3aa07e3}
export SHAREDEVAL_REQUIRE_SHAREDOS=1
case "$MODE" in
  pilot) LIST=pilot; MARK=PILOT_DONE; PASSES=1;;
  full) LIST=jobs; MARK=DONE; PASSES=2;;
  optional) LIST=optional; MARK=OPTIONAL_DONE; PASSES=2;;
  *) echo "bad mode"; exit 2;;
esac
cd "$SE_DIR" || exit 1
[ "$(git rev-parse --short=7 HEAD)" = "$SE_REV" ] || { echo "SharedEval is not at $SE_REV"; exit 2; }
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "dirty tracked checkout, abort"; exit 2; fi
[ -r "$KEY_FILE" ] || { echo "key file not readable"; exit 2; }
mkdir -p "$L/logs"
log(){ echo "$(date -u +%FT%TZ) $*" >> "$L/sched.log"; }
lane_pids(){ pgrep -u "$(id -un)" -f "sharedeval-cli\.ts multi --config $L/cfg/" 2>/dev/null | grep -v "^$$\$" || true; }
inflight(){ pgrep -u "$(id -un)" -af "sharedeval-cli\.ts multi --config $L/cfg/" 2>/dev/null \
  | grep -o -- "--run-id SP-[^ ]*" | sort -u | wc -l; }
spent(){ python3 - "$KEY_ID" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:<vm>/gw/telemetry.sqlite?mode=ro", uri=True)
print(round(c.execute("select coalesce(sum(cash_cost_usd),0) from model_calls where key_id=?", (sys.argv[1],)).fetchone()[0], 4))
PY
}
ge(){ python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) >= float(sys.argv[2]) else 1)' "$1" "$2"; }
is_valid(){ python3 -c '
import glob,json,sys
m=sys.argv[1]
try:
    s=json.load(open(m+"/summary.json")); u=s.get("usage") or {}
    ok=s.get("evaluationRows")==s.get("selectedTasks") and (u.get("contactCalls") or 0)>0
    for f in glob.glob(m+"/.sharedeval-file-workflow/records/record-*.json"):
        tel=((json.load(open(f)).get("payload") or {}).get("privateEvidence") or {}).get("providerTelemetry") or {}
        ok=ok and all(q.get("provider")=="Relace" for v in tel.values() for q in (v or {}).get("requests") or [])
    sys.exit(0 if ok else 1)
except Exception: sys.exit(1)' "$L/cfg/runs/$1/multi"; }
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
monitor(){ # kill switch and watchdog, every 20 s, until the scheduler exits
  while kill -0 "$1" 2>/dev/null; do
    if ge "$(spent)" "$KILL_USD"; then
      log "kill switch: spend \$$(spent) >= \$$KILL_USD; ending every session of this lane"
      touch "$L/KILLED"; touch "$L/COSTGUARD"
      for p in $(lane_pids); do kill -TERM "$p" 2>/dev/null; done
    fi
    for p in $(lane_pids); do
      e=$(ps -o etimes= -p "$p" 2>/dev/null | tr -d ' ')
      if [ -n "$e" ] && [ "$e" -gt "$MAX_SESSION_S" ]; then
        log "watchdog: pid $p ran ${e}s > ${MAX_SESSION_S}s; ended"; kill -TERM "$p" 2>/dev/null
      fi
    done
    sleep 20
  done
}
run_pass(){ local PASS=$1 n=0 RID
  while read -r RID; do
    [ -z "$RID" ] && continue
    [ -e "$L/KILLED" ] && break
    if [ "$PASS" = 2 ]; then
      [ -e "$L/cfg/runs/$RID" ] || continue
      is_valid "$RID" && continue
      RID="$RID-x2"
    fi
    if ge "$(spent)" "$STOP_USD"; then log "cash guard: \$$(spent) >= \$$STOP_USD, pass $PASS stops launching"; touch "$L/COSTGUARD"; break; fi
    while [ "$(inflight)" -ge "$CAP" ]; do sleep 5; done
    if launch "$RID"; then n=$((n+1)); sleep 1; fi
  done < "$L/$LIST.txt"
  while [ "$(inflight)" -gt 0 ]; do sleep 20; done
  log "pass $PASS finished ($n launched, spent \$$(spent))"
}
log "scheduler start mode $MODE pid $$ rev $(git rev-parse --short HEAD) spent at start \$$(spent)"
echo $$ > "$L/SCHED.pid"
monitor $$ &
run_pass 1
if [ "$PASSES" = 2 ] && [ ! -e "$L/COSTGUARD" ]; then run_pass 2; fi
echo "$(date -u +%FT%TZ) spent \$$(spent)" > "$L/$MARK.tmp"
mv -f "$L/$MARK.tmp" "$L/$MARK"
log "terminal marker $MARK written"
