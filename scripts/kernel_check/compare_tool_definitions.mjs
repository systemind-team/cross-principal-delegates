#!/usr/bin/env node
// Kernel check: are the kernel-supplied tool definitions a model is shown the same in K2 and K1?
// SharedEval offers the model the kernel's own definitions for the file tools (os.createFileTools over a files
// provider) and for messages.request (core.MESSAGE_REQUEST_TOOL_DEFINITION); PACT task tools are SharedEval's.
// Prints, per tool, whether the K1 definition equals K2's byte for byte (JSON with sorted keys), and the fields
// that differ. Usage: node compare_tool_definitions.mjs <K2 build> <K1 build>
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [k2dir, k1dir] = process.argv.slice(2).map(p => resolve(p));
async function defs(dir) {
  const core = await import(pathToFileURL(join(dir, 'packages/core/dist/index.js')).href);
  const os = await import(pathToFileURL(join(dir, 'packages/os/dist/index.js')).href);
  const provider = { namespace: 'files', invoke: async () => { throw new Error('not invoked'); } };
  const out = { 'messages.request': core.MESSAGE_REQUEST_TOOL_DEFINITION };
  for (const h of os.createFileTools(provider)) out[h.definition.name] = h.definition;
  return out;
}
const sortKeys = v => Array.isArray(v) ? v.map(sortKeys)
  : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort().map(k => [k, sortKeys(v[k])])) : v;
const a = await defs(k2dir);
const b = await defs(k1dir);
const rows = [];
for (const name of [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()) {
  const x = a[name] && JSON.stringify(sortKeys(a[name]));
  const y = b[name] && JSON.stringify(sortKeys(b[name]));
  const fields = x && y && x !== y
    ? [...new Set([...Object.keys(a[name]), ...Object.keys(b[name])])]
      .filter(k => JSON.stringify(sortKeys(a[name][k])) !== JSON.stringify(sortKeys(b[name][k])))
    : [];
  rows.push({ tool: name, in_k2: Boolean(x), in_k1: Boolean(y), identical: x === y, differing_fields: fields });
}
console.log(JSON.stringify(rows));
