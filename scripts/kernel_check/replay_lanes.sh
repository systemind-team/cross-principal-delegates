#!/usr/bin/env bash
# Kernel check, option B over whole lanes: replay every run directory of the given PAIR II lanes through K2
# and K1 (replay_decisions.mjs), all attempts included (a decision is a kernel decision whether or not its session
# ended valid). Since v2 the tool also replays strict-profile runs (deferred per-task responder grants); a run it
# cannot replay is reported with an error, never skipped silently.
#   replay_lanes.sh <outdir> <lane> [...]   lanes under <vm>/runs; writes <outdir>/lane-<lane>.jsonl
# A lane with no run directory is reported and skipped.
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
OUT=$1; shift
mkdir -p "$OUT"
for lane in "$@"; do
  out=$OUT/lane-$lane.jsonl
  list=$(mktemp)
  find <vm>/runs/$lane/cfg/runs -mindepth 2 -maxdepth 2 -type d -name multi | sort > "$list"
  if [ ! -s "$list" ]; then echo "$lane: no run directory, skipped"; rm -f "$list"; continue; fi
  : > "$out"
  xargs -n 50 nice -n 10 node "$KC/scripts/replay_decisions.mjs" --k2 "$KC/kernels/K2" --k1 "$KC/kernels/K1" < "$list" >> "$out"
  echo "$lane $(wc -l < "$list") folders, $(wc -l < "$out") results"
  rm -f "$list"
done
