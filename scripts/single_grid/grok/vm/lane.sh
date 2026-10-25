#!/bin/bash
# usage: lane.sh <config-dir> <cell...>   runs each <config-dir>/<cell>.yaml once; output <config-dir>/runs/<cell>
# grok-4.6 via Azure, native node 24, SharedEval 5aaa7f1 (runtime 40f4f01), SharedOS 3aa07e3. Skips cells with .done.
set -u
C=$1; shift
L=<vm>/luna; REPO=$L/src/pact-azure
export PATH=$HOME/.local/node24/bin:$PATH
set -a; . $L/.env.azure; set +a
export SHAREDEVAL_MODEL_API_KEY="$AZURE_LUNA_API_KEY"
export SHAREDEVAL_SHAREDOS_DIR=$L/src/sharedos-3aa07e3
mkdir -p "$C/../logs"
for cell in "$@"; do
  out="$C/runs/$cell"; log="$C/../logs/$cell.log"
  if [ -f "$out/.done" ]; then echo "$(date -u +%FT%TZ) SKIP $cell"; continue; fi
  if [ -d "$out" ]; then echo "$(date -u +%FT%TZ) REFUSE $cell: $out exists without .done (single run; inspect before rerunning)"; continue; fi
  echo "$(date -u +%FT%TZ) START $cell"
  ( cd "$REPO" && timeout 6h ./node_modules/.bin/tsx src/runner/v1/sharedeval-cli.ts single --config "$C/$cell.yaml" --run-id "$cell" ) > "$log" 2>&1
  rc=$?
  echo "$(date -u +%FT%TZ) EXIT=$rc $cell"
  if [ $rc -eq 0 ] && [ -d "$out/single" ]; then touch "$out/.done"; fi
done
echo "$(date -u +%FT%TZ) LANE DONE: $*"
