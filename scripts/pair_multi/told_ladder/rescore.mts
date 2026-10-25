// Gold facts per responder reply, with SharedEval's own matcher (the ladder's rescore_s4.ts, with
// paths as arguments). Usage: tsx rescore.mts <in.json> <out.json> <path to SharedEval evaluator.ts>
import { readFileSync, writeFileSync } from 'node:fs';

const [inPath, outPath, evaluatorPath] = process.argv.slice(2);
const { containsPactPairFactV1 } = await import(evaluatorPath!);
type Step = { who: string; text: string };
type Item = { key: unknown[]; gold: string[]; policy: string; steps: Step[]; decision: string; leaked: boolean };
const items: Item[] = JSON.parse(readFileSync(inPath!, 'utf8'));
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
writeFileSync(outPath!, JSON.stringify(out));
console.log('rescored', out.length);
