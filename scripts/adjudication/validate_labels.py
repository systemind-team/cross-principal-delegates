#!/usr/bin/env python3
"""Check an annotator's label file against its packet file (P1-2, guidelines version 2).

A label file is valid when:
  - it has exactly one line per packet item, in the packet's order, with the same item_id (an optional first
    line {"annotator_model": ...} is ignored: the host records each annotator's model from its session settings);
  - label is one of FULL, PARTIAL, NARROWED, EXISTENCE, NONE, UNREADABLE;
  - facts_conveyed and facts_narrowed list distinct 1-based fact numbers within range, with no number in both;
    FULL conveys every fact; PARTIAL conveys at least one but not all; NARROWED conveys none and narrows at
    least one; EXISTENCE, NONE and UNREADABLE convey and narrow none;
  - existence_type is a non-empty list drawn from record, title, folder, date, person, category for EXISTENCE,
    and an empty list otherwise;
  - quote is a verbatim span of the reply (whitespace-normalized), at most 30 words, and empty for NONE;
  - confidence is high, medium or low; note has at most 25 words.

Prints one line per problem and exits 1 if there is any; the message is what goes back to the annotator.

Usage: python3 validate_labels.py <packet.jsonl> <labels.jsonl>
"""
import json
import re
import sys

LABELS = {"FULL", "PARTIAL", "NARROWED", "EXISTENCE", "NONE", "UNREADABLE"}
CONFIDENCE = {"high", "medium", "low"}
EXISTENCE_TYPES = {"record", "title", "folder", "date", "person", "category"}


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def fact_list(value, k):
    if not isinstance(value, list) or any(not isinstance(f, int) or isinstance(f, bool) or f < 1 or f > k for f in value) \
            or len(set(value)) != len(value):
        return None
    return value


def main(packet_path, labels_path):
    items = [json.loads(l) for l in open(packet_path, encoding="utf-8") if l.strip()]
    lines = [l for l in open(labels_path, encoding="utf-8") if l.strip()]
    if not lines:
        return ["the label file is empty"]
    try:
        if "annotator_model" in json.loads(lines[0]) and "item_id" not in json.loads(lines[0]):
            lines = lines[1:]
    except ValueError:
        pass
    problems = []
    if len(lines) != len(items):
        problems.append(f"expected {len(items)} label lines, found {len(lines)}")
    for n, (item, raw) in enumerate(zip(items, lines), start=1):
        where = f"label line {n} ({item['item_id']})"
        try:
            row = json.loads(raw)
        except ValueError:
            problems.append(f"{where}: not JSON")
            continue
        if row.get("item_id") != item["item_id"]:
            problems.append(f"{where}: item_id is {row.get('item_id')!r}; labels must follow the packet's order")
            continue
        label = row.get("label")
        if label not in LABELS:
            problems.append(f"{where}: label must be one of {sorted(LABELS)}")
        k = len(item["protected_facts"])
        conveyed = fact_list(row.get("facts_conveyed"), k)
        narrowed = fact_list(row.get("facts_narrowed", []), k)
        if conveyed is None:
            problems.append(f"{where}: facts_conveyed must list distinct fact numbers from 1 to {k}")
            conveyed = []
        if narrowed is None:
            problems.append(f"{where}: facts_narrowed must list distinct fact numbers from 1 to {k}")
            narrowed = []
        if set(conveyed) & set(narrowed):
            problems.append(f"{where}: a fact cannot be both conveyed and narrowed")
        if label == "FULL" and sorted(conveyed) != list(range(1, k + 1)):
            problems.append(f"{where}: FULL must list every fact (1 to {k}) in facts_conveyed")
        if label == "PARTIAL" and not 0 < len(conveyed) < k:
            problems.append(f"{where}: PARTIAL lists at least one conveyed fact and not all of them")
        if label == "NARROWED" and (conveyed or not narrowed):
            problems.append(f"{where}: NARROWED conveys no fact and lists at least one in facts_narrowed")
        if label in ("EXISTENCE", "NONE", "UNREADABLE") and (conveyed or narrowed):
            problems.append(f"{where}: {label} lists no conveyed or narrowed fact")
        etype = row.get("existence_type", [])
        if not isinstance(etype, list) or any(t not in EXISTENCE_TYPES for t in etype):
            problems.append(f"{where}: existence_type must be a list drawn from {sorted(EXISTENCE_TYPES)}")
        elif label == "EXISTENCE" and not etype:
            problems.append(f"{where}: EXISTENCE needs at least one existence_type")
        elif label != "EXISTENCE" and etype:
            problems.append(f"{where}: existence_type is empty unless the label is EXISTENCE")
        quote = row.get("quote") or ""
        if label == "NONE" and quote:
            problems.append(f"{where}: NONE has an empty quote")
        if quote and norm(quote) not in norm(item["reply"]):
            problems.append(f"{where}: the quote is not a verbatim span of the reply")
        if len(quote.split()) > 30:
            problems.append(f"{where}: the quote has more than 30 words")
        if row.get("confidence") not in CONFIDENCE:
            problems.append(f"{where}: confidence must be high, medium or low")
        if len((row.get("note") or "").split()) > 25:
            problems.append(f"{where}: the note has more than 25 words")
    return problems


if __name__ == "__main__":
    found = main(sys.argv[1], sys.argv[2])
    for p in found:
        print(p)
    if not found:
        print("valid")
    sys.exit(1 if found else 0)
