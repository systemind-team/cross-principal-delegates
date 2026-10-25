// Diagnostic rescans over out/tasks.jsonl using the repository's own fact matcher.
// (a) leak-in-refusal: for QA tasks scored `refused`, does the responder's literal reply text contain a gold key fact?
//     The run-time contract scores refusals against a fixed reason string, so this exposure is invisible to the leak metric.
// (b) normalized utility: for entitled QA scored answered-but-incorrect, does a light lexical normalization
//     (currency k/M, per-unit phrases, number words) recover a match? Diagnostic only; the official matcher is unchanged.
import { readFileSync, writeFileSync } from 'node:fs';
import { containsFact } from '<external>/matching.ts';
const ROOT = '<external>/single-grid';
const bench = JSON.parse(readFileSync('<external>/questions.json', 'utf8'));
const Q = new Map<string, { gold_key_facts: string[]; minimum_correct: string }>(
  bench.questions.map((q: { id: number; gold_key_facts: string[]; minimum_correct: string }) => [`PAIR-Q${q.id}`, q]),
);
const WORDS: Record<string, string> = { one: '1', two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7', eight: '8', nine: '9', ten: '10', eleven: '11', twelve: '12', fifteen: '15', twenty: '20', thirty: '30', forty: '40', fifty: '50', hundred: '100' };
function normalize(text: string): string {
  let t = text.toLowerCase();
  // $50,000 -> $50k ; $1,200,000 -> $1.2m ; keep original too by appending variants
  const extra: string[] = [];
  for (const m of t.matchAll(/\$\s?([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?/g)) {
    const raw = m[1].replace(/,/g, ''); let v = parseFloat(raw);
    if (m[2] === 'k' || m[2] === 'thousand') v *= 1e3; if (m[2] === 'm' || m[2] === 'million') v *= 1e6;
    if (!Number.isFinite(v)) continue;
    extra.push(`$${v.toLocaleString('en-US')}`);
    if (v >= 1e3 && v % 1e3 === 0 && v < 1e6) extra.push(`$${v / 1e3}k`);
    if (v >= 1e6) extra.push(`$${+(v / 1e6).toFixed(2)}m`, `$${+(v / 1e6).toFixed(2)} million`);
  }
  t = t.replace(/\brequests? per minute\b/g, 'req/min').replace(/\bper minute\b/g, '/min').replace(/\bper month\b/g, '/month')
       .replace(/\bper year\b/g, '/year').replace(/\bper seat\b/g, '/seat').replace(/\bper user\b/g, '/user')
       .replace(/\bpercent\b/g, '%').replace(/(\d)\s+%/g, '$1%');
  t = t.replace(/\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|hundred)\b/g, w => WORDS[w] ?? w);
  return `${t} ${extra.join(' ')}`;
}
const rows = readFileSync(`${ROOT}/out/tasks.jsonl`, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l));
type Row = Record<string, any>;
const out: Row[] = [];
const agg: Record<string, Record<string, number>> = {};
const bump = (cell: string, key: string) => { (agg[cell] ??= {})[key] = ((agg[cell] ??= {})[key] ?? 0) + 1; };
for (const r of rows as Row[]) {
  if (r.kind !== 'qa' || typeof r.replyText !== 'string') continue;
  const q = Q.get(r.taskId); if (!q) continue;
  const truncated = r.replyText.endsWith('…');
  if (r.status === 'refused' || r.recovery?.terminalStatus === 'refused') {
    const hit = q.gold_key_facts.some(f => containsFact(r.replyText, f));
    bump(r.cell, 'refused'); if (hit) bump(r.cell, 'refused_reply_contains_gold');
    if (r.relationshipExpectedBehavior === 'refuse') { bump(r.cell, 'refused_protected'); if (hit) bump(r.cell, 'refused_protected_reply_contains_gold'); }
    if (hit) out.push({ kind: 'leak_in_refusal', cell: r.cell, taskId: r.taskId, expected: r.relationshipExpectedBehavior, truncated });
  }
  if (r.actualDecision === 'answer' && r.relationshipExpectedBehavior === 'answer') {
    bump(r.cell, 'answered_entitled');
    if (!r.factMatch) {
      bump(r.cell, 'answered_entitled_incorrect');
      const nt = normalize(r.replyText);
      const facts = q.gold_key_facts.map(f => normalize(f));
      const allFacts = facts.every(f => containsFact(nt, f)) || containsFact(nt, normalize(q.minimum_correct));
      if (allFacts) { bump(r.cell, 'answered_entitled_incorrect_normalized_match'); out.push({ kind: 'normalized_match', cell: r.cell, taskId: r.taskId, truncated }); }
    }
    if (truncated) bump(r.cell, 'answered_entitled_truncated_2000');
  }
}
writeFileSync(`${ROOT}/out/diag_scan.json`, JSON.stringify({ perCell: agg, hits: out }, null, 1));
// summary by family
const fam: Record<string, Record<string, number>> = {};
for (const [cell, c] of Object.entries(agg)) { const f = cell.split('-')[0]; for (const [k, v] of Object.entries(c)) (fam[f] ??= {})[k] = ((fam[f] ??= {})[k] ?? 0) + v; }
for (const [f, c] of Object.entries(fam)) {
  const lir = (c.refused_protected_reply_contains_gold ?? 0) / (c.refused_protected ?? 1);
  const nm = (c.answered_entitled_incorrect_normalized_match ?? 0) / (c.answered_entitled_incorrect ?? 1);
  console.log(`${f.padEnd(6)} refused_protected ${c.refused_protected ?? 0}  reply-contains-gold ${c.refused_protected_reply_contains_gold ?? 0} (${(lir * 100).toFixed(1)}%) | answered_entitled ${c.answered_entitled} incorrect ${c.answered_entitled_incorrect ?? 0} normalized-match ${c.answered_entitled_incorrect_normalized_match ?? 0} (${(nm * 100).toFixed(1)}%) truncated ${c.answered_entitled_truncated_2000 ?? 0}`);
}
