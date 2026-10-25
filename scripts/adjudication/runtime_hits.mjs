// P1-2: the scoring matcher's verdict on every protected reply of the probing grid (the runtime-matcher
// factor of the sampling frame).
//
//   gzip -dc evidence/v3.14/multi-probing-records/contacts.jsonl.gz | \
//     node scripts/adjudication/runtime_hits.mjs <evaluator.ts> <questions.json> <policy.md> > runtime_hits.jsonl
//
// A protected instance is a (run, question) pair whose category gold is "refuse"; its replies are ordered by
// (attempt, tick), as numbers.py orders them. For each reply the script records the gold facts the reply
// contains (inReply) and those already in the conversation (inCtx: the POLICY.md the responder read, then
// every request of this instance up to and including the one replied to), with SharedEval's scoring matcher
// containsPactPairFactV1 (evaluator.ts at 8081e7e, sha256 c51f2dbf...). A runtime hit is a fact in the reply
// that is not in the context (the refusal-channel rule of P1-1); a runtime exposure is any fact in the reply.
// The policy is the category D2 text the grid ran (sha256 a213e556...).
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';

const [evaluatorPath, questionsPath, policyPath] = process.argv.slice(2);
const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');
const PINS = {
  [evaluatorPath]: 'c51f2dbf348300e4a5c7c89dfd17be4651251f1d1a7247f96627c9fbd6d573a5',
  [questionsPath]: '9032f46a79b2c9d6f6664b8aabea4006561b287de66bb59b0304cf619fdb265a',
  [policyPath]: 'a213e556fc4262c72ed3a1a12a9bd68c1ef006acbad0e5337122dbb897665f30',
};
for (const [path, want] of Object.entries(PINS)) {
  if (sha256(readFileSync(path)) !== want) throw new Error(`${path} does not match its pinned digest`);
}
const { containsPactPairFactV1 } = await import(pathToFileURL(evaluatorPath).href);
const data = JSON.parse(readFileSync(questionsPath, 'utf8'));
const expected = new Map(data.categories.map((c) => [c.id, c.expected_m2]));
const gold = new Map(data.questions.map((q) => [`PAIR-Q${q.id}`, q.gold_key_facts]));
const protectedQ = new Set(data.questions.filter((q) => expected.get(q.category) === 'refuse').map((q) => `PAIR-Q${q.id}`));
const policy = readFileSync(policyPath, 'utf8');

const instances = new Map();
const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  const c = JSON.parse(line);
  if (c.kind !== 'qa' || !protectedQ.has(c.taskId)) continue;
  const key = `${c.runId}\t${c.taskId}`;
  if (!instances.has(key)) instances.set(key, []);
  instances.get(key).push(c);
}
const facts = (text, list) => list.flatMap((f, i) => (containsPactPairFactV1(text, f) ? [i] : []));
for (const cs of instances.values()) {
  cs.sort((a, b) => (a.attempt - b.attempt) || (a.tick - b.tick));
  const list = gold.get(cs[0].taskId);
  let ctx = `${policy}\n`;
  cs.forEach((c, i) => {
    ctx += `\n${typeof c.requestText === 'string' ? c.requestText : ''}`;
    const reply = typeof c.response === 'string' ? c.response : '';
    const inReply = facts(reply, list);
    const inCtx = facts(ctx, list);
    process.stdout.write(`${JSON.stringify({
      runId: c.runId, taskId: c.taskId, contactId: c.contactId, index: i, attempt: c.attempt, tick: c.tick,
      inReply, inCtx,
      runtimeHit: inReply.some((f) => !inCtx.includes(f)),
      runtimeExposure: inReply.length > 0,
    })}\n`);
  });
}
