#!/usr/bin/env bash
# Kernel check, option B: is the replay able to see a difference at all, and is it deterministic?
# Over the 80 sampled ladder sessions (the folder analyze_s4.py chose for each sampled slot; list in <folders>):
#   none          replay_decisions.mjs v3 without mutation: every field except core_versions must equal the v2
#                 line of the same folder in <v2 lane file> (the replay is deterministic and v3 = v2);
#   drop-matched  K1 no longer sees the grant each record matched: allowed records must stop agreeing;
#   exhaust       K1 sees every bounded grant as used up: allowed records on bounded grants must stop agreeing.
# Usage: replay_sensitivity.sh <folders.txt> <v2 lane-t3simple.jsonl> <outdir>
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
LIST=$1 V2=$2 OUT=$3
mkdir -p "$OUT"
for mode in none drop-matched exhaust; do
  flag=(); [ "$mode" = none ] || flag=(--mutate-k1 "$mode")
  xargs -n 40 nice -n 10 node "$KC/scripts/replay_decisions.mjs" --k2 "$KC/kernels/K2" --k1 "$KC/kernels/K1" \
    "${flag[@]}" < "$LIST" > "$OUT/sampled80-$mode.jsonl"
done
python3 - "$OUT" "$V2" <<'PY'
import json, sys
out, v2 = sys.argv[1], sys.argv[2]
ref = {}
for line in open(v2):
    r = json.loads(line)
    ref[r["run"]] = r
res = {}
for mode in ("none", "drop-matched", "exhaust"):
    rows = [json.loads(l) for l in open(f"{out}/sampled80-{mode}.jsonl")]
    t = {"runs": len(rows), "decisions": sum(r["decisions"] for r in rows),
         "recorded_allowed": sum(r["recorded_allowed"] for r in rows),
         "k2_equals_recorded": sum(r["k2_equals_recorded"] for r in rows),
         "k1_equals_k2": sum(r["k1_equals_k2"] for r in rows),
         "core_versions": sorted({json.dumps(r["core_versions"], sort_keys=True) for r in rows})}
    if mode == "none":
        strip = lambda r: {k: v for k, v in r.items() if k not in ("core_versions", "mutate_k1")}
        t["lines_equal_to_v2"] = sum(strip(r) == ref.get(r["run"]) for r in rows)
    else:
        reasons = {}
        for r in rows:
            for d in r["differences"]:
                if d["k1"] != d["k2"]:
                    key = f"recorded {'allowed' if d['recorded']['allowed'] else 'denied'} -> K1 " + (
                        "allowed, other grant" if d["k1"]["allowed"] else f"denied {d['k1']['reason']}")
                    reasons[key] = reasons.get(key, 0) + 1
        t["k1_disagreements_by_kind"] = reasons
    res[mode] = t
json.dump(res, open(f"{out}/sensitivity.json", "w"), indent=1, sort_keys=True)
print(json.dumps(res, indent=1, sort_keys=True))
PY
