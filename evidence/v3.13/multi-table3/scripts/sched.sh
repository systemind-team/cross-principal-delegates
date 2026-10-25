#!/usr/bin/env bash
# t3simple scheduler -- Table 3 under the simple profile (an author, 2026-09-28: "用 simple 重跑 Table 3").
#   MODE=pilot  -> pilot-<B>.txt (groups g004, g100), terminal marker PILOT_DONE
#   MODE=full   -> jobs-<B>.txt  (all 50 groups),     terminal marker DONE
#  * Three build loops in parallel; caps DS 16 / GLM 24 / GROK 16 (Grok is TPM-bound; more only buys 429s).
#  * Pass 1 runs every job not already run. Pass 2 retries ONCE ("<id>-x2") each invalid pass-1 run
#    (evaluationRows != selectedTasks or contactCalls == 0).
#  * GLM cash guard every 10 GLM launches; if it trips, GLM stops launching and COSTGUARD is written.
#  * Provider errors other than 429 are kept under fetchlog/<run id>/ (request body + error body).
#  * Never deletes anything; skips a run id whose run dir already exists.
#  * Terminal marker is written as tmp -> mv, then verified; both outcomes are logged. ALIVE is touched
#    every 60 s while the scheduler lives, so a watcher can tell "finished" from "died".
set -u
MODE=${1:?pilot or full}
L=<vm>/runs/t3simple
case "$MODE" in pilot) LIST=pilot; MARK=PILOT_DONE;; full) LIST=jobs; MARK=DONE;; *) echo "bad mode"; exit 2;; esac
. <vm>/env.sh >/dev/null 2>&1
cd <vm>/repos/SharedEval-a1 || exit 1
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "dirty tracked checkout, abort"; exit 2; fi
AZ_KEY="$SHAREDEVAL_MODEL_API_KEY"
OR_KEY="$OPENROUTER_API_KEY"
declare -A CAP=([DS]=16 [GLM]=24 [GROK]=16)
log(){ echo "$(date -u +%FT%TZ) $*" >> "$L/sched.log"; }
inflight(){ pgrep -u <user> -af "sharedeval-cli\.ts multi --config $L/cfg/" 2>/dev/null | grep -o -- "--run-id S4-$1-[^ ]*" | sort -u | wc -l; }
is_valid(){ python3 -c '
import json,sys
try:
    s=json.load(open(sys.argv[1])); u=s.get("usage") or {}
    sys.exit(0 if s.get("evaluationRows")==s.get("selectedTasks") and (u.get("contactCalls") or 0)>0 else 1)
except Exception: sys.exit(1)' "$L/cfg/runs/$1/multi/summary.json"; }
launch(){ local RID=$1 K=$2 BASE=${1%-x2}
  local C="$L/cfg/$BASE.json"
  if [ ! -f "$C" ]; then log "no config for $RID"; return 1; fi
  if [ -e "$L/cfg/runs/$RID" ]; then return 1; fi
  ( export SHAREDEVAL_MODEL_API_KEY="$K"
    # Errors-only provider log (request + error body of any non-429 failure); behaviour-neutral.
    export FETCHLOG_DIR="$L/fetchlog/$RID" FETCHLOG_MODE=errors NODE_OPTIONS="--import <vm>/runs/fetchlog.mjs"
    setsid nohup bash -c '
      s=$(date +%s.%N)
      npm run sharedeval -- multi --config "$1" --run-id "$2" > "$3" 2>&1 < /dev/null
      rc=$?
      e=$(date +%s.%N)
      printf "%s\t%s\t%s\t%s\n" "$2" "$s" "$e" "$rc" >> "$4"
    ' _ "$C" "$RID" "$L/logs/$RID.log" "$L/times.tsv" > /dev/null 2>&1 < /dev/null & )
  log "started $RID"
  return 0
}
run_build(){ local B=$1 cap=${CAP[$1]} K n=0 m=0 RID RETRY
  if [ "$B" = GLM ]; then K="$OR_KEY"; else K="$AZ_KEY"; fi
  log "$B pass 1 begins ($MODE, cap $cap)"
  while read -r RID RETRY; do
    if [ -z "$RID" ]; then continue; fi
    if [ "$B" = GLM ] && [ $((n % 10)) -eq 0 ]; then
      if ! python3 "$L/guard.py" >> "$L/sched.log" 2>&1; then log "GLM cash guard tripped; GLM stops launching"; break; fi
    fi
    while [ "$(inflight "$B")" -ge "$cap" ]; do sleep 5; done
    if launch "$RID" "$K"; then n=$((n+1)); sleep 1; fi
  done < "$L/$LIST-$B.txt"
  while [ "$(inflight "$B")" -gt 0 ]; do sleep 20; done
  log "$B pass 1 finished ($n launched)"
  if [ "$B" = GLM ] && [ -e "$L/COSTGUARD" ]; then log "GLM pass 2 skipped (cost guard)"; return 0; fi
  while read -r RID RETRY; do
    if [ "$RETRY" != 1 ] || [ ! -e "$L/cfg/runs/$RID" ]; then continue; fi
    if is_valid "$RID"; then continue; fi
    while [ "$(inflight "$B")" -ge "$cap" ]; do sleep 5; done
    if launch "$RID-x2" "$K"; then m=$((m+1)); sleep 1; fi
  done < "$L/$LIST-$B.txt"
  while [ "$(inflight "$B")" -gt 0 ]; do sleep 20; done
  log "$B pass 2 finished ($m retries)"
  return 0
}
alive(){ while :; do date -u +%FT%TZ > "$L/ALIVE"; python3 "$L/progress.py" "$LIST" > "$L/PROGRESS.tmp" 2>/dev/null && mv -f "$L/PROGRESS.tmp" "$L/PROGRESS"; sleep 60; done; }
log "scheduler start mode $MODE pid $$ rev $(git rev-parse --short HEAD)"
echo $$ > "$L/SCHED.pid"
alive & AL=$!
run_build DS & P1=$!
run_build GLM & P2=$!
run_build GROK & P3=$!
wait $P1 $P2 $P3
kill $AL 2>/dev/null
python3 "$L/progress.py" "$LIST" > "$L/PROGRESS" 2>/dev/null
tmp="$L/$MARK.tmp"
echo "$MARK $(date -u +%FT%TZ): every $MODE run has finished, including one retry per invalid run." > "$tmp"
cat "$L/PROGRESS" >> "$tmp"
if [ -e "$L/COSTGUARD" ]; then echo "COSTGUARD tripped: $(cat "$L/COSTGUARD")" >> "$tmp"; fi
mv -f "$tmp" "$L/$MARK"
if [ -s "$L/$MARK" ] && [ ! -e "$tmp" ]; then log "$MARK verified ($(wc -c < "$L/$MARK") bytes)"; else log "$MARK rename FAILED"; fi
