#!/usr/bin/env bash
# Kernel check: runtime digest of each built kernel, computed with SharedEval's own
# digestSharedOsRuntimeV1 (load-sharedos.ts at 8081e7e; the function is identical at 58829fe),
# plus the commit, tree, package versions and a clean-tree check. Prints one JSON object per kernel.
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
SE=${SE_CLONE:-<vm>/repos/SharedEval-a1}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git -C "$SE" show 8081e7e:src/execution/sharedos/v1/load-sharedos.ts > "$tmp/load-sharedos.ts"
cmp <(git -C "$SE" show 8081e7e:src/execution/sharedos/v1/load-sharedos.ts | sed -n '/^export function digestSharedOsRuntimeV1/,/^}/p') \
    <(git -C "$SE" show 58829fe:src/execution/sharedos/v1/load-sharedos.ts | sed -n '/^export function digestSharedOsRuntimeV1/,/^}/p') \
  || { echo "digest function differs between 8081e7e and 58829fe" >&2; exit 2; }
cat > "$tmp/run.mts" <<'EOF'
import { digestSharedOsRuntimeV1, verifySharedOsBuildV1 } from './load-sharedos.ts';
const [dir, rev] = process.argv.slice(2);
const digest = digestSharedOsRuntimeV1(dir);
const verification = verifySharedOsBuildV1(dir, { expectedRevision: rev, expectedRuntimeDigest: digest });
console.log(JSON.stringify({ digest, verification }));
EOF
for name in "${@:-K2 K1 V1P}"; do
  for k in $name; do
    d=$KC/kernels/$k
    rev=$(git -C "$d" rev-parse HEAD)
    out=$(cd "$tmp" && node run.mts "$d" "$rev")
    vers=$(cd "$d" && node -e 'const f=require("fs");console.log(JSON.stringify(Object.fromEntries(["contracts","core","os","runtime"].map(p=>[p,JSON.parse(f.readFileSync(`packages/${p}/package.json`)).version]))))')
    printf '{"kernel":"%s","commit":"%s","tree":"%s","describe":"%s","clean":%s,"versions":%s,"result":%s}\n' \
      "$k" "$rev" "$(git -C "$d" rev-parse 'HEAD^{tree}')" "$(git -C "$d" describe --tags --always HEAD 2>/dev/null || echo none)" \
      "$([ -z "$(git -C "$d" status --porcelain --untracked-files=no)" ] && echo true || echo false)" "$vers" "$out"
  done
done
