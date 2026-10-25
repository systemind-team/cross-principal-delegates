#!/usr/bin/env python3
"""Write evidence/v3.14/net-judge-inputs/ from the VM extraction, after checking it against the record.

Inputs (see the README in the evidence folder for the exact commands that produce them):
  --extraction  gzipped JSONL printed by extract_net_judge_inputs.ts on the VM
  --git         `git rev-parse HEAD`, branch, dirty-file count and `git ls-tree -r HEAD` of the
                SharedEval checkout, as captured by the README command
Read only: evidence/v3.13/net-rerun/{replies.jsonl,manifest.json}.

Nothing is written unless every check passes: each of the 1,306 recorded rows must find exactly
one extracted reply with the same model lane, rung, run id and sequence, the same edge, holder,
asker and arm, and a prompt hash and reply hash equal to the recorded ones by every path the
extraction computed (its own render, the judge's own function, the judge's judgments.json and
its cache); and every file the extraction read must be the blob committed at the recorded
SharedEval revision.

Writes: rubric.txt, net_judge_inputs.jsonl, shareable_blocks.json, edges.json,
proposition_check.json (through rebuild.proposition_check), provenance.json.

Usage:  python3 scripts/freeze/net_judge_inputs/freeze.py --extraction X.jsonl.gz --git Y.txt
"""
import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild  # noqa: E402  (same folder)

WORKTREE = rebuild.WORKTREE
RECORD_DIR = WORKTREE / "evidence" / "v3.13" / "net-rerun"
OUT = rebuild.EVIDENCE
LANE_OF_MODEL = {"deepseek-v4-flash": "net-or-ds", "glm-5.3": "net-or-glm"}
JUDGE_MODEL = "DeepSeek-V4-Flash-0731"
EXTRACT_SCRIPT = Path(__file__).resolve().parent / "extract_net_judge_inputs.ts"


def fail(message):
    sys.exit(f"freeze: {message}")


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--git", type=Path, required=True)
    args = parser.parse_args()

    raw = gzip.decompress(args.extraction.read_bytes())
    records = [json.loads(line.decode("utf-8")) for line in raw.split(b"\n") if line.strip()]
    kinds = Counter(r["kind"] for r in records)
    meta = next(r for r in records if r["kind"] == "meta")
    lanes = [r for r in records if r["kind"] == "lane"]
    replies = [r for r in records if r["kind"] == "reply"]
    holders = {r["holder"]: r for r in records if r["kind"] == "holder"}
    identities = {r["agent"]: r for r in records if r["kind"] == "identity"}
    edges = [r for r in records if r["kind"] == "edge"]

    manifest = json.loads((RECORD_DIR / "manifest.json").read_text(encoding="utf-8"))
    revision = manifest["runner"]["sharedeval_source_revision"]
    rubric_hash = manifest["judge"]["rubric_hash"]

    # --- the checkout the extraction read is the recorded revision, unmodified -------------
    git_lines = args.git.read_text(encoding="utf-8").splitlines()
    head, branch, dirty = git_lines[0].strip(), git_lines[1].strip(), int(git_lines[2])
    blobs = {}
    for line in git_lines[3:]:
        mode_type_blob, path = line.split("\t", 1)
        blobs[path] = mode_type_blob.split()[2]
    if head != revision:
        fail(f"checkout HEAD {head} is not the recorded revision {revision}")
    if dirty != 0:
        fail(f"{dirty} modified or untracked files under src/suites/pact-net or dataset/pact-net")
    files_read = dict(meta["files"])
    for h in holders.values():
        files_read[f"dataset/pact-net/agent_configs/{h['holder']}/data.json"] = h["dataJson"]
    for i in identities.values():
        files_read[f"dataset/pact-net/agent_configs/{i['agent']}/USER.md"] = i["userMd"]
    for path, hashes in files_read.items():
        if blobs.get(path) != hashes["gitBlobSha1"]:
            fail(f"{path}: content read is not the blob at {revision}")

    # --- rubric -------------------------------------------------------------------------------
    rubric = meta["rubric"]
    if not (meta["rubricHash"] == rubric_hash == rebuild.RUBRIC_SHA256 == rebuild.sha256_js(rubric)):
        fail("rubric hash mismatch")

    # --- the lanes the final judge pass read ------------------------------------------------
    for lane in lanes:
        if not lane["linksMatchCfgRuns"] or lane["recordedNotReadNow"] \
                or lane["repliesRead"] != lane["judgedRecorded"]:
            fail(f"lane {lane['lane']}-{lane['rung']} does not reproduce the judged set")

    # --- every recorded row against the extraction ---------------------------------------------
    by_key = {}
    for r in replies:
        key = (r["lane"], r["rung"], r["runId"], r["sequence"])
        if key in by_key:
            fail(f"extracted reply {key} twice")
        by_key[key] = r
    record_rows = rebuild.read_jsonl(RECORD_DIR / "replies.jsonl")
    if len(record_rows) != rebuild.EXPECTED_ROWS or len(replies) != rebuild.EXPECTED_ROWS:
        fail(f"{len(record_rows)} recorded rows, {len(replies)} extracted replies")

    tally = Counter()
    rows = []
    for rec in record_rows:
        key = (LANE_OF_MODEL[rec["model"]], rec["rung"].lower(), rec["run_id"], rec["sequence"])
        ext = by_key.pop(key, None)
        if ext is None:
            fail(f"recorded row {key} has no extracted reply")
        same_cell = (ext["edge"], ext["holder"], ext["asker"], ext["arm"]) == \
            (rec["edge"], rec["holder"], rec["asker"], rec["arm"])
        prompt_paths = {ext["promptHash"], ext["repoPathPromptHash"], ext["recorded"]["promptHash"],
                        ext["cachePromptHash"]}
        reply_paths = {ext["replySha256"], ext["replySha256Recomputed"], ext["recorded"]["replySha256"]}
        if not same_cell:
            fail(f"{key}: edge/holder/asker/arm differ from the record")
        if prompt_paths != {rec["prompt_hash"]}:
            fail(f"{key}: prompt hash differs between paths {sorted(prompt_paths)} and record")
        if reply_paths != {rec["reply_sha256"]}:
            fail(f"{key}: reply hash differs")
        if not (rec["rubric_hash"] == ext["recorded"]["rubricHash"] == rubric_hash):
            fail(f"{key}: rubric hash differs")
        if rec["judge_model"] != ext["recorded"]["modelId"] or rec["majority"] != ext["recorded"]["majority"]:
            fail(f"{key}: judge model or majority differs from judgments.json")
        if ext["repoPathKey"] != f"{ext['runId']}#{ext['probeId']}#{ext['sequence']}":
            fail(f"{key}: repository path judged a different reply at this position")
        if not all(ext["checks"][k] for k in ("askedByLineIsTemplate", "answeredByLineIsTemplate",
                                               "scaffoldReassembles")):
            fail(f"{key}: scaffold does not reassemble from its parts")
        if ext["answeredByLine"] != holders[ext["holder"]]["answeredByLine"]:
            fail(f"{key}: Answered-by line differs from the holder's")
        tally["rows"] += 1
        tally["dollar_pattern_expanded"] += not ext["checks"]["promptIsScaffoldWithReply"]
        tally["lone_surrogates"] += ext["checks"]["loneSurrogateInPrompt"]
        rows.append({
            "run_id": rec["run_id"],
            "model": rec["model"],
            "rung": rec["rung"],
            "edge": rec["edge"],
            "arm": rec["arm"],
            "rep": rec["rep"],
            "sequence": rec["sequence"],
            "holder": rec["holder"],
            "asker": rec["asker"],
            "probe_id": ext["probeId"],
            "prompt_hash": rec["prompt_hash"],
            "reply_sha256": rec["reply_sha256"],
            "asked_by_line": ext["askedByLine"],
            "answered_by_line": ext["answeredByLine"],
            "question": ext["question"],
            "reply_text": ext["replyText"],
        })
    if by_key:
        fail(f"{len(by_key)} extracted replies are not in the record")
    if tally["lone_surrogates"]:
        fail("a prompt holds an unpaired surrogate; the JSONL writer below cannot carry it")

    def who(agent):
        return {"agent": agent, "name": identities[agent]["name"], "role": identities[agent]["role"]}

    edge_rows = []
    for e in sorted(edges, key=lambda e: e["edge"]):
        edge_rows.append({
            "edge": e["edge"],
            "holder": e["holder"],
            "holder_name": identities[e["holder"]]["name"],
            "holder_role": identities[e["holder"]]["role"],
            "withheld_asker": who(e["withheldAsker"]),
            "permitted_asker": who(e["permittedAsker"]),
            "permitted_basis": e["permittedBasis"],
            "question": e["question"],
            "forbidden_fact": e["forbiddenFact"],
            "forbidden_to": e["gold"]["forbidden_to"],
            "evidence_note_title": e["evidenceNoteTitle"],
            "category": e["category"],
            "gold_protected": e["gold"]["protected"],
            "gold_indicators": e["gold"]["indicators"],
            "gold_scorable": e["gold"]["scorable"],
        })
        if e["gold"]["forbidden_to"] != e["withheldAsker"] or e["gold"]["dataset_fact"] != e["forbiddenFact"]:
            fail(f"{e['edge']}: gold record does not describe the probed edge")
        if not e["questionSameOnBothArms"]:
            fail(f"{e['edge']}: the two arms were asked different questions")

    jsonl = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    if len(jsonl) > 5 * 1024 * 1024:
        fail("per-reply JSONL is over 5 MB; gzip it (rebuild.py reads .jsonl.gz)")

    # --- write ----------------------------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rubric.txt").write_bytes(rubric.encode("utf-8"))
    (OUT / "net_judge_inputs.jsonl").write_bytes(jsonl)

    blocks = {}
    for holder in sorted(holders):
        h = holders[holder]
        blocks[holder] = {
            "answered_by_line": h["answeredByLine"],
            "work_public_notes": h["workPublicNotes"],
            "clipped_notes": h["clippedNotes"],
            "budget_dropped_notes": h["budgetDroppedNotes"],
            "lines_sha256": h["blockSha256"],
            "lines": h["block"],
        }
    dump_json(OUT / "shareable_blocks.json", blocks)

    dump_json(OUT / "edges.json", edge_rows)

    rubric_bytes, frozen_rows, frozen_blocks, frozen_edges = rebuild.load(OUT)
    check = rebuild.proposition_check(
        rebuild.rebuild_all(rubric_bytes.decode("utf-8"), frozen_rows, frozen_blocks), frozen_edges)
    dump_json(OUT / "proposition_check.json", check)

    lane_rows = []
    for lane in lanes:
        mine = [r for r in replies if r["lane"] == lane["lane"] and r["rung"] == lane["rung"]]
        lane_rows.append({
            "lane": f"{lane['lane']}-{lane['rung']}",
            "lane_dir": lane["laneDir"],
            "cfg_symlinks": lane["cfgLinks"],
            "symlinks_match_cfg_runs": lane["linksMatchCfgRuns"],
            "run_roots": lane["runRoots"],
            "replies_read_now": lane["repliesRead"],
            "judgments_recorded": lane["judgedRecorded"],
            "judgments_json": lane["judgmentsJson"],
            "cache_json": lane["cacheJson"],
            "prompt_hash_equal_to_judgments_json": sum(
                r["promptHash"] == r["recorded"]["promptHash"] for r in mine),
        })
    dump_json(OUT / "provenance.json", {
        "what": "Provenance of the frozen NET judge inputs; see README.md",
        "sharedeval": {
            "vm_checkout": meta["root"].rstrip("/"),
            "branch": branch,
            "head": head,
            "equals_record_revision": head == revision,
            "modified_or_untracked_files_under_src_suites_pact_net_and_dataset_pact_net": dirty,
        },
        "judge": {
            "model": JUDGE_MODEL,
            "rubric_sha256": rubric_hash,
            "invocation": "npm run -s judge:pact-net -- judge-runs --lane <J>/<L>-<G>/lane --both-arms "
                          "--model DeepSeek-V4-Flash-0731 --votes 3 --max-calls 6000 --label <L>-<G> "
                          "--out <J>/<L>-<G>/out --cache <J>/cache-<L>-<G>.json",
            "code_path": "cli.ts judgeRunsCommand -> observed.ts judgePactNetObservedRepliesV1 -> "
                         "rubric.ts renderPactNetJudgePromptV1 -> contracts.ts sha256HexV1",
            "judge_dir": "<vm>/runs/net-or-judge",
            "responder_runs": ["<vm>/runs/net-or-ds/cfg/runs",
                               "<vm>/runs/net-or-glm/cfg/runs"],
        },
        "lanes": lane_rows,
        "files_read": {path: {"sha256": h["sha256"], "git_blob_sha1": h["gitBlobSha1"],
                              "bytes": h["bytes"], "blob_at_head": True}
                       for path, h in sorted(files_read.items())},
        "extraction": {
            "script": "scripts/freeze/net_judge_inputs/extract_net_judge_inputs.ts",
            "script_sha256": hashlib.sha256(EXTRACT_SCRIPT.read_bytes()).hexdigest(),
            "output_sha256_uncompressed": hashlib.sha256(raw).hexdigest(),
            "output_records": dict(sorted(kinds.items())),
            "node": meta["node"],
            "probes_loaded_both_arms": meta["probesLoaded"],
            "shareable_chars_per_note": meta["shareableCharsPerNote"],
            "shareable_chars_total": meta["shareableCharsTotal"],
        },
        "checks": {
            "rows": tally["rows"],
            "prompt_hash_equal_on_all_paths": tally["rows"],
            "paths": ["extraction render (rubric.ts functions)",
                      "observed.ts judgePactNetObservedRepliesV1 with the offline always-refused fake",
                      "out/judgments.json promptHash", "cache-<lane>.json entry promptHash",
                      "v3.13 replies.jsonl prompt_hash"],
            "reply_sha256_equal_on_all_paths": tally["rows"],
            "prompts_where_a_dollar_pattern_was_expanded": tally["dollar_pattern_expanded"],
            "prompts_with_unpaired_surrogates": tally["lone_surrogates"],
        },
    })
    print(f"wrote {len(rows)} rows, {len(blocks)} holder blocks, {len(edge_rows)} edges to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
