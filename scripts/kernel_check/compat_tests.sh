#!/usr/bin/env bash
# Kernel check: API compatibility of each SharedEval arm with its kernel, no model call.
#   compat_tests.sh <arm> <kernel> [suite]
# suite = sharedos (default: SharedEval's own `test:sharedos`, the loader and runtime-conformance tests,
#         with SHAREDEVAL_REQUIRE_SHAREDOS=1 so a missing or rejected kernel fails instead of skipping)
#       | full     (SharedEval's whole `npm test`; compare failure sets between arms, never absolute counts)
#       | full1    (the same files with --test-concurrency=1)
# Output: $KC/compat/<arm>-<suite>.log and a one-line TAP summary.
set -uo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
arm=$1 kernel=$2 suite=${3:-sharedos}
mkdir -p "$KC/compat"
log=$KC/compat/$arm-$suite.log
cd "$KC/se/$arm" || exit 2
export SHAREDEVAL_SHAREDOS_DIR=$KC/kernels/$kernel SHAREDEVAL_REQUIRE_SHAREDOS=1
unset SHAREDEVAL_MODEL_API_KEY
case "$suite" in
  sharedos) nice -n 10 npx tsx --test tests/execution/sharedos-loader.test.ts tests/execution/sharedos-runtime-conformance.test.ts > "$log" 2>&1 ;;
  full) nice -n 10 npm test > "$log" 2>&1 ;;
  full1) # the same files as `npm test`, one test file at a time (lighter on a shared VM)
    cmd=$(node -e 'console.log(require("./package.json").scripts.test.replace("tsx --test", "npx tsx --test --test-concurrency=1"))')
    nice -n 10 bash -c "$cmd" > "$log" 2>&1 ;;
  *) echo "unknown suite $suite"; exit 2 ;;
esac
rc=$?
printf '%s %s %s rc=%s %s\n' "$arm" "$kernel" "$suite" "$rc" \
  "$(grep -E '^# (tests|pass|fail|skipped|cancelled)' "$log" | tr '\n' ' ')"
