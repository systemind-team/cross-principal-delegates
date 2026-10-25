#!/bin/bash
# Offline relationship-v2 rescore of the 28 gpt-5.6-luna cells (rep1), strict + quarantined-QA recovery.
set -eu
L=<vm>/luna; W=<vm>/work; REPO=$L/src/pact-azure
export PATH=$HOME/.local/node24/bin:$PATH
CELLS=""
for d in $W/luna-cells/luna-d*-r*; do c=$(basename $d); CELLS="$CELLS --cell $c=$d"; done
cd $REPO
exec ./node_modules/.bin/tsx scripts/experiments/rescore-relationship-grid.ts $CELLS \
  --output $W/rescore-luna/rescore.json --detail-dir $W/rescore-luna/tasks --include-text --recover-quarantined-qa
