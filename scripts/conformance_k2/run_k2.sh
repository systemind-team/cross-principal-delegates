#!/usr/bin/env bash
# Run kernel K2's own scripted conformance suite (SharedOS 3aa07e3, the kernel every experiment loaded)
# and copy its outputs into evidence/v3.14/conformance-k2/. The scripted suite makes no model call.
#
# Usage: scripts/conformance_k2/run_k2.sh <SharedOS git repo> <scratch dir>
#   The repo is only read: the run happens in a fresh local clone under <scratch dir>.
set -euo pipefail
REPO=$1
WORK=$2
REV=3aa07e33999b656a10ace294fd4e41df8cbc318e
HERE=$(cd "$(dirname "$0")/../.." && pwd)
OUT="$HERE/evidence/v3.14/conformance-k2"
CLONE="$WORK/sharedos-k2"

rm -rf "$CLONE"
git clone --quiet --local --no-checkout "$REPO" "$CLONE"
git -C "$CLONE" checkout --quiet "$REV"
test "$(git -C "$CLONE" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$CLONE" status --porcelain)"
(cd "$CLONE" && pnpm install --frozen-lockfile --offline)

mkdir -p "$OUT"
{
  echo "revision $(git -C "$CLONE" rev-parse HEAD)"
  echo "tree $(git -C "$CLONE" rev-parse 'HEAD^{tree}')"
  echo "node $(cd "$CLONE" && node --version)"
  echo "pnpm $(cd "$CLONE" && pnpm --version)"
  echo "os $(uname -srm)"
} > "$OUT/environment.txt"

# 1. Build, run the suite, and compare the fresh manifest with the one committed at K2 (no write).
(cd "$CLONE" && node scripts/conformance.mjs --check --strict) 2>&1 | sed "s#$CLONE#<clone>#g" > "$OUT/check-strict.txt"
# 2. Run again and write the manifest and the per-cell evidence.
(cd "$CLONE" && node scripts/conformance.mjs --no-build) 2>&1 | sed "s#$CLONE#<clone>#g" > "$OUT/run.txt"
# The rewrite must leave the committed manifest byte-identical.
test -z "$(git -C "$CLONE" status --porcelain)"
cp "$CLONE/artifacts/conformance/evidence.json" "$WORK/evidence.first.json"
# 3. A third run, to show the evidence is byte-deterministic.
(cd "$CLONE" && node scripts/conformance.mjs --no-build) > /dev/null 2>&1
cmp "$WORK/evidence.first.json" "$CLONE/artifacts/conformance/evidence.json"

cp "$CLONE/docs/conformance/kernel-conformance.json" "$OUT/kernel-conformance.json"
cp "$CLONE/docs/conformance/kernel-conformance.md" "$OUT/kernel-conformance.md"
gzip -n -c "$CLONE/artifacts/conformance/evidence.json" > "$OUT/evidence.json.gz"
python3 "$HERE/scripts/conformance_k2/compare_k1_k2.py" \
  "$HERE/evidence/kernel_conformance.source.json" "$OUT/kernel-conformance.json" > "$OUT/comparison.json"
(cd "$OUT" && shasum -a 256 kernel-conformance.json kernel-conformance.md evidence.json.gz comparison.json \
  environment.txt check-strict.txt run.txt > SHA256SUMS)
echo "done: $OUT"
