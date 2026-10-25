#!/usr/bin/env node
// Kernel check, option B: replay the kernel's recorded authorization decisions through K2 and K1.
//
// For every `authorization.checked` record a K2 run persisted (SharedEval's durable audit sink,
// <run>/.sharedeval-sharedos-session/audit/record-*.json, in sequence order), the same question is asked again,
// once of a K2 kernel and once of a K1 kernel, through the public `SharedOSKernel.authorize(context, request)`:
//   context  = the record's namespaceId, actor, authority, owner, purpose, traceId, and `now` = the record's `at`
//              (enabledToolNamespaces does not gate the resource plane; ["files"] fills the field);
//   request  = the record's resource (with owner) and action;
//   grants   = the run's immutable grant manifest (grants.json) filtered as SharedEval's store filters it
//              (namespace, subject = actor, issuer = authority; a grant listed in one of the binding's
//              responderGrantSets is deferred and loads only in a trace whose responder binding lists it);
//   usage    = for each grant, the number of earlier records in the same run that were allowed, consumed
//              (metadata.consumed) and matched that grant. At the end of a run these counts must equal the
//              run's own usage records per grant, or the run is reported as a calibration failure.
// `authorize` never consumes, so the replay writes nothing. Compared per record: allowed, the matched grant
// (allowed) or the reason code (denied). K2's replay must reproduce the recorded decision; K1 is then compared
// with the record and with K2's replay.
//
// Usage: node replay_decisions.mjs --k2 <K2 build> --k1 <K1 build> [--mutate-k1 drop-matched|exhaust] <run-multi-dir> [...]
//        (JSON lines on stdout)
// --mutate-k1 is a sensitivity check of this tool, never a result: it breaks K1's inputs on purpose (drop-matched
// removes, for each question, the grant the record matched from what K1 sees; exhaust reports every grant to K1 as
// used up to its maxUses), so a working comparison must report disagreements. Without it the output is v2's.
// Each output line also names the core package version each kernel loaded.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const opt = { runs: [] };
for (let i = 0; i < argv.length; i += 1) {
  if (argv[i] === '--k2' || argv[i] === '--k1') { opt[argv[i].slice(2)] = resolve(argv[i + 1]); i += 1; }
  else if (argv[i] === '--mutate-k1') { opt.mutate = argv[i + 1]; i += 1; }
  else opt.runs.push(argv[i]);
}
if (opt.mutate !== undefined && !['drop-matched', 'exhaust'].includes(opt.mutate)) {
  console.error(`unknown --mutate-k1 ${opt.mutate}`);
  process.exit(2);
}
if (!opt.k2 || !opt.k1 || opt.runs.length === 0) {
  console.error('usage: replay_decisions.mjs --k2 <dir> --k1 <dir> <run-multi-dir> [...]');
  process.exit(2);
}
const core = {};
const coreVersion = {};
for (const name of ['k2', 'k1']) {
  core[name] = await import(pathToFileURL(join(opt[name], 'packages/core/dist/index.js')).href);
  coreVersion[name] = JSON.parse(readFileSync(join(opt[name], 'packages/core/package.json'), 'utf8')).version;
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eqAddr = (a, b) => a && b && a.kind === b.kind
  && (a.agentId ?? a.serviceId ?? a.userId ?? a.conversationId) === (b.agentId ?? b.serviceId ?? b.userId ?? b.conversationId);

function readRun(dir) {
  const s = join(dir, '.sharedeval-sharedos-session');
  const grants = JSON.parse(readFileSync(join(s, 'grants.json'), 'utf8')).grants;
  const binding = JSON.parse(readFileSync(join(s, 'binding.json'), 'utf8')).binding;
  const audit = readdirSync(join(s, 'audit')).filter(f => /^record-\d{12}\.json$/.test(f)).sort()
    .map(f => JSON.parse(readFileSync(join(s, 'audit', f), 'utf8')));
  audit.forEach((r, i) => { if (r.sequence !== i) throw new Error(`${dir}: audit sequence gap at ${i}`); });
  const usage = existsSync(join(s, 'usage'))
    ? readdirSync(join(s, 'usage')).filter(f => /^record-\d{12}\.json$/.test(f)).sort()
      .map(f => JSON.parse(readFileSync(join(s, 'usage', f), 'utf8')))
    : [];
  const responderBindings = existsSync(join(s, 'responder-bindings'))
    ? readdirSync(join(s, 'responder-bindings')).filter(f => /^contact-[0-9a-f]{64}\.json$/.test(f)).sort()
      .map(f => JSON.parse(readFileSync(join(s, 'responder-bindings', f), 'utf8')))
    : [];
  return { grants, binding, events: audit.map(r => r.event), usage, responderBindings };
}

function kernelFor(K, grants, usageCounts, deferred, traceGrants, mutation) {
  const grantSource = {
    load: async context => grants.filter(g => g.namespaceId === context.namespaceId
      && eqAddr(g.subject, context.actor) && eqAddr(g.issuer, context.authority)
      && (!deferred.has(g.id) || (traceGrants.get(context.traceId)?.has(g.id) ?? false))
      && !(mutation?.mode === 'drop-matched' && g.id === mutation.current))
      .map(g => structuredClone(g)),
  };
  const maxUses = new Map(grants.map(g => [g.id, g.constraints?.maxUses]));
  const usageStore = {
    getUsage: async (_namespaceId, grantId) => (mutation?.mode === 'exhaust' && maxUses.get(grantId) !== undefined
      ? maxUses.get(grantId) : usageCounts.get(grantId) ?? 0),
    tryConsume: async () => { throw new Error('the replay never consumes'); },
  };
  return new K.SharedOSKernel({ grantSource, authorizer: new K.CapabilityAuthorizer({ usageStore }) });
}

function verdict(d) {
  return d.allowed ? { allowed: true, grantId: d.matchedGrantId ?? null } : { allowed: false, reason: d.reasonCode };
}

for (const dir of opt.runs) {
  const out = { run: dir };
  try {
    const run = readRun(dir);
    const deferred = new Set((run.binding.responderGrantSets ?? []).flatMap(set => set.grantIds));
    const traceGrants = new Map();
    for (const b of run.responderBindings) {
      if (traceGrants.has(b.traceId)) throw new Error(`two responder bindings for trace ${b.traceId}`);
      traceGrants.set(b.traceId, new Set(b.grantIds));
    }
    const usageCounts = new Map();
    const mutation = opt.mutate === undefined ? undefined : { mode: opt.mutate, current: null };
    const kernels = {
      k2: kernelFor(core.k2, run.grants, usageCounts, deferred, traceGrants),
      k1: kernelFor(core.k1, run.grants, usageCounts, deferred, traceGrants, mutation),
    };
    const rows = [];
    for (const e of run.events) {
      if (e.type !== 'authorization.checked') continue;
      const context = {
        namespaceId: e.namespaceId, actor: e.actor, authority: e.authority, owner: e.owner, purpose: e.purpose,
        traceId: e.traceId, enabledToolNamespaces: ['files'], now: e.at,
      };
      const request = { resource: e.resource, action: e.action };
      const recorded = e.outcome === 'allowed'
        ? { allowed: true, grantId: e.grantId ?? null }
        : { allowed: false, reason: e.reason ?? null };
      if (mutation) mutation.current = e.grantId ?? null;
      const k2 = verdict(await kernels.k2.authorize(context, request));
      const k1 = verdict(await kernels.k1.authorize(context, request));
      rows.push({ actor: e.actor.agentId ?? e.actor.serviceId, resource: `${e.resource.namespace}:${e.resource.path.join('/')}`,
        action: e.action, recorded, k2, k1 });
      if (e.outcome === 'allowed' && e.metadata?.consumed === true && e.grantId) {
        usageCounts.set(e.grantId, (usageCounts.get(e.grantId) ?? 0) + 1);
      }
    }
    const usageFromRecords = new Map();
    for (const u of run.usage) usageFromRecords.set(u.grantId, (usageFromRecords.get(u.grantId) ?? 0) + 1);
    const calibrated = same([...usageCounts.entries()].sort(), [...usageFromRecords.entries()].sort());
    Object.assign(out, {
      ...(opt.mutate === undefined ? {} : { mutate_k1: opt.mutate }),
      core_versions: coreVersion,
      deferred_grants: deferred.size,
      responder_bindings: run.responderBindings.length,
      decisions: rows.length,
      recorded_allowed: rows.filter(r => r.recorded.allowed).length,
      recorded_denied: rows.filter(r => !r.recorded.allowed).length,
      denied_reasons: Object.fromEntries([...new Set(rows.filter(r => !r.recorded.allowed).map(r => r.recorded.reason))]
        .map(k => [k, rows.filter(r => !r.recorded.allowed && r.recorded.reason === k).length])),
      usage_calibrated: calibrated,
      k2_equals_recorded: rows.filter(r => same(r.k2, r.recorded)).length,
      k1_equals_recorded: rows.filter(r => same(r.k1, r.recorded)).length,
      k1_equals_k2: rows.filter(r => same(r.k1, r.k2)).length,
      differences: rows.filter(r => !same(r.k1, r.recorded) || !same(r.k2, r.recorded)),
    });
  } catch (error) {
    out.error = error instanceof Error ? error.message : String(error);
  }
  console.log(JSON.stringify(out));
}
