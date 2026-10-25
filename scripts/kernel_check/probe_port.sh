#!/usr/bin/env bash
# Kernel check: SCOPING PROBE ONLY. Never used for a measured run.
#
# Builds branch kc/e3-k1-probe = kc/e3-k1 (8081e7e + K1 pin) plus the smallest edits that let a scripted
# (no-model) session finish on K1, one commit per step, so each step's effect can be read on its own:
#   step 1  audit schemas accept K1's new audit fields: `id` (on every K1 record), `requestedAuthority`, and
#           the new event type `turn.ended`. Files: src/runner/v1/sharedos-session-store.ts (the durable
#           audit sink) and src/runner/v1/file-workflow-artifacts.ts (the retained-evidence schema).
#   step 2  NOT A PORT: the evidence projector's tool-catalog check is switched off when a
#           `tool.catalog.listed` record has no `visibleTools` (K1 records `catalogHash` and `withheldCount`
#           instead). The stub admits every tool, so it removes a check instead of porting it.
# A real port of step 2 has to re-base the catalog check on another source of the visible tool names (for
# example the definitions the turn driver is handed, verified against K1's `catalogHash`); see
# <internal>
# Usage: probe_port.sh  (prints the branch head and the diff stat)
set -euo pipefail
export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
KC=<vm>/kernel-check
BASE=$KC/se/base
WT=$KC/se/e3-k1-probe
git -C "$BASE" rev-parse --verify --quiet kc/e3-k1 >/dev/null || { echo "run setup_sharedeval.sh first"; exit 2; }
if [ -d "$WT" ]; then git -C "$BASE" worktree remove --force "$WT"; fi
git -C "$BASE" branch -f kc/e3-k1-probe kc/e3-k1
git -C "$BASE" worktree add --quiet "$WT" kc/e3-k1-probe
cd "$WT"
npm ci --no-audit --no-fund --loglevel=error >/dev/null

python3 - <<'PY'
for p in ['src/runner/v1/sharedos-session-store.ts', 'src/runner/v1/file-workflow-artifacts.ts']:
    s = open(p).read()
    old_enum = "    'message.sent',\n  ]),"
    assert s.count(old_enum) == 1, p
    s = s.replace(old_enum, "    'message.sent',\n    'turn.ended',\n  ]),")
    if p.endswith('sharedos-session-store.ts'):
        old = "const auditEventSchema: z.ZodType<SoAuditEvent> = z.object({\n  version: z.literal('1'),"
        new = old + "\n  id: identifierSchema.optional(),\n  requestedAuthority: jsonObjectSchema.optional(),"
    else:
        old = "const sharedOsAuditEventSchema = z.object({\n  version: z.literal('1'),"
        new = old + "\n  id: opaqueIdSchema.optional(),\n  requestedAuthority: strictJsonObjectInputSchema.optional(),"
    assert s.count(old) == 1, p
    open(p, 'w').write(s.replace(old, new))
PY
git add src/runner/v1/sharedos-session-store.ts src/runner/v1/file-workflow-artifacts.ts
git commit --quiet -m "PROBE ONLY step 1: accept K1 audit id, requestedAuthority, turn.ended"

python3 - <<'PY'
p = 'src/runner/v1/file-workflow-sharedos-evidence.ts'
s = open(p).read()
old = """function parseVisibleTools(event: NativeAuditEvent): ReadonlySet<string> {
  const visible = event.metadata?.['visibleTools'];"""
new = """function parseVisibleTools(event: NativeAuditEvent): ReadonlySet<string> {
  // PROBE ONLY (kernel-check scoping): K1 records catalogHash, not visibleTools. This admits every tool.
  if (event.metadata?.['visibleTools'] === undefined) {
    return new (class extends Set<string> { override has(_tool: string) { return true; } })();
  }
  const visible = event.metadata?.['visibleTools'];"""
assert s.count(old) == 1
open(p, 'w').write(s.replace(old, new))
PY
git add src/runner/v1/file-workflow-sharedos-evidence.ts
git commit --quiet -m "PROBE ONLY step 2: switch off the tool-catalog check when visibleTools is absent"
git log --oneline -4
git diff --stat kc/e3-k1 HEAD
git format-patch --quiet kc/e3-k1..HEAD -o "$KC/patches/probe"
