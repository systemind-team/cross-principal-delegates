#!/usr/bin/env python3
"""Compare kernel K2's scripted conformance manifest with K1's, row by row and column by column.

K1 = SharedOS c74461c (the paper's Tables 8, 9 and 12; evidence/kernel_conformance.source.json).
K2 = SharedOS 3aa07e3 (the kernel every experiment loaded; evidence/v3.14/conformance-k2/).

Columns are matched by id, except K2's in-process column: K2 calls it "sharedos-embedded" (label
"Standard"), and it is the SharedOS executor driving the scripted adversary, which K1 calls
"adversary-embedded" (label "Adversary"). K1's "model-scripted" column (label "Standard": the model
driver replaying model-shaped replies) has no K2 counterpart.

Usage: python3 compare_k1_k2.py <K1 manifest> <K2 manifest> > comparison.json
"""
import collections
import json
import sys

K1 = json.load(open(sys.argv[1]))
K2 = json.load(open(sys.argv[2]))
COLUMN_MAP = {  # K2 column id -> K1 column id
    "sharedos-embedded": "adversary-embedded",
    "codex-scripted": "codex-scripted",
    "claude-code-scripted": "claude-code-scripted",
    "deepseek-scripted": "deepseek-scripted",
    "pi-scripted": "pi-scripted",
}
FIELDS = ("status", "refusedBy", "reasonCodes", "declared", "attempted", "notApplicable", "recordUsable", "turns")


def index(manifest):
    return {(r["caseId"], r["conditionId"]): r for r in manifest["rows"]}


def cell(row, column):
    if row is None:
        return None
    for c in row["cells"]:
        if c["columnId"] == column:
            return {f: c.get(f) for f in FIELDS}
    return None


def totals(manifest):
    out = collections.defaultdict(collections.Counter)
    for r in manifest["rows"]:
        for c in r["cells"]:
            out[c["columnId"]][c["status"]] += 1
    return {k: dict(v) for k, v in out.items()}


r1, r2 = index(K1), index(K2)
keys = sorted(set(r1) | set(r2), key=lambda k: (k not in r2, k))
rows = []
agree = collections.Counter()
differ = []
for key in keys:
    a, b = r1.get(key), r2.get(key)
    entry = {"caseId": key[0], "conditionId": key[1], "inK1": a is not None, "inK2": b is not None,
             "kind": (b or a).get("kind"), "invariant": (b or a).get("invariant"),
             "expectedOutcomeK1": a.get("expectedOutcome") if a else None,
             "expectedOutcomeK2": b.get("expectedOutcome") if b else None,
             "columns": {}}
    for k2col, k1col in COLUMN_MAP.items():
        c1, c2 = cell(a, k1col), cell(b, k2col)
        same_status = c1 is not None and c2 is not None and c1["status"] == c2["status"]
        same_reason = same_status and sorted(c1["reasonCodes"] or []) == sorted(c2["reasonCodes"] or [])
        entry["columns"][k2col] = {"K1column": k1col, "K1": c1, "K2": c2,
                                   "sameStatus": same_status, "sameReasonCodes": same_reason}
        if a is not None and b is not None:
            agree[(k2col, "status")] += same_status
            agree[(k2col, "reasonCodes")] += same_reason
            if not (same_status and same_reason):
                differ.append({"row": list(key), "column": k2col, "K1": c1, "K2": c2})
    entry["K1only_model_scripted"] = cell(a, "model-scripted")
    rows.append(entry)

common = [k for k in keys if k in r1 and k in r2]
report = {
    "K1": {"manifestVersion": K1.get("version"), "judgeVersion": K1.get("judgeVersion"),
           "caseSetHash": K1.get("caseSetHash"), "worldSetHash": K1.get("worldSetHash"),
           "columns": [c["id"] for c in K1["columns"]], "rows": len(r1), "statusTotals": totals(K1)},
    "K2": {"manifestVersion": K2.get("version"), "judgeVersion": K2.get("judgeVersion"),
           "caseSetHash": K2.get("caseSetHash"), "worldSetHash": K2.get("worldSetHash"),
           "columns": [c["id"] for c in K2["columns"]], "rows": len(r2), "statusTotals": totals(K2)},
    "columnMap": COLUMN_MAP,
    "rowsCommon": len(common),
    "rowsOnlyInK1": [list(k) for k in keys if k in r1 and k not in r2],
    "rowsOnlyInK2": [list(k) for k in keys if k in r2 and k not in r1],
    "agreementOnCommonRows": {f"{col}/{what}": f"{n}/{len(common)}" for (col, what), n in sorted(agree.items())},
    "differencesOnCommonRows": differ,
    "rows": rows,
}
json.dump(report, sys.stdout, indent=1)
print()
