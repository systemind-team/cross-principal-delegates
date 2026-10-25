#!/usr/bin/env bash
# Kernel check: build the SharedOS kernels on the experiment VM.
#
#   K2       3aa07e33999b656a10ace294fd4e41df8cbc318e  every PAIR experiment loaded it (control).
#            Rebuilt fresh here so the build procedure itself is checked: the fresh K2 build must
#            reproduce the runtime digest SharedEval pins (4afb23d7...), or the procedure is wrong
#            and no K1 digest from it can be trusted.
#   K1       c74461c1c4b715fd60c18401100cd72362d3afc1  the kernel of the conformance tables (treatment).
#   V1P      526e77154216068a51d5ce96da0e595eac6e0678  v1.0.0-preview (optional third arm).
#
# Each kernel is a fresh clone of the VM's SharedOS clone at the exact commit, installed from its own
# lockfile (pnpm 9.15.0 through corepack, --frozen-lockfile) and built with the repository's own
# `pnpm build`. Nothing outside $KC is written. Usage: build_kernels.sh [K2|K1|V1P ...]
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
SRC=<vm>/repos/SharedOS
UPSTREAM=https://github.com/systemind-team/SharedOS.git
declare -A REV=(
  [K2]=3aa07e33999b656a10ace294fd4e41df8cbc318e
  [K1]=c74461c1c4b715fd60c18401100cd72362d3afc1
  [V1P]=526e77154216068a51d5ce96da0e595eac6e0678
)
mkdir -p "$KC/kernels" "$KC/logs"
[ $# -gt 0 ] || set -- K2 K1
for name in "$@"; do
  rev=${REV[$name]:?unknown kernel $name}
  d=$KC/kernels/$name
  log=$KC/logs/build-$name.log
  {
    echo "== $name $rev $(date -u +%FT%TZ)"
    if [ ! -d "$d/.git" ]; then git clone --quiet --no-checkout --local "$SRC" "$d"; fi
    if ! git -C "$d" cat-file -e "$rev^{commit}" 2>/dev/null; then
      git -C "$d" fetch --quiet "$UPSTREAM" "$rev" || git -C "$d" fetch --quiet "$UPSTREAM" '+refs/tags/*:refs/tags/*'
    fi
    git -C "$d" checkout --quiet --detach "$rev"
    test "$(git -C "$d" rev-parse HEAD)" = "$rev"
    test -z "$(git -C "$d" status --porcelain --untracked-files=no)"
    cd "$d"
    corepack pnpm install --frozen-lockfile
    nice -n 10 corepack pnpm build
    test -z "$(git -C "$d" status --porcelain --untracked-files=no)"
    for p in contracts core os runtime; do test -f "packages/$p/dist/index.js"; done
    echo "== $name built $(date -u +%FT%TZ)"
  } > "$log" 2>&1 && echo "$name OK" || { echo "$name FAILED (see $log)"; tail -20 "$log"; }
done
