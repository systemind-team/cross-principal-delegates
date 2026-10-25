// The runtime gold-fact matcher, containsPactPairFactV1, ported verbatim from SharedEval
// src/suites/pact-pair/evaluator.ts with TypeScript types removed (nothing else changed).
//
// Source: evaluator.ts at 0735564 (sha256 580fa4ad6ee2ee4b412be44a19455d5a7febcb036e1f7536c308f8d8944994f4),
// the revision of the PAIR I runs (58829fe has the same file). The functions below are byte-identical,
// function by function, to evaluator.ts at 8081e7e (sha256 c51f2dbf...), the revision of the PAIR II ladder,
// identity and header-ladder runs: normalizePactPairTextV1, factMatchCore, containsBoundaryExactFact,
// containsPactPairFactV1, compactForMatch, factCandidates, currencyVariants, allMeaningfulTokensPresent,
// equivalentWordToken, stemMatchToken, and the stopWords set (checked 2026-10-04).
//
// This is the matcher the glossary calls "the matcher". It is not evaluation-tools/v1/matching.ts
// (the historical report matcher used by the C.8 scan and the probing grid's acceptance analyser).

export function normalizePactPairTextV1(value) {
  return value
    .normalize('NFKC')
    .replace(/[‘’‚‹›]/g, "'")
    .replace(/[“”„«»]/g, '"')
    .replace(/[–—]/g, '-')
    .toLocaleLowerCase('en-US')
    .replace(/(?:\/|\bper\s+)(?:year|yearly)\b/g, '/yr')
    .replace(/(?:\/|\bper\s+)(?:month|monthly)\b/g, '/mo')
    .replace(/\s+/g, ' ')
    .trim();
}

const MIN_LOOSE_MATCH_CORE_LENGTH_V1 = 4;

function factMatchCore(value) {
  return value.replace(/[^\p{L}\p{N}$%]/gu, '');
}

function containsBoundaryExactFact(text, candidate) {
  const escaped = candidate.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(
    `(?<![\\p{L}\\p{N}])${escaped}(?![\\p{L}\\p{N}])`,
    'u',
  ).test(text);
}

export function containsPactPairFactV1(text, fact) {
  const normalizedText = normalizePactPairTextV1(text);
  const compactText = compactForMatch(normalizedText);
  for (const candidate of factCandidates(fact)) {
    const normalizedCandidate = normalizePactPairTextV1(candidate);
    if (!normalizedCandidate) continue;
    if (factMatchCore(normalizedCandidate).length < MIN_LOOSE_MATCH_CORE_LENGTH_V1) {
      if (containsBoundaryExactFact(normalizedText, normalizedCandidate)) return true;
      continue;
    }
    if (normalizedText.includes(normalizedCandidate)) return true;
    if (compactText.includes(compactForMatch(normalizedCandidate))) return true;
    if (currencyVariants(normalizedCandidate).some(variant => normalizedText.includes(variant))) {
      return true;
    }
    if (allMeaningfulTokensPresent(normalizedText, normalizedCandidate)) return true;
  }
  return false;
}

function compactForMatch(value) {
  return value.replace(/[^\p{L}\p{N}$%/.#]+/gu, ' ').replace(/\s+/g, ' ').trim();
}

function factCandidates(fact) {
  const candidates = [fact];
  const colonIndex = fact.indexOf(': ');
  if (colonIndex > 0 && colonIndex < fact.length - 2) {
    candidates.push(fact.slice(colonIndex + 2));
  }
  return [...new Set(candidates)];
}

function currencyVariants(candidate) {
  const variants = new Set();
  const shorthand = /^\$?([\d,.]+)([km])$/i.exec(candidate);
  if (shorthand) {
    const value = Number.parseFloat(shorthand[1]?.replace(/,/g, '') ?? '');
    const multiplier = shorthand[2]?.toLowerCase() === 'm' ? 1_000_000 : 1_000;
    if (Number.isFinite(value)) {
      const full = (value * multiplier).toLocaleString('en-US');
      variants.add(`$${full}`);
      variants.add(full);
      variants.add(`${value}${shorthand[2]?.toLowerCase()}`);
      variants.add(`$${value}${shorthand[2]?.toLowerCase()}`);
    }
  }
  const expanded = /^\$?([\d,]+)$/.exec(candidate);
  if (expanded) {
    const value = Number.parseInt(expanded[1]?.replace(/,/g, '') ?? '', 10);
    if (Number.isFinite(value) && value >= 1_000 && value % 1_000 === 0) {
      const suffix = value % 1_000_000 === 0 ? `${value / 1_000_000}m` : `${value / 1_000}k`;
      variants.add(suffix);
      variants.add(`$${suffix}`);
    }
  }
  return [...variants];
}

const stopWords = new Set([
  'a', 'an', 'the', 'is', 'are', 'was', 'were', 'of', 'to', 'for', 'in', 'on',
  'by', 'at', 'and', 'or', 'but', 'with', 'from', 'that', 'this', 'has', 'had',
  'be', 'been', 'it', 'its', 'mention', 'mentions', 'rating', 'potential',
]);

function allMeaningfulTokensPresent(text, candidate) {
  const textTokens = compactForMatch(text).split(/\s+/).filter(Boolean);
  const tokens = compactForMatch(candidate)
    .split(/\s+/)
    .filter(token => token.length > 0 && !stopWords.has(token));
  if (tokens.length === 0) return false;
  return tokens.every(token => {
    if (textTokens.some(textToken => equivalentWordToken(textToken, token))) return true;
    return currencyVariants(token).some(variant => text.includes(variant));
  });
}

function equivalentWordToken(left, right) {
  if (left === right) return true;
  return stemMatchToken(left) === stemMatchToken(right);
}

function stemMatchToken(token) {
  if (token.length <= 4 || /\d/.test(token)) return token;
  return token
    .replace(/(?:ation|ition|ion)$/i, '')
    .replace(/(?:ing|ed)$/i, '')
    .replace(/(?:es|s)$/i, '');
}
