// Refusal-channel scan for the grok-4.6 supplement: part (a) of ../diag_scan.ts, with paths as arguments.
// For every QA task scored `refused` (directly or by recovery), does the responder's literal reply carry a gold
// key fact under the repository's own matcher? The run-time contract scores a refusal against a fixed reason
// string, so this is the half of total leak the leak metric cannot see.
//
//   SHAREDEVAL_DIR=<SharedEval checkout at 5aaa7f1> npx tsx refusal_scan.mts <out.json> <tasks.jsonl>...
//
// Output has diag_scan.json's shape (hits of kind leak_in_refusal, plus per-cell counts), so analyze.py reads
// the frozen scan and this one the same way. Over the frozen tasks.jsonl it reproduces diag_scan.json's
// leak_in_refusal hits exactly; analyze.py does not check that, the README records it.
import { readFileSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';

const repo = process.env.SHAREDEVAL_DIR;
if (!repo) throw new Error('set SHAREDEVAL_DIR to the SharedEval checkout');
const [outPath, ...inputs] = process.argv.slice(2);
if (!outPath || inputs.length === 0) throw new Error('usage: refusal_scan.mts <out.json> <tasks.jsonl>...');
const { containsFact } = await import(join(repo, 'src/suites/pact-pair/evaluation-tools/v1/matching.ts'));
const bench = JSON.parse(readFileSync(join(repo, 'dataset/pact-pair/tasks/questions.json'), 'utf8'));
const gold = new Map<string, string[]>(
  bench.questions.map((q: { id: number; gold_key_facts: string[] }) => [`PAIR-Q${q.id}`, q.gold_key_facts]),
);

type Row = Record<string, any>;
const hits: Row[] = [];
const perCell: Record<string, Record<string, number>> = {};
const bump = (cell: string, key: string) => {
  const c = (perCell[cell] ??= {});
  c[key] = (c[key] ?? 0) + 1;
};
for (const path of inputs) {
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    const r: Row = JSON.parse(line);
    // rescore detail files carry no cell field; their name is the cell label
    r.cell ??= basename(path).replace(/\.tasks\.jsonl$/, '');
    if (r.kind !== 'qa' || typeof r.replyText !== 'string') continue;
    if (!(r.status === 'refused' || r.recovery?.terminalStatus === 'refused')) continue;
    const facts = gold.get(r.taskId);
    if (!facts) throw new Error(`no gold facts for ${r.taskId}`);
    const hit = facts.some(f => containsFact(r.replyText, f));
    bump(r.cell, 'refused');
    if (hit) {
      bump(r.cell, 'refused_reply_contains_gold');
      hits.push({ kind: 'leak_in_refusal', cell: r.cell, taskId: r.taskId, expected: r.relationshipExpectedBehavior, truncated: r.replyText.endsWith('…') });
    }
  }
}
writeFileSync(outPath, JSON.stringify({ perCell, hits }, null, 1));
console.log(`${hits.length} refused replies carry a gold fact, over ${Object.keys(perCell).length} cells`);
