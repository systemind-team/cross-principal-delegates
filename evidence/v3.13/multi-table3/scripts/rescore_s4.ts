import { readFileSync, writeFileSync } from 'node:fs';
import { containsPactPairFactV1 } from '<vm>/repos/SharedEval-a1/src/suites/pact-pair/evaluator.ts';
type Step = { who: string; text: string };
type Item = { key: unknown[]; gold: string[]; policy: string; steps: Step[]; decision: string; leaked: boolean };
const items: Item[] = JSON.parse(readFileSync('/tmp/s4_rescore_in.json', 'utf8'));
const out = items.map(it => {
  let ctx = it.policy + '\n';
  const replies: { idx: number; inReply: string[]; inCtx: string[] }[] = [];
  it.steps.forEach((s, i) => {
    if (s.who === 'requester') { ctx += '\n' + s.text; return; }
    const inReply = it.gold.filter(f => containsPactPairFactV1(s.text, f));
    const inCtx = it.gold.filter(f => containsPactPairFactV1(ctx, f));
    replies.push({ idx: i, inReply, inCtx });
  });
  return { key: it.key, decision: it.decision, leaked: it.leaked, replies };
});
writeFileSync('/tmp/s4_rescore_out.json', JSON.stringify(out));
console.log('done', out.length);
