#!/usr/bin/env bash
# Kernel check: the no-cost feasibility runs, end to end. No model is called: the scripted PAIR runner
# (SharedEval 8081e7e scripts/experiments/run-pair-scripted.ts, model id scripted/pair-probe-v1, base URL
# https://scripted.invalid) plays both actors through the real production run path and the real kernel.
#
# Runs, all on one config ($KC/feasibility/scripted-simple-32.yaml: PAIR-Q11 and PAIR-Q103, D2, R1, simple
# profile, 8 ticks; a copy of runs/mr-scripted/scripted-simple-32.yaml):
#   k2        8081e7e unchanged             on K2   (control)
#   k1pin     8081e7e + K1 pin              on K1
#   k1step1   + probe step 1 (audit schema) on K1
#   k1step2   + probe step 2 (catalog stub) on K1   (scoping only, not a port)
# and SharedEval's own real-kernel tests (`test:sharedos`) for every arm worktree.
# Outputs: $KC/feasibility/{runs,logs}/ and $KC/feasibility/summary.jsonl (scripts/kernel_check/audit_counts.py).
set -uo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
F=$KC/feasibility
mkdir -p "$F/logs" "$F/runs"
cp <vm>/runs/mr-scripted/scripted-simple-32.yaml "$F/scripted-simple-32.yaml"
# a detached worktree at probe step 1 (the runner refuses a dirty checkout, so each step is a commit)
if [ ! -d "$KC/se/e3-k1-step1" ]; then
  git -C "$KC/se/base" worktree add --quiet --detach "$KC/se/e3-k1-step1" "kc/e3-k1-probe~1"
  (cd "$KC/se/e3-k1-step1" && npm ci --no-audit --no-fund --loglevel=error >/dev/null)
fi
scripted() {  # $1 run label, $2 worktree, $3 kernel
  local id=feas-$1
  rm -rf "$F/runs/$id"
  ( cd "$KC/se/$2" &&
    SHAREDEVAL_SHAREDOS_DIR=$KC/kernels/$3 SHAREDEVAL_REQUIRE_SHAREDOS=1 SHAREDEVAL_MODEL_API_KEY=scripted-no-key \
    SHAREDEVAL_DEBUG_HEARTBEAT_CAUSE=1 nice -n 10 npx tsx scripts/experiments/run-pair-scripted.ts \
      --config "$F/scripted-simple-32.yaml" --run-id "$id" > "$F/logs/$id.log" 2>&1
    echo "exit=$?" >> "$F/logs/$id.log" )
  printf '%-10s %-14s %-4s %s | %s\n' "$1" "$2" "$3" "$(tail -1 "$F/logs/$id.log")" \
    "$(grep -E 'heartbeat [a-z_]+\]|scripted_summary' "$F/logs/$id.log" | grep -v '^\s*at ' | head -2 | tr '\n' ' ' | cut -c1-260)"
}
scripted k2      e3-k2       K2
scripted k1pin   e3-k1       K1
scripted k1step1 e3-k1-step1 K1
scripted k1step2 e3-k1-probe K1
python3 "$KC/scripts/audit_counts.py" "$F"/runs/feas-k2 "$F"/runs/feas-k1pin "$F"/runs/feas-k1step1 "$F"/runs/feas-k1step2 \
  > "$F/summary.jsonl"
for a in "e3-k2 K2" "e3-k1 K1" "e3-v1p V1P" "e1-k2 K2" "e1-k1 K1" "e1-v1p V1P" "e3-k1-step1 K1" "e3-k1-probe K1"; do
  set -- $a
  ( cd "$KC/se/$1" && SHAREDEVAL_SHAREDOS_DIR=$KC/kernels/$2 SHAREDEVAL_REQUIRE_SHAREDOS=1 \
      nice -n 10 npx tsx --test tests/execution/sharedos-loader.test.ts tests/execution/sharedos-runtime-conformance.test.ts \
      > "$F/logs/test-sharedos-$1.log" 2>&1 )
  printf 'test:sharedos %-12s on %-4s pass=%s fail=%s\n' "$1" "$2" \
    "$(grep -oE '^ℹ pass [0-9]+' "$F/logs/test-sharedos-$1.log" | grep -oE '[0-9]+')" \
    "$(grep -oE '^ℹ fail [0-9]+' "$F/logs/test-sharedos-$1.log" | grep -oE '[0-9]+')"
done
