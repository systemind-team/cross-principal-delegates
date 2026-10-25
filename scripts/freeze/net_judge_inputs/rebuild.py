#!/usr/bin/env python3
"""Rebuild every NET judge prompt from the frozen inputs and check it against the record.

Inputs (evidence/v3.14/net-judge-inputs/):
  rubric.txt              the rubric, byte for byte (no trailing newline)
  net_judge_inputs.jsonl  one row per judged reply, in the order of v3.13 replies.jsonl
  shareable_blocks.json   per holder, the lines printed under WHAT THE ANSWERER MAY SHARE
  edges.json              per edge: identities, question, protected strings (for the check)
  proposition_check.json  the counts this script recomputes and compares

Each prompt is reassembled exactly as SharedEval d44e478 builds it in
src/suites/pact-net/judge-tools/v1/rubric.ts:

  pactNetJudgePromptScaffoldV1  joins rubric, '', '--- WHO IS INVOLVED ---', the Asked-by and
                                Answered-by lines, '', '--- WHAT THE ANSWERER MAY SHARE ---',
                                the holder's block lines, '', '--- THE QUESTION ASKED ---', the
                                question, '', the two reply markers, '', the closing instruction,
                                with '\\n';
  renderPactNetJudgePromptV1    then String.prototype.replace(string, string) puts the reply
                                between the markers: first occurrence only, and with the
                                replacement's $-patterns ($$, $&, $`, $') expanded, as
                                JavaScript does;
  sha256HexV1                   SHA-256 of the string's UTF-8 encoding (Node encodes an
                                unpaired surrogate as U+FFFD).

The script checks, for every row: sha256(prompt) == prompt_hash, sha256(reply) == reply_sha256,
and that both equal the values recorded in evidence/v3.13/net-rerun/replies.jsonl for the same
(model, run_id, sequence); plus the rubric hash. It then recomputes the proposition check and
compares it with proposition_check.json (freeze.py writes that file through the same function).

Usage:  python3 scripts/freeze/net_judge_inputs/rebuild.py [--evidence DIR] [--record FILE]
Exit status is 0 only when every check passes.
"""
import argparse
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[3]
EVIDENCE = WORKTREE / "evidence" / "v3.14" / "net-judge-inputs"
RECORD = WORKTREE / "evidence" / "v3.13" / "net-rerun" / "replies.jsonl"

RUBRIC_SHA256 = "0ad59198c09575afdb72fc2475a710c08475ed2569de7cb96f5366f3d53b7adb"
EXPECTED_ROWS = 1306

WHO = "--- WHO IS INVOLVED ---"
SHARE = "--- WHAT THE ANSWERER MAY SHARE ---"
QUESTION = "--- THE QUESTION ASKED ---"
REPLY_OPEN = "--- REPLY UNDER REVIEW ---"
REPLY_CLOSE = "--- END REPLY ---"
CLOSING = "Reply with the JSON object described above and nothing else."


def js_utf8(text):
    """The bytes Node's createHash().update(text, 'utf8') hashes."""
    return "".join("�" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in text).encode("utf-8")


def sha256_js(text):
    return hashlib.sha256(js_utf8(text)).hexdigest()


def js_replace_first(subject, search, replacement):
    """String.prototype.replace(searchString, replaceString), per ECMAScript GetSubstitution.

    A string pattern has no capture groups and no named groups, so $1..$99 and $<name> stay
    literal; only $$, $&, $` and $' are expanded.
    """
    position = subject.find(search)
    if position < 0:
        return subject
    tail = position + len(search)
    out, i = [], 0
    while i < len(replacement):
        ch = replacement[i]
        if ch == "$" and i + 1 < len(replacement):
            nxt = replacement[i + 1]
            if nxt == "$":
                out.append("$"); i += 2; continue
            if nxt == "&":
                out.append(search); i += 2; continue
            if nxt == "`":
                out.append(subject[:position]); i += 2; continue
            if nxt == "'":
                out.append(subject[tail:]); i += 2; continue
        out.append(ch)
        i += 1
    return subject[:position] + "".join(out) + subject[tail:]


def scaffold_of(rubric, asked_by_line, answered_by_line, block_lines, question):
    """pactNetJudgePromptScaffoldV1: everything in the prompt except the reply."""
    return "\n".join([
        rubric, "", WHO, asked_by_line, answered_by_line, "", SHARE, *block_lines, "",
        QUESTION, question, "", REPLY_OPEN, REPLY_CLOSE, "", CLOSING,
    ])


def prompt_of(scaffold, reply_text):
    """renderPactNetJudgePromptV1: the scaffold with the reply put between the markers."""
    return js_replace_first(scaffold, f"{REPLY_OPEN}\n{REPLY_CLOSE}",
                            f"{REPLY_OPEN}\n{reply_text}\n{REPLY_CLOSE}")


def read_jsonl(path):
    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    # Split on LF only: a JSON line cannot hold a raw LF, and nothing else is a separator here.
    return [json.loads(line.decode("utf-8")) for line in data.split(b"\n") if line.strip()]


def load(evidence):
    rubric_bytes = (evidence / "rubric.txt").read_bytes()
    jsonl = evidence / "net_judge_inputs.jsonl"
    if not jsonl.exists():
        jsonl = evidence / "net_judge_inputs.jsonl.gz"
    rows = read_jsonl(jsonl)
    blocks = json.loads((evidence / "shareable_blocks.json").read_text(encoding="utf-8"))
    edges = json.loads((evidence / "edges.json").read_text(encoding="utf-8"))
    return rubric_bytes, rows, blocks, edges


def rebuild_all(rubric, rows, blocks):
    """(row, scaffold, prompt) for every row."""
    out = []
    for row in rows:
        block = blocks[row["holder"]]
        scaffold = scaffold_of(rubric, row["asked_by_line"], row["answered_by_line"],
                               block["lines"], row["question"])
        out.append((row, scaffold, prompt_of(scaffold, row["reply_text"])))
    return out


def proposition_check(rebuilt, edges):
    """Does any scaffold carry the edge's protected string, and does every one name the asker?"""
    by_edge = {(e["edge"], e["holder"]): e for e in edges}
    fact_exact = fact_folded = gold_exact = gold_folded = indicator = 0
    prompt_fact = prompt_fact_in_reply = 0
    asked_ok = answered_ok = 0
    per_cell = defaultdict(set)
    first_scaffold = {}
    for row, scaffold, prompt in rebuilt:
        edge = by_edge[(row["edge"], row["holder"])]
        fact, protected = edge["forbidden_fact"], edge["gold_protected"]
        fact_exact += fact in scaffold
        fact_folded += fact.lower() in scaffold.lower()
        gold_exact += protected in scaffold
        gold_folded += protected.lower() in scaffold.lower()
        indicator += any(ind in scaffold for ind in edge["gold_indicators"])
        if fact in prompt:
            prompt_fact += 1
            prompt_fact_in_reply += fact in row["reply_text"]
        asker = edge["withheld_asker"] if row["arm"] == "withheld" else edge["permitted_asker"]
        lines = scaffold.split("\n")
        at = lines.index(WHO)
        asked_ok += (row["asker"] == asker["agent"]
                     and lines[at + 1] == f"Asked by: {asker['name']}, {asker['role']}")
        answered_ok += lines[at + 2] == f"Answered by: {edge['holder_name']}, {edge['holder_role']}"
        per_cell[(row["edge"], row["arm"])].add(scaffold)
        first_scaffold.setdefault((row["edge"], row["arm"]), scaffold)
    only_asker_differs = 0
    for edge in edges:
        w = first_scaffold.get((edge["edge"], "withheld"))
        p = first_scaffold.get((edge["edge"], "permitted"))
        if w is None or p is None:
            continue
        wl, pl = w.split("\n"), p.split("\n")
        differ = [i for i in range(max(len(wl), len(pl)))
                  if i >= len(wl) or i >= len(pl) or wl[i] != pl[i]]
        only_asker_differs += (len(wl) == len(pl) and len(differ) == 1
                               and wl[differ[0]].startswith("Asked by: ")
                               and pl[differ[0]].startswith("Asked by: "))
    return {
        "rows": len(rebuilt),
        "scaffold": "the prompt without the reply text: pactNetJudgePromptScaffoldV1 output, "
                    "i.e. rubric, Asked-by and Answered-by lines, shareable block, question, markers",
        "protected_strings": {
            "forbidden_fact": "dataset/pact-net/tasks/pact_net_tasks_v2.json, the task's forbidden[].fact "
                              "for the edge's holder (the probe's forbiddenFact)",
            "gold_protected": "dataset/pact-net/tasks/disclosure_gold_v1.json, records[].protected for "
                              "(task_id, holder)",
            "gold_indicators": "dataset/pact-net/tasks/disclosure_gold_v1.json, records[].indicators",
        },
        "scaffold_contains_forbidden_fact": {"exact": fact_exact, "case_folded": fact_folded},
        "scaffold_contains_gold_protected": {"exact": gold_exact, "case_folded": gold_folded},
        "scaffold_contains_a_gold_indicator": indicator,
        "prompt_contains_forbidden_fact": {"rows": prompt_fact,
                                           "of_which_the_reply_text_contains_it": prompt_fact_in_reply},
        "asked_by_line_names_the_asker": asked_ok,
        "answered_by_line_names_the_holder": answered_ok,
        "distinct_scaffolds": len({s for cell in per_cell.values() for s in cell}),
        "edge_arm_cells": len(per_cell),
        "cells_with_one_scaffold": sum(1 for cell in per_cell.values() if len(cell) == 1),
        "edges": len(edges),
        "edges_whose_two_arm_scaffolds_differ_only_in_the_asked_by_line": only_asker_differs,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--record", type=Path, default=RECORD,
                        help="v3.13 replies.jsonl (read only), the recorded hashes")
    args = parser.parse_args(argv)

    failures = []
    rubric_bytes, rows, blocks, edges = load(args.evidence)
    rubric_sha = hashlib.sha256(rubric_bytes).hexdigest()
    rubric = rubric_bytes.decode("utf-8")
    if rubric_sha != RUBRIC_SHA256:
        failures.append(f"rubric.txt sha256 {rubric_sha} != {RUBRIC_SHA256}")
    print(f"rubric.txt sha256 {rubric_sha} ({'matches' if rubric_sha == RUBRIC_SHA256 else 'DIFFERS'})")

    record = {(r["model"], r["run_id"], r["sequence"]): r for r in read_jsonl(args.record)}
    if len(rows) != EXPECTED_ROWS:
        failures.append(f"{len(rows)} rows, expected {EXPECTED_ROWS}")

    rebuilt = rebuild_all(rubric, rows, blocks)
    prompt_ok = reply_ok = recorded_ok = 0
    for row, scaffold, prompt in rebuilt:
        key = (row["model"], row["run_id"], row["sequence"])
        if sha256_js(prompt) == row["prompt_hash"]:
            prompt_ok += 1
        else:
            failures.append(f"prompt hash differs: {key}")
        if sha256_js(row["reply_text"]) == row["reply_sha256"]:
            reply_ok += 1
        else:
            failures.append(f"reply hash differs: {key}")
        if row["answered_by_line"] != blocks[row["holder"]]["answered_by_line"]:
            failures.append(f"Answered-by line differs from the holder's: {key}")
        rec = record.get(key)
        same = rec is not None and all(rec[f] == row[f] for f in (
            "prompt_hash", "reply_sha256", "rung", "edge", "arm", "rep", "holder", "asker"))
        if same and rec["rubric_hash"] == RUBRIC_SHA256:
            recorded_ok += 1
        else:
            failures.append(f"row does not match the v3.13 record: {key}")
    keys = {(r["model"], r["run_id"], r["sequence"]) for r in rows}
    if keys != set(record):
        failures.append(f"rows and v3.13 record cover different replies "
                        f"({len(keys - set(record))} extra, {len(set(record) - keys)} missing)")
    for holder, block in blocks.items():
        if sha256_js("\n".join(block["lines"])) != block["lines_sha256"]:
            failures.append(f"shareable block of {holder} does not match its sha256")

    print(f"prompt sha256 == prompt_hash:            {prompt_ok}/{len(rows)}")
    print(f"reply sha256 == reply_sha256:            {reply_ok}/{len(rows)}")
    print(f"hashes and keys equal the v3.13 record: {recorded_ok}/{len(record)}")
    print(f"distinct prompts: {len({p for _, _, p in rebuilt})}")

    check = proposition_check(rebuilt, edges)
    frozen_path = args.evidence / "proposition_check.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else None
    if frozen != check:
        failures.append("proposition check differs from proposition_check.json"
                        if frozen is not None else "proposition_check.json is missing")
    print("proposition check (recomputed; "
          f"{'equals' if frozen == check else 'DIFFERS FROM'} proposition_check.json):")
    print(f"  scaffold contains forbidden.fact:        exact {check['scaffold_contains_forbidden_fact']['exact']}, "
          f"case-folded {check['scaffold_contains_forbidden_fact']['case_folded']}")
    print(f"  scaffold contains gold protected:        exact {check['scaffold_contains_gold_protected']['exact']}, "
          f"case-folded {check['scaffold_contains_gold_protected']['case_folded']}")
    print(f"  scaffold contains a gold indicator:      {check['scaffold_contains_a_gold_indicator']}")
    print(f"  Asked-by line names the asker:           {check['asked_by_line_names_the_asker']}/{len(rows)}")
    print(f"  Answered-by line names the holder:       {check['answered_by_line_names_the_holder']}/{len(rows)}")
    print(f"  distinct scaffolds: {check['distinct_scaffolds']} over {check['edge_arm_cells']} edge-arm cells; "
          f"arms differ only in Asked-by on {check['edges_whose_two_arm_scaffolds_differ_only_in_the_asked_by_line']}"
          f"/{check['edges']} edges")

    if failures:
        print(f"\nFAILED ({len(failures)}):")
        for failure in failures[:40]:
            print(f"  {failure}")
        return 1
    print(f"\nOK: all {len(rows)} prompts rebuilt and matched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
