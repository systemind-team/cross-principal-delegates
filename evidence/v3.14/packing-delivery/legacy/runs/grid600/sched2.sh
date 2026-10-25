#!/usr/bin/env bash
# grid600 调度器 v2。
#   v1 的 running() 用 pgrep -c 数进程，而一个 run 是 npm+tsx+node 三个进程，
#   于是 MAXC=20 实际只跑到 7 个。这版按 --run-id 去重计数。
#   完成扫描也从「每个 run 一个 python 进程」改成每轮一次。
. <vm>/env.sh
LANE=<vm>/runs/grid600
REPO=<vm>/repos/SharedEval-a1
MAXC=${MAXC:-20}
mkdir -p "$LANE/logs" "$LANE/attic"
cd "$REPO"

live_ids() { pgrep -u <user> -af 'sharedeval-cli\.ts multi' 2>/dev/null \
             | grep -o -- '--run-id [^ ]*' | awk '{print $2}' | sort -u; }
running()  { live_ids | wc -l; }

scan() {   # 一次扫完，吐出还没完成的 runId
  python3 - <<'PY'
import json, glob, os
LANE="<vm>/runs/grid600"
for p in sorted(glob.glob(f"{LANE}/cfg/G6-*.json")):
    rid=os.path.basename(p)[:-5]
    s=f"{LANE}/cfg/runs/{rid}/multi/summary.json"
    try:
        d=json.load(open(s)); u=d.get("usage") or {}
        if d.get("evaluationRows")==d.get("selectedTasks") and (u.get("contactCalls") or 0)>0:
            continue
    except Exception: pass
    print(rid)
PY
}

TOTAL=$(ls "$LANE/cfg"/G6-*.json | wc -l)
echo "$(date +%F_%T) v2 开跑: $TOTAL 个, MAXC=$MAXC"
for pass in 1 2 3 4 5 6 7 8; do
  TODO=$(scan)
  [ -z "$TODO" ] && { echo "$(date +%F_%T) 全部完成"; break; }
  echo "$(date +%F_%T) pass $pass: 待跑 $(echo "$TODO" | wc -l)"
  LIVE=$(live_ids)
  for RID in $TODO; do
    echo "$LIVE" | grep -qx "$RID" && continue
    while [ "$(running)" -ge "$MAXC" ]; do sleep 5; done
    [ -d "$LANE/cfg/runs/$RID" ] && mv "$LANE/cfg/runs/$RID" "$LANE/attic/$RID.p$pass.$(date +%H%M%S)" 2>/dev/null
    setsid nohup npm run sharedeval -- multi \
      --config "$LANE/cfg/$RID.json" --run-id "$RID" \
      > "$LANE/logs/$RID.p$pass.log" 2>&1 < /dev/null &
    sleep 0.3
  done
  while [ "$(running)" -gt 0 ]; do sleep 20; done
done
echo "$(date +%F_%T) 调度器结束"
