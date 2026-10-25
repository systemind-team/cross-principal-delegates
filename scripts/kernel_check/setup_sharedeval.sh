#!/usr/bin/env bash
# Kernel check: SharedEval checkouts for each arm, on the experiment VM.
#
# One private clone ($KC/se/base, a --local clone of repos/SharedEval-a1; nothing in that repository is
# written) and one worktree per (evaluator, kernel):
#   e3-k2   8081e7e unchanged                      PAIR II control  (the ladder grid's evaluator)
#   e3-k1   8081e7e + pin patch to K1              PAIR II treatment
#   e3-v1p  8081e7e + pin patch to v1.0.0-preview  optional third arm
#   e1-k2   58829fe unchanged                      PAIR I control   (the ds41 cells' evaluator)
#   e1-k1   58829fe + pin patch to K1              PAIR I treatment
#   e1-v1p  58829fe + pin patch to v1.0.0-preview  optional third arm
#
# The pin patch changes only the declared SharedOS revision and runtime digest: the two constants in
# src/execution/sharedos/v1/load-sharedos.ts, the same two values asserted by
# tests/execution/sharedos-loader.test.ts, and the image pin in scripts/experiments/build-image.sh.
# The patch is committed (the runner refuses a dirty checkout) and exported to $KC/patches.
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
SRC=<vm>/repos/SharedEval-a1
BASE=$KC/se/base
K2_REV=3aa07e33999b656a10ace294fd4e41df8cbc318e
K2_DIGEST=4afb23d79851a83a48e25e968f04e45cefc81847b4a9963c62277b5c05862d5d
declare -A KREV=([K1]=c74461c1c4b715fd60c18401100cd72362d3afc1 [V1P]=526e77154216068a51d5ce96da0e595eac6e0678)
declare -A KDIG=([K1]=d28f0109cfb20cd679c7ae058ef367b3da946f5dea8a2a6182895301331cc9b9
                 [V1P]=005a22669b0cdac764cea7e8c17e8b9906b56bfa2f4623ff6d86fc0b0058f122)
declare -A EREV=([e3]=8081e7e78e0e5acfe79830c606619faae53c3b0a [e1]=58829feb17289e4e3092dae44089831a51336c4a)
mkdir -p "$KC/se" "$KC/patches"
[ -d "$BASE/.git" ] || git clone --quiet --no-checkout --local "$SRC" "$BASE"
git -C "$BASE" config user.name "kernel-check"
git -C "$BASE" config user.email "kernel-check@invalid"

make_arm() {  # $1 = e3|e1, $2 = K2|K1|V1P
  local ev=$1 k=$2 name wt
  name="$ev-$(echo "$k" | tr 'A-Z' 'a-z')"
  wt=$KC/se/$name
  if [ ! -d "$wt" ]; then
    git -C "$BASE" branch -f "kc/$name" "${EREV[$ev]}"
    git -C "$BASE" worktree add --quiet "$wt" "kc/$name"
    if [ "$k" != K2 ]; then
      (
        cd "$wt"
        sed -i "s/$K2_REV/${KREV[$k]}/" src/execution/sharedos/v1/load-sharedos.ts \
          tests/execution/sharedos-loader.test.ts scripts/experiments/build-image.sh
        sed -i "s/$K2_DIGEST/${KDIG[$k]}/" src/execution/sharedos/v1/load-sharedos.ts \
          tests/execution/sharedos-loader.test.ts
        git add src/execution/sharedos/v1/load-sharedos.ts tests/execution/sharedos-loader.test.ts \
          scripts/experiments/build-image.sh
        git commit --quiet -m "kernel check: pin SharedOS $k (${KREV[$k]})" \
          -m "Runtime pin and digest switched from K2 (3aa07e3, 4afb23d7...) to $k; nothing else changes."
        git format-patch --quiet -1 --stdout > "$KC/patches/$name-pin.patch"
      )
    fi
  fi
  ( cd "$wt" && [ -d node_modules ] || npm ci --no-audit --no-fund --loglevel=error )
  printf '%s %s %s clean=%s\n' "$name" "$(git -C "$wt" rev-parse --short HEAD)" \
    "$(grep -A1 'SHAREDOS_VERIFIED_REVISION_V1 =' "$wt/src/execution/sharedos/v1/load-sharedos.ts" | tail -1 | tr -d " ';" )" \
    "$([ -z "$(git -C "$wt" status --porcelain --untracked-files=no)" ] && echo yes || echo no)"
}

for arm in "${@:-e3:K2 e3:K1 e1:K2 e1:K1}"; do
  for a in $arm; do make_arm "${a%%:*}" "${a##*:}"; done
done
