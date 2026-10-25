// P1-6, which gold facts does each impersonation prefix already contain?
//
// The total-leak rule drops a gold fact that is already in the conversation (the policy text plus the
// requester's messages). The prefix now sits in every requester message, so a fact the prefix contains
// would count as an echo in the arms that carry that prefix and as a leak elsewhere. This script runs
// SharedEval's own matcher, containsPactPairFactV1, with each prefix as the text and every gold fact of the
// ladder's 100 questions as the fact, and lists the flagged questions. The primary analysis excludes every
// flagged question from all arms; a sensitivity analysis keeps them.
//
// It also reports, for context, the facts the two responder policy texts contain (the header D2R_ID_R0 and
// D2R_PRINCIPLES): those are identical within each primary comparison, which pairs arms with the same policy.
//
// Usage: node prefix_overlap.mjs <SharedEval evaluator.ts> <questions.json> <ladder MANIFEST.json>
//                                <prefix dir> <D2R_ID_R0.md> <D2R_PRINCIPLES.md>  > prefix_overlap.json
// evaluator.ts must be SharedEval's src/suites/pact-pair/evaluator.ts at 8081e7e (sha256 c51f2dbf...),
// identical at 26dd392; Node runs it with built-in type stripping.
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const [evaluatorPath, questionsPath, manifestPath, prefixDir, headerPolicyPath, principlesPath] = process.argv.slice(2);
const EVALUATOR_SHA256 = 'c51f2dbf348300e4a5c7c89dfd17be4651251f1d1a7247f96627c9fbd6d573a5';
const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');
if (sha256(readFileSync(evaluatorPath)) !== EVALUATOR_SHA256) {
  throw new Error('evaluator.ts is not the SharedEval 8081e7e file');
}
const { containsPactPairFactV1 } = await import(pathToFileURL(evaluatorPath).href);

const questions = JSON.parse(readFileSync(questionsPath, 'utf8')).questions;
const byId = new Map(questions.map((q) => [`PAIR-Q${q.id}`, q]));
const groups = JSON.parse(readFileSync(manifestPath, 'utf8')).groups;
const taskIds = Object.values(groups).flat().filter((t) => t.startsWith('PAIR-Q'));
if (taskIds.length !== 100) throw new Error(`expected 100 questions, found ${taskIds.length}`);

const texts = {};
for (const name of readdirSync(prefixDir).filter((f) => f.endsWith('.txt')).sort()) {
  texts[`prefix:${name.replace(/\.txt$/, '')}`] = readFileSync(join(prefixDir, name), 'utf8');
}
texts['policy:D2R_ID_R0'] = readFileSync(headerPolicyPath, 'utf8');
texts['policy:D2R_PRINCIPLES'] = readFileSync(principlesPath, 'utf8');

const report = { evaluatorSha256: EVALUATOR_SHA256, questionsSha256: sha256(readFileSync(questionsPath)),
  texts: Object.fromEntries(Object.entries(texts).map(([k, v]) => [k, { bytes: Buffer.byteLength(v), sha256: sha256(Buffer.from(v)) }])),
  flagged: {} };
for (const [name, text] of Object.entries(texts)) {
  const hits = [];
  for (const id of taskIds) {
    const q = byId.get(id);
    const facts = q.gold_key_facts.filter((f) => containsPactPairFactV1(text, f));
    if (facts.length) hits.push({ taskId: id, category: q.category, question: q.question, factsMatched: facts });
  }
  report.flagged[name] = hits;
}
const prefixFlagged = [...new Set(Object.entries(report.flagged)
  .filter(([k]) => k.startsWith('prefix:')).flatMap(([, v]) => v.map((h) => h.taskId)))].sort();
report.excludedFromPrimary = prefixFlagged;
console.log(JSON.stringify(report, null, 1));
