// Locate every PAIR I gold fact wherever it occurs in the workspace, not only in its declared
// source, so the mechanism baseline can bound readability under requester-derived grants by occurrence.
//
// node locate_facts.mjs <evaluator.ts> <questions.json> <alex_data_store.json> > fact_locations.json
//
// For every question and every gold fact, it records the resources (note or to-do, by surface and title) whose
// text contains the fact, under two locators:
// matcher SharedEval's containsPactPairFactV1 (evaluator.ts at 8081e7e, sha c51f2dbf...), the function that
// decides a leak, over each note's title+content and each to-do's title+description;
// verbatim the fact, lower-cased and whitespace-collapsed, of at least 8 characters after collapsing, as a
// substring of the resource's lower-cased whitespace-collapsed text.
// It also marks each fact's declared-source resources (source_notes / source_todos), so compute.py can form the
// declared-source, matcher-anywhere and verbatim-anywhere bounds from one frozen file. No model calls.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [evaluatorPath, questionsPath, storePath] = process.argv.slice(2);
const SHA = {
  evaluator: 'c51f2dbf348300e4a5c7c89dfd17be4651251f1d1a7247f96627c9fbd6d573a5',
  questions: '9032f46a79b2c9d6f6664b8aabea4006561b287de66bb59b0304cf619fdb265a',
  store: 'f67467c13e4dde3ff0a3ad38b2bc98e7a777fc771034fe53ab88105433297617',
};
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');
if (sha(evaluatorPath) !== SHA.evaluator) throw new Error('evaluator.ts is not the 8081e7e file');
if (sha(questionsPath) !== SHA.questions) throw new Error('questions.json is not the frozen task set');
if (sha(storePath) !== SHA.store) throw new Error('alex_data_store.json is not the frozen store');
const { containsPactPairFactV1 } = await import(pathToFileURL(evaluatorPath).href);

const Q = JSON.parse(readFileSync(questionsPath, 'utf8'));
const DS = JSON.parse(readFileSync(storePath, 'utf8'));
const collapse = (s) => (s ?? '').toLowerCase().replace(/\s+/g, ' ').trim();

// every resource: (surface, title) -> text (title + body) and its collapsed form
const resources = [];
for (const n of DS.notes) resources.push({ surface: 'note', title: n.title, text: `${n.title}\n${n.content}` });
for (const t of DS.todos) resources.push({ surface: 'todo', title: t.title, text: `${t.title}\n${t.description}` });
for (const r of resources) r.collapsed = collapse(r.text);

const verbatimHit = (fact, r) => {
  const f = collapse(fact);
  return f.length >= 8 && r.collapsed.includes(f);
};

const out = { inputs: SHA, questions: {} };
for (const q of Q.questions) {
  const qid = `PAIR-Q${q.id}`;
  const declared = new Set();
  for (const title of q.source_notes ?? []) declared.add(`note\u0000${title}`);
  for (const title of q.source_todos ?? []) declared.add(`todo\u0000${title}`);
  const facts = (q.gold_key_facts ?? []).map((fact) => {
    const matcher = [];
    const verbatim = [];
    for (const r of resources) {
      const key = `${r.surface}\u0000${r.title}`;
      if (containsPactPairFactV1(r.text, fact)) matcher.push(key);
      if (verbatimHit(fact, r)) verbatim.push(key);
    }
    return { fact, len_collapsed: collapse(fact).length, matcher, verbatim };
  });
  out.questions[qid] = {
    declared: [...declared],
    facts,
  };
}
process.stdout.write(`${JSON.stringify(out)}\n`);
