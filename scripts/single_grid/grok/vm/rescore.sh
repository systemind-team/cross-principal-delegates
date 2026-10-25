#!/bin/bash
# usage: rescore.sh <config-dir> <out-dir> <cell...>
# Lays each finished run out as <out-dir>/cells/<cell>/root/{config.yaml, runs/<cell>/{single,workspaces}} (the luna-cells shim),
# rescores with SharedEval 5aaa7f1 (relationship-v2 + quarantined-QA recovery), then scans refused replies for gold facts.
set -eu
C=$1; O=$2; shift 2
L=<vm>/luna; REPO=$L/src/pact-azure; P=<vm>/grok/paper
export PATH=$HOME/.local/node24/bin:$PATH
mkdir -p $O/cells
args=""
for cell in "$@"; do
  run=$C/runs/$cell
  [ -f $run/.done ] || { echo "$cell has no .done"; exit 1; }
  rm -rf $O/cells/$cell; d=$O/cells/$cell/root; mkdir -p $d/runs/$cell
  cp $C/$cell.yaml $d/config.yaml
  ln -s $run/single $d/runs/$cell/single; ln -s $run/workspaces $d/runs/$cell/workspaces
  args="$args --cell $cell=$O/cells/$cell"
done
cd $REPO
./node_modules/.bin/tsx scripts/experiments/rescore-relationship-grid.ts $args \
  --output $O/rescore.json --detail-dir $O/tasks --include-text --recover-quarantined-qa > $O/rescore.log 2>&1
SHAREDEVAL_DIR=$REPO ./node_modules/.bin/tsx $P/scripts/single_grid/grok/refusal_scan.mts $O/scan.json $O/tasks/*.tasks.jsonl
