#!/bin/bash
# Re-run the relationship-v2 rescore over the 82 old-grid cells with quarantined-QA recovery enabled.
# Strict numbers must reproduce rescore-final-82.json exactly; recovery is reported separately.
set -eu
L=<vm>/luna; W=<vm>/work; REPO=$L/src/pact-azure
export PATH=$HOME/.local/node24/bin:$PATH
CELLS=""
for d in $W/v41-grid-out/*-rep1; do [ -f $d/.done ] || continue; c=$(basename $d); c=${c%-rep1}; CELLS="$CELLS --cell $c=$d"; done
cd $REPO
exec ./node_modules/.bin/tsx scripts/experiments/rescore-relationship-grid.ts $CELLS \
  --output $W/rescore-v41-recovered/rescore.json --detail-dir $W/rescore-v41-recovered/tasks --include-text --recover-quarantined-qa
