#!/usr/bin/env python3
"""P1-2, annotator option (c): run a scripted non-Claude annotator (a Gemini model through the research gateway)
over annotator B's packets. Written for review; not run until the authors approve the spend.

One call per packet file: the system message is GUIDELINES.md plus a fixed output instruction; the user
message is the packet file, unchanged. The reply's JSON lines go to <out>/<packet name>. validate_labels.py checks
the file; if it fails, the same file goes back once with the validator's messages only, as for an agent annotator.
The model ID is the one in the request config, recorded with every call (the session setting, not
the model's own report). The log keeps each request's model, file, attempt, the raw reply, usage and the served
model and provider, never the key. The key is read from --key-file into the request header and never printed.
Temperature 0. --dry-run builds every request and prints sizes without any network call.

Usage:
  python3 gemini_runner.py --packets <annotator-B/packets> --guidelines <GUIDELINES.md> --out <annotator-B/labels>
                           --log <log dir> --model <gateway model id> --key-file <0600 file>
                           [--base-url http://127.0.0.1:8787/v1] [--provider-routing '<json>'] [--dry-run]
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_labels import main as validate  # noqa: E402

OUTPUT_INSTRUCTION = """

## Output for this run

You will receive one packet file: one JSON object per line. Label every item under the guidelines above.
Return only the label lines, one JSON object per line, in the packet's order, with the fields of section 5:
item_id, label, facts_conveyed, facts_narrowed, existence_type, quote, confidence, note.
No other text, no code fences, no header line."""

ap = argparse.ArgumentParser()
ap.add_argument("--packets", required=True)
ap.add_argument("--guidelines", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--log", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--key-file", required=True)
ap.add_argument("--base-url", default="http://127.0.0.1:8787/v1")
ap.add_argument("--provider-routing")
ap.add_argument("--max-output-tokens", type=int, default=32000)
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

system = open(args.guidelines, encoding="utf-8").read() + OUTPUT_INSTRUCTION
files = sorted(f for f in os.listdir(args.packets) if f.endswith(".jsonl"))
os.makedirs(args.out, exist_ok=True)
os.makedirs(args.log, exist_ok=True)


def call(messages):
    body = {"model": args.model, "messages": messages, "temperature": 0, "max_tokens": args.max_output_tokens}
    if args.provider_routing:
        body["provider"] = json.loads(args.provider_routing)
    req = urllib.request.Request(f"{args.base_url}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + open(args.key_file).read().strip()})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                raise
            time.sleep(10 * (attempt + 1))
            print(f"retrying after {type(e).__name__}", file=sys.stderr)


def label_lines(text):
    rows = []
    for line in (text or "").splitlines():
        line = line.strip().strip("`")
        if line.startswith("{") and line.endswith("}"):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if "item_id" in row:
                rows.append(row)
    return rows


summary = []
for name in files:
    packet = open(os.path.join(args.packets, name), encoding="utf-8").read()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": packet}]
    if args.dry_run:
        summary.append({"file": name, "items": packet.count("\n"), "system_chars": len(system), "packet_chars": len(packet)})
        continue
    out_path = os.path.join(args.out, name)
    for attempt in (1, 2):
        resp = call(messages)
        text = resp["choices"][0]["message"].get("content") or ""
        rows = label_lines(text)
        with open(out_path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        problems = validate(os.path.join(args.packets, name), out_path)
        with open(os.path.join(args.log, f"{name}.attempt{attempt}.json"), "w", encoding="utf-8") as fh:
            json.dump({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "file": name, "attempt": attempt,
                       "requested_model": args.model, "served_model": resp.get("model"), "provider": resp.get("provider"),
                       "usage": resp.get("usage"), "reply": text, "problems": problems}, fh, ensure_ascii=False, indent=1)
        summary.append({"file": name, "attempt": attempt, "lines": len(rows), "problems": len(problems)})
        if not problems:
            break
        messages = messages + [{"role": "assistant", "content": text},
                               {"role": "user", "content": "The validator found these problems:\n" + "\n".join(problems) +
                                "\nReturn the full corrected label file for this packet, one JSON line per item."}]
print(json.dumps({"model": args.model, "files": summary}, indent=1))
