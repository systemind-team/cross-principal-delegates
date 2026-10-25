#!/usr/bin/env python3
"""Add the told ladder's policies to a SharedEval checkout at 8081e7e (run from its root).

The multi-turn ladder's responder is never told who asks. The told ladder puts the same
runtime-verified head that PAIR I and D2R_ID_* use in front of each ladder rung, so the only change
from the ladder is that the responder now reads who is asking:
  D0_ID_Rk = head alone                       (PAIR I's D0 form)
  D1_ID_Rk = head + separator + P1 (ladder D1, generic caution, byte-exact)
  D2_ID_Rk = head + separator + P2 (ladder D2, category policy, byte-exact)
The head for Rk is copied byte-for-byte from policies/pact-pair-identified/rk (D2R_ID_Rk).

Writes the nine policy sources and workspace assets, registers them, and teaches the loader the
names: each maps to its rung's category dial and must be run by the requester it names.
"""
import copy
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(".")
WS = ROOT / "dataset/shared-eval/workspaces/v1"
POL = WS / "policies"
REQS = ("r1", "r2", "r3")
SEP = "\n---\n\n"

bodies = {n: (POL / f"pact-pair-defense/d{n}/1.0.0/POLICY.md").read_bytes().decode() for n in (0, 1, 2)}
assert bodies[0] == "" and len(bodies[1].encode()) == 128 and len(bodies[2].encode()) == 2278

registry = json.loads((WS / "registry.json").read_text())
template = next(a for a in registry["assets"] if a["id"] == "policies/pact-pair-identified/r1")
names = []
for r in REQS:
    identified = (POL / f"pact-pair-identified/{r}/1.0.0/POLICY.md").read_bytes().decode()
    head = identified.split(SEP, 1)[0].rstrip("\n") + "\n"
    assert "## Verified caller" in head and "You are talking to" in head
    for n in (0, 1, 2):
        text = head if n == 0 else head + SEP + bodies[n]
        name = f"D{n}_ID_{r.upper()}"
        names.append(name)
        raw = text.encode()
        src = ROOT / f"dataset/pact-pair/policies/{name}.md"
        asset_id = f"policies/pact-pair-told/d{n}-{r}"
        dst = WS / asset_id / "1.0.0/POLICY.md"
        src.write_bytes(raw)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        entry = copy.deepcopy(template)
        entry.update({"id": asset_id, "sourcePath": f"policies/pact-pair-told/d{n}-{r}/1.0.0/POLICY.md",
                      "aliases": [f"pact:dataset/pact-pair/policies/{name}.md"],
                      "byteLength": len(raw), "sha256": digest,
                      "provenance": {"kind": "exact", "sourcePath": f"dataset/pact-pair/policies/{name}.md",
                                     "sourceSha256": digest}})
        registry["assets"] = [a for a in registry["assets"] if a["id"] != asset_id] + [entry]
# The registry must list assets in stable lexical id@version order.
registry["assets"].sort(key=lambda a: f"{a['id']}@{a['version']}")
(WS / "registry.json").write_text(json.dumps(registry, indent=2) + "\n")


def patch(path, old, new):
    p = ROOT / path
    s = p.read_text()
    assert s.count(old) == 1, (path, old[:60], s.count(old))
    p.write_text(s.replace(old, new))


patch("src/suites/pact-pair/task-loader.ts",
      "  'D2R_ID_R3',\n",
      "  'D2R_ID_R3',\n"
      "  // The multi-turn ladder's rungs (D0, D1, D2) behind the same runtime-verified\n"
      "  // caller head: the told ladder. Each names one requester.\n"
      + "".join(f"  '{n}',\n" for n in names))
patch("src/suites/pact-pair/task-loader.ts",
      "  if (policy === 'D5_SUBMITTED') return 5;\n",
      "  if (policy === 'D5_SUBMITTED') return 5;\n"
      "  const told = /^D([012])_ID_R[0-3]$/.exec(policy);\n"
      "  if (told) return Number(told[1]) as 0 | 1 | 2;\n")
patch("src/runner/v1/sharedeval-production.ts",
      "  if (!policy.startsWith(IDENTIFIED_POLICY_PREFIX_V1)) return;\n",
      "  const told = /^D[012]_ID_(R[0-3])$/.exec(policy);\n"
      "  if (told && told[1] !== requester) {\n"
      "    throw new Error(`Policy ${policy} names requester ${told[1]}, but the run selects requester ${requester}`);\n"
      "  }\n"
      "  if (!policy.startsWith(IDENTIFIED_POLICY_PREFIX_V1)) return;\n")
patch("src/runner/v1/sharedeval-production.ts",
      "function policyAssetId(policy: PactPairPolicyV1): string {\n",
      "function policyAssetId(policy: PactPairPolicyV1): string {\n"
      "  const told = /^D([012])_ID_(R[0-3])$/.exec(policy);\n"
      "  if (told) return `policies/pact-pair-told/d${told[1]}-${told[2]!.toLowerCase()}`;\n")
print("wrote", len(names), "told policies:", ", ".join(names))
