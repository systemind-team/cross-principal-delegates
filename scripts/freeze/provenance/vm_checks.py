#!/usr/bin/env python3
"""VM half of the provenance checks. Read-only; fed over stdin so nothing is written on the VM:

    ssh <host> 'nice -n 19 python3 -' < scripts/freeze/provenance/vm_checks.py > vm.json

collect.py runs this itself. Prints one compact JSON document.

What it opens, and nothing else:
  * git objects of the clones under <vm>/repos (rev-parse, cat-file, show of one source file),
    with GIT_OPTIONAL_LOCKS=0 so no index is refreshed;
  * run launch logs (<lane>/logs/*.log): only the "sourceRevision" the CLI prints, within the first 4 KiB;
  * per-run .sharedeval-file-workflow/binding.json: only binding.sharedOs.sharedOsRevision and
    binding.sharedOs.sharedOsRuntimeDigest; per-run run.json: only backend.kernelRevision and
    backend.kernelRuntimeDigest;
  * the names (not contents) of <lane>/cfg/*.json, which list a lane's sessions;
  * <vm>/work/v41-grid-out/*/*/cell-provenance.json (PAIR I OpenRouter cells): only imageRef and
    imageDigest; and whether <vm>/luna (PAIR I Azure cells) is readable at all;
  * `docker image ls` names, to see whether any SharedEval experiment image is on the VM.
No env file, key file, gateway folder or config content is read.
"""
import collections
import glob
import json
import os
import re
import subprocess

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
ROOT = "<vm>"
REPOS = f"{ROOT}/repos"
RUNS = f"{ROOT}/runs"
SE_TARGETS = ["58829feb1728", "0735564b0c31", "79b52cf8b76b", "40f4f01", "5aaa7f1", "e20062e", "5db4182",
              "26dd392", "8081e7e78e0e", "4565add", "d44e478", "6773638"]
OS_TARGETS = ["c74461c", "5392148", "3aa07e3"]
LOADER = "src/execution/sharedos/v1/load-sharedos.ts"
PIN_PATTERNS = {
    "SHAREDOS_RUNTIME_PACKAGES_V1": re.compile(r"export const SHAREDOS_RUNTIME_PACKAGES_V1 = \["),
    "SHAREDOS_VERIFIED_REVISION_V1": re.compile(r"export const SHAREDOS_VERIFIED_REVISION_V1 ="),
    "SHAREDOS_VERIFIED_RUNTIME_DIGEST_V1": re.compile(r"export const SHAREDOS_VERIFIED_RUNTIME_DIGEST_V1 ="),
}
REV = re.compile(r'"sourceRevision":\s*"([0-9a-f]{40})"')


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def resolve(repo, short):
    rc, out = git(repo, "rev-parse", "--verify", "--quiet", short + "^{commit}")
    return out if rc == 0 else None


def pins(repo, rev):
    """Declared pin, digest and package list in load-sharedos.ts at rev, with 1-based line numbers."""
    rc, text = git(repo, "show", f"{rev}:{LOADER}")
    if rc != 0:
        return None
    lines = text.split("\n")
    out = {}
    for name, pat in PIN_PATTERNS.items():
        for i, line in enumerate(lines):
            if pat.search(line):
                if name == "SHAREDOS_RUNTIME_PACKAGES_V1":
                    j = i
                    while "] as const" not in lines[j]:
                        j += 1
                    out[name] = {"lines": f"{i + 1}-{j + 1}",
                                 "value": re.findall(r"'([a-z]+)'", "\n".join(lines[i:j + 1]))}
                else:
                    m = re.search(r"'([0-9a-f]{40,64})'", lines[i] + lines[i + 1])
                    out[name] = {"lines": f"{i + 1}-{i + 2}", "value": m.group(1) if m else None}
                break
    rc, script = git(repo, "show", f"{rev}:scripts/experiments/build-image.sh")
    if rc == 0:
        for i, line in enumerate(script.split("\n")):
            m = re.match(r'SHAREDOS_PINNED_REVISION="([0-9a-f]{40})"', line)
            if m:
                out["build-image.sh SHAREDOS_PINNED_REVISION"] = {"lines": str(i + 1), "value": m.group(1)}
    rc, ci = git(repo, "show", f"{rev}:.github/workflows/ci.yml")
    if rc == 0:
        for i, line in enumerate(ci.split("\n")):
            m = re.match(r"\s*SHAREDOS_PIN:\s*([0-9a-f]{40})", line)
            if m:
                out["ci.yml SHAREDOS_PIN"] = {"lines": str(i + 1), "value": m.group(1)}
    return out


def commit_meta(repo, rev):
    rc, out = git(repo, "log", "-1", "--format=%H%x00%T%x00%P%x00%ad%x00%s", "--date=iso-strict", rev)
    if rc != 0:
        return None
    h, t, p, d, s = out.split("\x00")
    return {"commit": h, "tree": t, "parents": p.split(), "date": d, "subject": s}


out = {"repos": {}}
for repo in sorted(glob.glob(f"{REPOS}/*")):
    if not os.path.exists(f"{repo}/.git"):
        continue
    name = os.path.basename(repo)
    targets = OS_TARGETS if name.startswith("SharedOS") else SE_TARGETS
    rc, head = git(repo, "rev-parse", "HEAD")
    rc, dirty = git(repo, "status", "--porcelain", "--untracked-files=no")
    if not (name.startswith("SharedOS") or name.startswith("SharedEval") or name.startswith("SE-")):
        continue
    out["repos"][name] = {"head": head, "tracked_dirty": bool(dirty),
                          "resolved": {t: resolve(repo, t) for t in targets}}

se_a1, se_told, se_net = f"{REPOS}/SharedEval-a1", f"{REPOS}/SharedEval-told", f"{REPOS}/SE-net-e1"
out["commits"] = {
    "8081e7e": commit_meta(se_a1, "8081e7e"),
    "4565add": commit_meta(se_told, "4565add"),
    "d44e478": commit_meta(se_net, "d44e478"),
    "c74461c": commit_meta(f"{REPOS}/SharedOS", "c74461c"),
    "5392148": commit_meta(f"{REPOS}/SharedOS", "5392148"),
    "3aa07e3": commit_meta(f"{REPOS}/SharedOS", "3aa07e3"),
}
out["pins"] = {}
for short, repo in [("58829fe", se_a1), ("0735564", se_a1), ("e20062e", se_a1), ("5db4182", se_a1),
                    ("26dd392", se_a1), ("8081e7e", se_a1), ("4565add", se_told), ("d44e478", se_net)]:
    out["pins"][short] = {"repo": repo, "commit": resolve(repo, short), "load_sharedos": pins(repo, short)}
rc, k2head = git(f"{REPOS}/SharedOS-3aa07e3", "rev-parse", "HEAD")
rc, k2dirty = git(f"{REPOS}/SharedOS-3aa07e3", "status", "--porcelain", "--untracked-files=no")
out["sharedos_k2_checkout"] = {"path": f"{REPOS}/SharedOS-3aa07e3", "head": k2head, "tracked_dirty": bool(k2dirty),
                               "dist_index_js_present": {p: os.path.exists(f"{REPOS}/SharedOS-3aa07e3/packages/{p}/dist/index.js")
                                                         for p in ("contracts", "core", "os", "runtime")}}


def launch_revisions(lane, rid_glob="*"):
    """{run id: [(mtime, log name, sourceRevision or None), ...]} sorted by mtime then name."""
    logs = collections.defaultdict(list)
    for lg in glob.glob(f"{RUNS}/{lane}/logs/{rid_glob}.log"):
        base = os.path.basename(lg)[:-len(".log")]
        rid = base.rsplit(".", 1)[0] if "." in base else base
        with open(lg, errors="replace") as fh:
            m = REV.search(fh.read(4096))
        logs[rid].append((os.path.getmtime(lg), os.path.basename(lg), m.group(1) if m else None))
    return {k: sorted(v) for k, v in logs.items()}


def recorded(lane):
    """Per-run SharedOS revision/digest the harness bound at run time, and run.json's kernel fields."""
    bind = collections.Counter()
    kern = collections.Counter()
    for f in glob.glob(f"{RUNS}/{lane}/cfg/runs/*/multi/.sharedeval-file-workflow/binding.json") + \
            glob.glob(f"{RUNS}/{lane}/cfg/runs/*/*/multi/.sharedeval-file-workflow/binding.json"):
        try:
            b = json.load(open(f)).get("binding", {}).get("sharedOs", {})
        except Exception:
            bind[("unreadable", "unreadable")] += 1
            continue
        bind[(b.get("sharedOsRevision"), b.get("sharedOsRuntimeDigest"))] += 1
    for f in glob.glob(f"{RUNS}/{lane}/cfg/runs/*/multi/run.json") + glob.glob(f"{RUNS}/{lane}/cfg/runs/*/*/multi/run.json"):
        try:
            b = json.load(open(f)).get("backend", {}) or {}
        except Exception:
            kern[("unreadable", "unreadable")] += 1
            continue
        kern[(b.get("kernelRevision"), b.get("kernelRuntimeDigest"))] += 1
    fmt = lambda c: [{"revision": k[0], "runtime_digest": k[1], "runs": n} for k, n in sorted(c.items(), key=lambda x: -x[1])]
    return {"binding_sharedOs": fmt(bind), "run_json_backend_kernel": fmt(kern)}


# ---- E2: probing grid and packing study, per session ------------------------------------------------------
SESSION = {"grid600": re.compile(r"^G6-(R\d)-(r\d)-(g\d{3})$"), "pack1": re.compile(r"^PK1-(r\d)-(g\d{3})$"),
           "pack10": re.compile(r"^PK10-(r\d)-(g\d{3})$")}
out["e2"] = {}
for study, pat in SESSION.items():
    sessions = sorted(os.path.basename(p)[:-5] for p in glob.glob(f"{RUNS}/{study}/cfg/*.json")
                      if pat.match(os.path.basename(p)[:-5]))
    logs = launch_revisions(study)
    per = collections.Counter()
    per_req = collections.defaultdict(collections.Counter)
    mixed, missing, no_logs = [], [], []
    rows = {}
    kernel_field = collections.Counter()   # (launch revision, run.json carries backend.kernelRevision)
    for s in sessions:
        lg = logs.get(s, [])
        if not lg:
            no_logs.append(s)
            rev = None
        else:
            rev = lg[-1][2]
            revs = {x[2] for x in lg if x[2]}
            if len(revs) > 1:
                mixed.append({"session": s, "launches": [[x[1], x[2]] for x in lg]})
            if rev is None:
                missing.append({"session": s, "launches": [[x[1], x[2]] for x in lg]})
        per[rev] += 1
        req = pat.match(s).group(1) if study == "grid600" else "R1"
        per_req[req][rev] += 1
        rows[s] = rev[:7] if rev else None
        try:
            has_kernel = bool((json.load(open(f"{RUNS}/{study}/cfg/runs/{s}/multi/run.json")).get("backend") or {}).get("kernelRevision"))
        except Exception:
            has_kernel = "no run.json"
        kernel_field[(rev[:7] if rev else None, has_kernel)] += 1
        if rev is None and has_kernel is True:
            missing[-1]["run_json_has_kernelRevision"] = True
    unmatched = sorted(k for k in logs if k not in set(sessions))
    out["e2"][study] = {
        "sessions": len(sessions), "rule": "sourceRevision of the session's last launch log by mtime",
        "by_revision": {str(k): v for k, v in sorted(per.items(), key=lambda x: -x[1])},
        "by_requester": {r: {str(k): v for k, v in sorted(c.items(), key=lambda x: -x[1])} for r, c in sorted(per_req.items())},
        "sessions_whose_launches_disagree": mixed, "sessions_without_a_revision": missing,
        "sessions_without_logs": no_logs, "log_ids_not_a_session": unmatched,
        "launch_revision_vs_run_json_kernelRevision": [{"launch_revision": k[0], "run_json_has_kernelRevision": k[1], "sessions": n}
                                                       for k, n in sorted(kernel_field.items(), key=lambda x: -x[1])],
        "session_revision_7": rows, "recorded_at_run_time": recorded(study),
    }

# ---- every other lane the paper's studies ran in: what the runs bound ---------------------------------------
out["lanes"] = {}
for lane in ["t3full", "t3simple", "pair2id2", "pair2told", "net-or-ds", "net-or-glm"]:
    logs = launch_revisions(lane)
    last = collections.Counter(v[-1][2] for v in logs.values())
    every = collections.Counter(x[2] for v in logs.values() for x in v)
    # A log that prints no sourceRevision: is it a short log carrying an error message (a failed launch)?
    failed = collections.Counter()
    for v in logs.values():
        for _mtime, name, rev in v:
            if rev is None:
                p = f"{RUNS}/{lane}/logs/{name}"
                with open(p, errors="replace") as fh:
                    text = fh.read(65536)
                failed["short_with_error_text" if os.path.getsize(p) < 4096 and re.search(r"error|Error|ERR", text)
                       else "other"] += 1
    out["lanes"][lane] = {"run_ids_with_logs": len(logs),
                          "last_launch_sourceRevision": {str(k): n for k, n in sorted(last.items(), key=lambda x: -x[1])},
                          "every_log_sourceRevision": {str(k): n for k, n in sorted(every.items(), key=lambda x: -x[1])},
                          "logs_without_revision": dict(failed),
                          "recorded_at_run_time": recorded(lane)}

# ---- E1: PAIR I cells -------------------------------------------------------------------------------------
hx = "<vm>/work/v41-grid-out"
cells = collections.defaultdict(list)
for f in sorted(glob.glob(f"{hx}/*/*/cell-provenance.json")):
    d = json.load(open(f))
    cells[(d.get("imageRef"), d.get("imageDigest"))].append(f[len(hx) + 1:].split("/")[0])
out["e1"] = {
    "openrouter_cells_dir": hx,
    "images": [{"imageRef": k[0], "imageDigest": k[1], "cells": len(v),
                "voided_cells": sorted(c for c in v if ".bad-" in c)} for k, v in sorted(cells.items(), key=lambda x: -len(x[1]))],
    "azure_cells_dir_readable": os.access("<vm>/luna", os.R_OK | os.X_OK),
    "openrouter_task_dirs_readable": all(os.access(p, os.R_OK | os.X_OK)
                                         for p in glob.glob(f"{hx}/*/*/runs/*/single/*")[:50]) if glob.glob(f"{hx}/*/*/runs/*/single/*") else None,
}
p = subprocess.run(["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True)
out["e1"]["docker_sharedeval_images_on_vm"] = sorted(l for l in p.stdout.split() if "sharedeval" in l) if p.returncode == 0 else f"docker rc {p.returncode}"
print(json.dumps(out, sort_keys=True, separators=(",", ":")))
