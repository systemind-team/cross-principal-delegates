#!/usr/bin/env python3
"""Kernel check: what produced the frozen originals, read-only on the experiment VM.

Run on the VM (python3, no third-party modules; yaml configs are parsed by a tiny reader for the flat
subset these files use, and the raw text's sha256 is kept). Prints JSON on stdout. Reads no env or key file.

PAIR I  the four DeepSeek V4.1 Flash cells of the comparison (ds41-d0-r1, ds41-d0-r3, ds41-d2-r1, ds41-d2-r3):
        config.yaml (sha256 and text, which names no secret: apiKeyEnv is a variable name) and the image
        provenance fields (imageRef, imageDigest, startedAt, finishedAt, cliExitCode, egress allowlist).
        Also the xC cells' requester block, to record that xC (SharedEval 0735564) is a GLM-requester variant.
PAIR II the ladder grid's DeepSeek configs (t3simple S4-DS-<rung>-<requester>-<group>) for D0/D2 x R1/R3 x
        the 20 sampled groups, and the header ladder's same-route D2 control (pair2told T3-CTRL-D2-*), with
        the Azure endpoint host replaced by <azure-endpoint>.
Usage: original_configs.py <samples.json>
"""
import hashlib
import json
import os
import re
import sys

E1 = "<vm>/work/v41-grid-out"
T3S = "<vm>/runs/t3simple"
TOLD = "<vm>/runs/pair2told"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def redact(text):
    return re.sub(r"https://[a-z0-9-]+\.cognitiveservices\.azure\.com", "https://<azure-endpoint>", text)


def pair1():
    out = {}
    for cell in ("ds41-d0-r1", "ds41-d0-r3", "ds41-d2-r1", "ds41-d2-r3", "xC-d0-r1"):
        top = os.path.join(E1, f"{cell}-rep1")
        runs = [d for d in os.listdir(top) if os.path.isdir(os.path.join(top, d))]
        assert len(runs) == 1, (cell, runs)
        d = os.path.join(top, runs[0])
        raw = open(os.path.join(d, "config.yaml"), "rb").read()
        prov = json.load(open(os.path.join(d, "cell-provenance.json")))
        out[cell] = {
            "run_id": prov["runId"], "done_marker": os.path.exists(os.path.join(top, ".done")),
            "config_sha256": sha(raw), "config_text": raw.decode(),
            "imageRef": prov["imageRef"], "imageDigest": prov["imageDigest"],
            "allowlistedEgress": prov["allowlistedEgress"], "configDigest": prov["configDigest"],
            "startedAt": prov["startedAt"], "finishedAt": prov["finishedAt"], "cliExitCode": prov["cliExitCode"],
        }
    return out


def pair2(samples):
    groups = samples["pair2"]["groups"]
    ladder, told = {}, {}
    for g in groups:
        for rung in ("D0", "D2"):
            for req in ("R1", "R3"):
                rid = f"S4-DS-{rung}-{req}-{g}"
                raw = open(f"{T3S}/cfg/{rid}.json", "rb").read()
                c = json.loads(redact(raw.decode()))
                assert c["benchmark"]["tasks"]["ids"] == groups[g], rid
                ladder[rid] = {"sha256": sha(raw), "model": c["model"], "workflow": c["workflow"],
                               "benchmark": c["benchmark"], "budget": c.get("budget")}
        for req in ("R1", "R3"):
            rid = f"T3-CTRL-D2-{req}-{g}"
            raw = open(f"{TOLD}/cfg/{rid}.json", "rb").read()
            c = json.loads(raw)
            assert c["benchmark"]["tasks"]["ids"] == groups[g], rid
            told[rid] = {"sha256": sha(raw), "model": c["model"], "workflow": c["workflow"],
                         "benchmark": c["benchmark"], "budget": c.get("budget")}
    # every config of a block shares one model/workflow/budget; report the distinct values
    def distinct(block, key):
        return sorted({json.dumps(v[key], sort_keys=True) for v in block.values()})
    return {
        "ladder_configs": ladder, "told_ctrl_configs": told,
        "ladder_distinct": {k: [json.loads(x) for x in distinct(ladder, k)] for k in ("model", "workflow", "budget")},
        "told_distinct": {k: [json.loads(x) for x in distinct(told, k)] for k in ("model", "workflow", "budget")},
        "ladder_manifest_sha256": sha(open(f"{T3S}/MANIFEST.json", "rb").read()),
    }


if __name__ == "__main__":
    samples = json.load(open(sys.argv[1]))
    print(json.dumps({"pair1": pair1(), "pair2": pair2(samples)}, indent=1, sort_keys=True))
