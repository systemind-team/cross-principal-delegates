/**
 * Freeze the exact NET judge input per judged reply.
 *
 * Read-only extraction. It runs on the experiment VM inside the SharedEval checkout the
 * NET rerun was judged with (d44e4788562c438a97180443ee8cc5170094ad07), and the script is
 * fed on stdin, so nothing is written on the VM except tsx's own scratch directory, which
 * TMPDIR puts under /tmp/netjudge-tmp and the same command deletes:
 *
 *   ssh <host> 'export PATH=<vm>/toolchain/node-v24.18.0-linux-x64/bin:$PATH
 *     cd <vm>/repos/SE-net-e1 && mkdir -p /tmp/netjudge-tmp
 *     { TMPDIR=/tmp/netjudge-tmp node_modules/.bin/tsx --no-cache -; echo "tsx-exit=$?" >&2; } | gzip -9
 *     rm -rf /tmp/netjudge-tmp' < extract_net_judge_inputs.ts > extraction.jsonl.gz
 *
 * What it does, per (responder lane, rung): it reads the lane directory the final judge
 * pass read (runs/net-or-judge/<lane>-<rung>/lane, symlinks to the responder runs), collects
 * the delivered replies with the repository's own reader, and rebuilds every judge prompt
 * twice with the repository's own code:
 *
 *   1. through judgePactNetObservedRepliesV1 itself -- the function `judge-runs --both-arms`
 *      calls -- with the repository's offline 'always-refused' fake backend, so the prompt
 *      hash comes out of the exact code path and no model is called;
 *   2. through pactNetJudgePromptScaffoldV1 / renderPactNetJudgePromptV1 with the same inputs,
 *      which is what exposes the pieces (Asked-by and Answered-by lines, shareable block,
 *      question, reply) that the frozen files carry.
 *
 * Both hashes are checked against each other and against the promptHash the judge recorded
 * in out/judgments.json and in its cache. The NET world data the proposition check needs
 * (each edge's forbidden.fact and the disclosure gold's protected proposition and
 * indicators) is emitted too. Output: one JSON object per line on stdout.
 *
 * No model, network or API call is made: no credential is loaded (no .env is sourced), and
 * the only backend constructed is the repository's constant fake.
 */
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, readlinkSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  PACT_NET_JUDGE_RUBRIC_V1,
  PACT_NET_JUDGE_SHAREABLE_CHARS_V1,
  PACT_NET_JUDGE_SHAREABLE_TOTAL_V1,
  pactNetJudgeCacheKeyV1,
  pactNetJudgePromptScaffoldV1,
  pactNetJudgeRubricHashV1,
  pactNetJudgeShareableBlockV1,
  renderPactNetJudgePromptV1,
  type PactNetJudgePromptInputV1,
} from './src/suites/pact-net/judge-tools/v1/rubric.ts';
import { sha256HexV1 } from './src/suites/pact-net/judge-tools/v1/contracts.ts';
import {
  fakePactNetJudgeBackendV1,
  pactNetJudgeShareableMaterialV1,
} from './src/suites/pact-net/judge-tools/v1/judge.ts';
import {
  judgePactNetObservedRepliesV1,
  pactNetRunRootsV1,
  readPactNetObservedRepliesV1,
} from './src/suites/pact-net/judge-tools/v1/observed.ts';
import {
  loadPactNetV2ProbesV1,
  readPactNetAgentIdentityV1,
  type PactNetV2ProbeV1,
} from './src/suites/pact-net/v2-probes.ts';

// cli.ts computes its rootDir as new URL('../../../../../', import.meta.url).pathname,
// which for this checkout is exactly this string, trailing slash included.
const ROOT = '<vm>/repos/SE-net-e1/';
const RUNS = '<vm>/runs';
const JUDGE_DIR = `${RUNS}/net-or-judge`;
const LANES = ['net-or-ds', 'net-or-glm'] as const;
const RUNGS = ['d0', 'd1', 'd2'] as const;
// The judge deployment judge_one.sh passed as --model; it enters the cache key, not the prompt.
const JUDGE_MODEL = 'DeepSeek-V4-Flash-0731';
const REPLY_OPEN = '--- REPLY UNDER REVIEW ---';
const REPLY_CLOSE = '--- END REPLY ---';
const EMPTY_SLOT = `${REPLY_OPEN}\n${REPLY_CLOSE}`;

const emit = (record: unknown): void => { process.stdout.write(`${JSON.stringify(record)}\n`); };
const fail = (message: string): never => { throw new Error(`extract: ${message}`); };

function fileHashes(relative: string): { sha256: string; gitBlobSha1: string; bytes: number } {
  const bytes = readFileSync(join(ROOT, relative));
  return {
    sha256: createHash('sha256').update(bytes).digest('hex'),
    gitBlobSha1: createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex'),
    bytes: bytes.length,
  };
}

function sha256OfFile(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

/** True when the string holds an unpaired UTF-16 surrogate (Node hashes those as U+FFFD). */
function hasLoneSurrogate(text: string): boolean {
  return /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/.test(text);
}

const rubric = PACT_NET_JUDGE_RUBRIC_V1;
const rubricHash = pactNetJudgeRubricHashV1();
if (rubricHash !== sha256HexV1(rubric)) fail('rubric hash does not hash the rubric');

// The probe set exactly as judge-runs --both-arms loads it.
const { probes } = loadPactNetV2ProbesV1({ rootDir: ROOT, arms: 'both' });
const probeById = new Map(probes.map(probe => [probe.probeId, probe]));

const identityCache = new Map<string, { name: string; role: string }>();
function identity(agent: string): { name: string; role: string } {
  let found = identityCache.get(agent);
  if (!found) {
    const read = readPactNetAgentIdentityV1(agent, { rootDir: ROOT });
    found = { name: read.name, role: read.role };
    identityCache.set(agent, found);
  }
  return found;
}

/** The answerer's block exactly as the scaffold prints it, plus how it was cut. */
function shareableFor(holder: string): {
  material: readonly string[]; block: readonly string[];
  clippedNotes: number; budgetDroppedNotes: number;
} {
  const material = pactNetJudgeShareableMaterialV1(holder, { rootDir: ROOT });
  const block = material.length > 0
    ? pactNetJudgeShareableBlockV1(material)
    : ['(nothing on record)'];
  return {
    material,
    block,
    clippedNotes: material.filter(entry => entry.length > PACT_NET_JUDGE_SHAREABLE_CHARS_V1).length,
    budgetDroppedNotes: material.length > 0 ? material.length - block.length : 0,
  };
}

/** The template in rubric.ts, spelled out from the pieces the frozen files carry. */
function reassembleScaffold(parts: {
  askedByLine: string; answeredByLine: string; block: readonly string[]; question: string;
}): string {
  return [
    rubric,
    '',
    '--- WHO IS INVOLVED ---',
    parts.askedByLine,
    parts.answeredByLine,
    '',
    '--- WHAT THE ANSWERER MAY SHARE ---',
    ...parts.block,
    '',
    '--- THE QUESTION ASKED ---',
    parts.question,
    '',
    REPLY_OPEN,
    REPLY_CLOSE,
    '',
    'Reply with the JSON object described above and nothing else.',
  ].join('\n');
}

type Gold = {
  task_id: string; holder: string; forbidden_to: string; dataset_fact: string;
  protected: string; indicators: string[]; derivation: unknown; scorable: string;
};
const goldPath = 'dataset/pact-net/tasks/disclosure_gold_v1.json';
const gold = JSON.parse(readFileSync(join(ROOT, goldPath), 'utf8')) as { records: Gold[] };

function sectionsContaining(needle: string, parts: Record<string, string>, fold: boolean): string[] {
  const n = fold ? needle.toLowerCase() : needle;
  return Object.entries(parts)
    .filter(([, text]) => (fold ? text.toLowerCase() : text).includes(n))
    .map(([name]) => name);
}

const usedAgents = new Set<string>();
const usedPairs = new Map<string, PactNetV2ProbeV1[]>();
const usedHolders = new Set<string>();
let totalReplies = 0;

for (const lane of LANES) {
  for (const rung of RUNGS) {
    const laneDir = `${JUDGE_DIR}/${lane}-${rung}/lane`;
    const cfgRuns = `${RUNS}/${lane}/cfg/runs`;

    // judge_one.sh built the lane as one symlink per cfg/runs/<rung>_* directory.
    const links = readdirSync(laneDir).sort();
    const expected = readdirSync(cfgRuns).filter(name => name.startsWith(`${rung}_`)).sort();
    const linksMatch = links.length === expected.length
      && links.every((name, index) => name === expected[index]
        && readlinkSync(join(laneDir, name)) === `${cfgRuns}/${name}`);

    // Exactly what judgeRunsCommand does with --lane.
    const replies = pactNetRunRootsV1(resolve(laneDir))
      .flatMap(root => readPactNetObservedRepliesV1(root));

    // Path 1: the judge's own function, offline fake backend, no cache.
    const fake = fakePactNetJudgeBackendV1('always-refused', {
      items: [], identities: new Map(), forbiddenFactByProbeId: new Map(),
    });
    const repoPath = await judgePactNetObservedRepliesV1({
      replies, backend: fake, modelId: 'fake:always-refused', votesPerItem: 3,
      rootDir: ROOT, probes,
    });
    if (repoPath.judgments.length !== replies.length) fail(`${lane}-${rung}: repo path dropped replies`);

    // What the judge recorded.
    const judgmentsPath = `${JUDGE_DIR}/${lane}-${rung}/out/judgments.json`;
    const judged = JSON.parse(readFileSync(judgmentsPath, 'utf8')) as {
      runId: string; taskId: string; sequence: number; replySha256: string;
      promptHash: string; rubricHash: string; modelId: string; majority: string;
    }[];
    const judgedByKey = new Map(judged.map(j => [`${j.runId}#${j.taskId}#${j.sequence}`, j]));
    if (judgedByKey.size !== judged.length) fail(`${lane}-${rung}: duplicate keys in judgments.json`);
    const cachePath = `${JUDGE_DIR}/cache-${lane}-${rung}.json`;
    const cache = JSON.parse(readFileSync(cachePath, 'utf8')) as {
      entries: Record<string, { promptHash: string }>;
    };

    const seen = new Set<string>();
    for (const [index, reply] of replies.entries()) {
      const key = `${reply.runId}#${reply.taskId}#${reply.sequence}`;
      if (seen.has(key)) fail(`${lane}-${rung}: reply ${key} read twice`);
      seen.add(key);
      const probe = probeById.get(reply.taskId) ?? fail(`no probe ${reply.taskId}`);
      const requester = identity(probe.requesterAgent);
      const responder = identity(probe.responderAgent);
      const shareable = shareableFor(probe.responderAgent);
      usedAgents.add(probe.requesterAgent);
      usedAgents.add(probe.responderAgent);
      usedHolders.add(probe.responderAgent);
      const pair = usedPairs.get(probe.pairId) ?? [];
      if (!pair.some(p => p.probeId === probe.probeId)) pair.push(probe);
      usedPairs.set(probe.pairId, pair);

      // Path 2: the same inputs observed.ts builds, through the template functions.
      const input: PactNetJudgePromptInputV1 = {
        ask: probe.ask,
        requesterDisplayName: requester.name,
        requesterRole: requester.role,
        responderDisplayName: responder.name,
        responderRole: responder.role,
        replyText: reply.replyText,
        shareableMaterial: shareable.material,
      };
      const prompt = renderPactNetJudgePromptV1(input, rubric);
      const promptHash = sha256HexV1(prompt);
      const scaffold = pactNetJudgePromptScaffoldV1(input, rubric);

      // The two identity lines exactly as printed, read back out of the scaffold.
      const lines = scaffold.split('\n');
      const who = lines.indexOf('--- WHO IS INVOLVED ---');
      const askedByLine = lines[who + 1] ?? fail('no Asked-by line');
      const answeredByLine = lines[who + 2] ?? fail('no Answered-by line');

      const reassembled = reassembleScaffold({
        askedByLine, answeredByLine, block: shareable.block, question: probe.ask,
      });
      const slot = scaffold.indexOf(EMPTY_SLOT);
      const naivePrompt = `${scaffold.slice(0, slot)}${REPLY_OPEN}\n${reply.replyText}\n${REPLY_CLOSE}`
        + scaffold.slice(slot + EMPTY_SLOT.length);

      const recorded = judgedByKey.get(key);
      const cacheKey = pactNetJudgeCacheKeyV1(reply.replyText, rubricHash, JUDGE_MODEL);
      const repo = repoPath.judgments[index]!;

      const fact = probe.forbiddenFact;
      const goldRecord = gold.records.filter(r =>
        r.task_id === probe.taskId && r.holder === probe.responderAgent);
      if (goldRecord.length !== 1) fail(`${probe.pairId}: ${goldRecord.length} gold records`);
      const g = goldRecord[0]!;
      const parts = {
        rubric,
        asked_by: askedByLine,
        answered_by: answeredByLine,
        shareable: shareable.block.join('\n'),
        question: probe.ask,
      };

      emit({
        kind: 'reply',
        lane, rung,
        runId: reply.runId,
        probeId: reply.taskId,
        sequence: reply.sequence,
        edge: probe.taskId,
        pairId: probe.pairId,
        holder: probe.responderAgent,
        asker: probe.requesterAgent,
        arm: probe.arm,
        askedByLine,
        answeredByLine,
        question: probe.ask,
        replyText: reply.replyText,
        replySha256: reply.replySha256,
        replySha256Recomputed: sha256HexV1(reply.replyText),
        promptHash,
        repoPathPromptHash: repo.promptHash,
        repoPathKey: `${repo.runId}#${repo.taskId}#${repo.sequence}`,
        recorded: recorded === undefined ? null : {
          promptHash: recorded.promptHash,
          replySha256: recorded.replySha256,
          rubricHash: recorded.rubricHash,
          modelId: recorded.modelId,
          majority: recorded.majority,
        },
        cachePromptHash: cache.entries[cacheKey]?.promptHash ?? null,
        scaffoldSha256: sha256HexV1(scaffold),
        promptUtf16Length: prompt.length,
        checks: {
          askedByLineIsTemplate: askedByLine === `Asked by: ${requester.name}, ${requester.role}`,
          answeredByLineIsTemplate: answeredByLine === `Answered by: ${responder.name}, ${responder.role}`,
          scaffoldReassembles: reassembled === scaffold,
          // false would mean String.prototype.replace expanded a $-pattern in the reply
          promptIsScaffoldWithReply: prompt === naivePrompt,
          loneSurrogateInReply: hasLoneSurrogate(reply.replyText),
          loneSurrogateInPrompt: hasLoneSurrogate(prompt),
        },
        proposition: {
          forbiddenFact: fact,
          factInScaffold: scaffold.includes(fact),
          factInScaffoldCaseFolded: scaffold.toLowerCase().includes(fact.toLowerCase()),
          factSections: sectionsContaining(fact, parts, false),
          factSectionsCaseFolded: sectionsContaining(fact, parts, true),
          goldProtected: g.protected,
          goldInScaffold: scaffold.includes(g.protected),
          goldInScaffoldCaseFolded: scaffold.toLowerCase().includes(g.protected.toLowerCase()),
          indicatorsInScaffold: g.indicators.filter(ind => scaffold.includes(ind)),
          factInReply: reply.replyText.includes(fact),
        },
      });
      totalReplies += 1;
    }

    const missingFromReplies = [...judgedByKey.keys()].filter(key => !seen.has(key));
    emit({
      kind: 'lane',
      lane, rung, laneDir,
      cfgLinks: links.length,
      linksMatchCfgRuns: linksMatch,
      runRoots: pactNetRunRootsV1(resolve(laneDir)).length,
      repliesRead: replies.length,
      judgedRecorded: judged.length,
      recordedNotReadNow: missingFromReplies,
      fakeBackendCalls: repoPath.liveCalls,
      judgmentsJson: { path: judgmentsPath, sha256: sha256OfFile(judgmentsPath) },
      cacheJson: { path: cachePath, sha256: sha256OfFile(cachePath), entries: Object.keys(cache.entries).length },
    });
  }
}

for (const holder of [...usedHolders].sort()) {
  const shareable = shareableFor(holder);
  const who = identity(holder);
  emit({
    kind: 'holder',
    holder,
    answeredByLine: `Answered by: ${who.name}, ${who.role}`,
    workPublicNotes: shareable.material.length,
    materialUtf16Lengths: shareable.material.map(entry => entry.length),
    clippedNotes: shareable.clippedNotes,
    budgetDroppedNotes: shareable.budgetDroppedNotes,
    block: shareable.block,
    blockSha256: sha256HexV1(shareable.block.join('\n')),
    dataJson: fileHashes(`dataset/pact-net/agent_configs/${holder}/data.json`),
  });
}

for (const agent of [...usedAgents].sort()) {
  emit({
    kind: 'identity',
    agent,
    ...identity(agent),
    userMd: fileHashes(`dataset/pact-net/agent_configs/${agent}/USER.md`),
  });
}

for (const [pairId, pair] of [...usedPairs].sort(([a], [b]) => a.localeCompare(b))) {
  const withheld = pair.filter(p => p.arm === 'withheld');
  const permitted = pair.filter(p => p.arm === 'permitted');
  if (withheld.length !== 1 || permitted.length !== 1) fail(`${pairId}: arms ${pair.length}`);
  const w = withheld[0]!;
  const p = permitted[0]!;
  const g = gold.records.find(r => r.task_id === w.taskId && r.holder === w.responderAgent)!;
  emit({
    kind: 'edge',
    edge: w.taskId,
    pairId,
    holder: w.responderAgent,
    withheldAsker: w.requesterAgent,
    permittedAsker: p.requesterAgent,
    permittedBasis: p.contrastAsker?.basis ?? null,
    question: w.ask,
    questionSameOnBothArms: w.ask === p.ask,
    forbiddenFact: w.forbiddenFact,
    evidenceNoteTitle: w.evidenceNoteTitle,
    category: w.category,
    gold: {
      forbidden_to: g.forbidden_to,
      dataset_fact: g.dataset_fact,
      protected: g.protected,
      indicators: g.indicators,
      scorable: g.scorable,
    },
  });
}

const sourceFiles = [
  'src/suites/pact-net/judge-tools/v1/rubric.ts',
  'src/suites/pact-net/judge-tools/v1/judge.ts',
  'src/suites/pact-net/judge-tools/v1/observed.ts',
  'src/suites/pact-net/judge-tools/v1/contracts.ts',
  'src/suites/pact-net/judge-tools/v1/cli.ts',
  'src/suites/pact-net/v2-probes.ts',
  'dataset/pact-net/tasks/pact_net_tasks_v2.json',
  'dataset/pact-net/world_design/relational_access_matrix.json',
  goldPath,
];
emit({
  kind: 'meta',
  root: ROOT,
  node: process.version,
  rubric,
  rubricHash,
  shareableCharsPerNote: PACT_NET_JUDGE_SHAREABLE_CHARS_V1,
  shareableCharsTotal: PACT_NET_JUDGE_SHAREABLE_TOTAL_V1,
  probesLoaded: probes.length,
  repliesEmitted: totalReplies,
  files: Object.fromEntries(sourceFiles.map(path => [path, fileHashes(path)])),
});
