#!/usr/bin/env bash
# Kernel check: how far apart the two evaluators are in the files a K1 port would touch, and how much of
# the K2->K1 divergence in the four loaded SharedOS packages is test code. Read-only git queries.
#   evaluator_divergence.sh <SharedEval clone> <SharedOS clone>
set -euo pipefail
SE=${1:-<vm>/kernel-check/se/base}
SO=${2:-<vm>/kernel-check/kernels/K1}
echo "== SharedEval 58829fe..8081e7e, files a K1 port touches"
git -C "$SE" diff --numstat 58829feb17289e4e3092dae44089831a51336c4a 8081e7e78e0e5acfe79830c606619faae53c3b0a -- \
  src/runner/v1/file-workflow-sharedos-evidence.ts src/runner/v1/sharedos-session-store.ts \
  src/runner/v1/file-workflow-artifacts.ts
echo "== SharedOS 3aa07e3..c74461c in packages/{contracts,core,os,runtime}/src: all, tests, non-tests (+ / -)"
git -C "$SO" diff --numstat 3aa07e33999b656a10ace294fd4e41df8cbc318e c74461c1c4b715fd60c18401100cd72362d3afc1 -- \
  packages/contracts/src packages/core/src packages/os/src packages/runtime/src |
  awk '{t=($3 ~ /\.test\.ts$/)?"test":"src"; a[t]+=$1; d[t]+=$2; n[t]++; A+=$1; D+=$2; N++}
       END {printf "all      %d files +%d -%d\ntests    %d files +%d -%d\nnon-test %d files +%d -%d\n", N, A, D, n["test"], a["test"], d["test"], n["src"], a["src"], d["src"]}'
