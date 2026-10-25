// Total leak: run the runtime matcher over every PAIR I question reply.
//
//   xz -dc evidence/v3.14/single-grid-tasks/tasks.jsonl.xz | node scripts/p11/match_pair1.mjs > matches.jsonl
//
// For each question row of the 110 cells: which gold facts appear in the responder's reply, and which
// already appear in the conversation context the responder was given (the policy text it read plus the
// request text), the echo rule of the ladder's rescore (rescore_s4.ts / rescore_classify_s4.py).
// Output: one line per question row: {cell, task, f: number of gold facts, r: indices in reply, c: indices in context}.
import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { containsPactPairFactV1 } from './matcher.mjs';

const ROOT = new URL('../../', import.meta.url).pathname;
const questions = JSON.parse(readFileSync(`${ROOT}evidence/v3.14/pair-dataset/questions.json`, 'utf8')).questions;
const gold = new Map(questions.map(q => [`PAIR-Q${q.id}`, q.gold_key_facts]));
const policyCache = new Map();
function policyText(policy, requester) {
  const key = `${policy}_${requester}`;
  if (!policyCache.has(key)) {
    policyCache.set(key, readFileSync(`${ROOT}evidence/v3.14/pair-dataset/policies/PAIR-I_${key}.md`, 'utf8'));
  }
  return policyCache.get(key);
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  const row = JSON.parse(line);
  if (row.kind !== 'qa') continue;
  const facts = gold.get(row.taskId);
  if (!facts) throw new Error(`no gold facts for ${row.taskId}`);
  const reply = typeof row.replyText === 'string' ? row.replyText : null;
  const ctx = `${policyText(row.policy, row.requester)}\n${row.requestText ?? ''}`;
  const r = [];
  const c = [];
  facts.forEach((fact, i) => {
    if (reply !== null && containsPactPairFactV1(reply, fact)) r.push(i);
    if (containsPactPairFactV1(ctx, fact)) c.push(i);
  });
  process.stdout.write(`${JSON.stringify({ cell: row.cell, task: row.taskId, f: facts.length, r, c, text: reply !== null })}\n`);
}
