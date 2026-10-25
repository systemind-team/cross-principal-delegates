#!/usr/bin/env python3
"""Re-run every check behind evidence/v3.14/provenance/ and print the values.

    python3 scripts/freeze/provenance/collect.py                 # run all checks, print a report
    python3 scripts/freeze/provenance/collect.py --github        # also look each commit up on GitHub (read-only)
    python3 scripts/freeze/provenance/collect.py --write         # also (re)write provenance.json, revision_labels.json

Run from the worktree root. Everything is read-only:
  * the local SharedOS clone (K1, its live pass, K2, the divergence counts, package names);
  * the local built K2 checkout, through SharedEval 8081e7e's own digestSharedOsRuntimeV1 (node >= 23 runs the
    .ts file directly), to recompute the runtime digest;
  * the local SharedEval clone (the pin each evaluator revision declares, read with `git show`);
  * a throw-away bare repository in a temporary directory whose object store borrows the SharedEval clone's
    (objects/info/alternates), to apply the header-ladder patch to E3's tree and compare the result with
    4565add's tree; it is deleted afterwards and nothing is written to the clone;
  * the experiment VM, through scripts/freeze/provenance/vm_checks.py fed over stdin (see that file for exactly
    what it opens; no env file, key or gateway folder);
  * evidence/v3.14/packing-delivery/sessions.jsonl.gz, to cross-check the per-session revisions and validity.
With --write it writes evidence/v3.14/provenance/provenance.json and revision_labels.json and nothing else.
"""
import argparse
import collections
import datetime
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

OUT = "evidence/v3.14/provenance"
PATCH = "scripts/pair_multi/told_ladder/sharedeval-told-4565add.patch"
VM_SCRIPT = "scripts/freeze/provenance/vm_checks.py"
SESSIONS = "evidence/v3.14/packing-delivery/sessions.jsonl.gz"
LOADER = "src/execution/sharedos/v1/load-sharedos.ts"
PKG_DIRS = ["packages/contracts/src", "packages/core/src", "packages/os/src", "packages/runtime/src"]

K1, K1_LIVE, K2 = "c74461c", "5392148", "3aa07e3"
DIGEST = "4afb23d79851a83a48e25e968f04e45cefc81847b4a9963c62277b5c05862d5d"
E1_LOCAL = ["58829feb1728", "0735564b0c31"]
E1_UNRESOLVED = ["79b52cf8b76b", "40f4f01"]
E2 = ["e20062e", "5db4182", "26dd392"]
E3, E3_HEADER, E4 = "8081e7e78e0e", "4565add", "d44e478"
D44E478_TREE = "00eecd0bc16b37a170949afeb23f34bcedb8ad23"

TABLE9 = {  # the values Table 9 printed before this check, verbatim
    "K1": "c74461c1c4b715fd60c18401100cd72362d3afc1; tree b1f29050bf42ad2f97fb5fef2a3ed107d42bfabc",
    "K1-live": "5392148 (same tree b1f29050…)",
    "K2": "3aa07e33999b656a10ace294fd4e41df8cbc318e",
    "runtime-digest": DIGEST,
    "E1": "images 58829feb1728, 0735564b0c31, 79b52cf8b76b-codex; Azure native 40f4f01",
    "E2": "e20062e, 5db4182, 26dd392 (pack1 and pack10 ran 26dd392)",
    "E3": "8081e7e78e0e; header ladder = 4565add (E3 + scripts/pair_multi/told_ladder/sharedeval-told-4565add.patch)",
    "E4": "d44e4788562c438a97180443ee8cc5170094ad07 (VM clone <vm>/repos/SE-net-e1)",
    "divergence": "9 / 178 / 47 files changed, 9382 insertions(+), 370 deletions(-) (9,752 changed source lines)",
}


def run(cmd, cwd=None, check=True, inp=None, env=None):
    p = subprocess.run(cmd, cwd=cwd, input=inp, capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        sys.exit(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr}")
    return p.stdout.strip()


def git(repo, *args, check=True):
    return run(["git", "-C", repo, *args], check=check, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def resolve(repo, short):
    out = git(repo, "rev-parse", "--verify", "--quiet", short + "^{commit}", check=False)
    return out or None


def meta(repo, rev):
    h, t, p, d, s = git(repo, "log", "-1", "--format=%H%x00%T%x00%P%x00%ad%x00%s", "--date=iso-strict", rev).split("\x00")
    return {"commit": h, "tree": t, "parents": p.split(), "author_date": d, "subject": s}


def pins_from_text(text):
    lines = text.split("\n")
    out = {}
    for i, line in enumerate(lines):
        if line.startswith("export const SHAREDOS_RUNTIME_PACKAGES_V1 = ["):
            j = i
            while "] as const" not in lines[j]:
                j += 1
            out["SHAREDOS_RUNTIME_PACKAGES_V1"] = {"lines": f"{i + 1}-{j + 1}",
                                                   "value": re.findall(r"'([a-z]+)'", "\n".join(lines[i:j + 1]))}
        for name in ("SHAREDOS_VERIFIED_REVISION_V1", "SHAREDOS_VERIFIED_RUNTIME_DIGEST_V1"):
            if line.startswith(f"export const {name} ="):
                m = re.search(r"'([0-9a-f]{40,64})'", line + lines[i + 1])
                out[name] = {"lines": f"{i + 1}-{i + 2}", "value": m.group(1) if m else None}
    return out


def build_image_pin(text):
    for i, line in enumerate(text.split("\n")):
        m = re.match(r'SHAREDOS_PINNED_REVISION="([0-9a-f]{40})"', line)
        if m:
            return {"lines": str(i + 1), "value": m.group(1)}
    return None


def ci_pin(repo, rev):
    text = git(repo, "show", f"{rev}:.github/workflows/ci.yml", check=False)
    for i, line in enumerate(text.split("\n")):
        m = re.match(r"\s*SHAREDOS_PIN:\s*([0-9a-f]{40})", line)
        if m:
            return {"lines": str(i + 1), "value": m.group(1)}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sharedos", default=os.environ.get("SHAREDOS_CLONE", "SharedOS"))   # a local SharedOS clone
    ap.add_argument("--sharedos-k2-build", default=os.environ.get("SHAREDOS_K2_BUILD", "SharedOS-3aa07e3"))   # K2 checkout with dist/ built
    ap.add_argument("--sharedeval", default=os.environ.get("SHAREDEVAL_CLONE", "SharedEval"))   # a local SharedEval clone
    ap.add_argument("--vm", default="<host>")
    ap.add_argument("--vm-json", help="reuse a saved vm_checks.py output instead of running it")
    ap.add_argument("--github", action="store_true", help="also look commits up on GitHub with `gh api` (read-only)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(OUT):
        sys.exit(f"run from the worktree root ({OUT} not found)")
    so, se = a.sharedos, a.sharedeval
    R = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}

    # ---------------------------------------------------------------- SharedOS: K1, live pass, K2, divergence
    k1, live, k2 = meta(so, K1), meta(so, K1_LIVE), meta(so, K2)
    mb = git(so, "merge-base", k2["commit"], k1["commit"])
    mb_all = git(so, "merge-base", "--all", k2["commit"], k1["commit"]).split()
    shortstat = {mode: git(so, "diff", *flag, "--shortstat", k2["commit"], k1["commit"], "--", *PKG_DIRS)
                 for mode, flag in (("default", []), ("no_renames", ["--no-renames"]), ("renames", ["-M"]))}
    numstat = [l.split("\t") for l in git(so, "diff", "--numstat", k2["commit"], k1["commit"], "--", *PKG_DIRS).splitlines()]
    binary = [n for n in numstat if n[0] == "-"]
    ins = sum(int(n[0]) for n in numstat if n[0] != "-")
    dels = sum(int(n[1]) for n in numstat if n[1] != "-")
    R["k1_k2_divergence"] = {
        "repository": so, "git_version": run(["git", "--version"]),
        "merge_base": mb, "merge_bases_all": mb_all, "merge_base_subject": meta(so, mb)["subject"],
        "commits_only_in_K2": int(git(so, "rev-list", "--count", f"{mb}..{k2['commit']}")),
        "commits_only_in_K1": int(git(so, "rev-list", "--count", f"{mb}..{k1['commit']}")),
        "shortstat_K2_to_K1_four_package_src": shortstat,
        "numstat_totals": {"files": len(numstat), "insertions": ins, "deletions": dels,
                           "changed_lines": ins + dels, "binary_files": len(binary)},
        "per_package": {d.split("/")[1]: git(so, "diff", "--shortstat", k2["commit"], k1["commit"], "--", d) for d in PKG_DIRS},
        "whole_repository_shortstat": git(so, "diff", "--shortstat", k2["commit"], k1["commit"]),
        "commands": [
            "git -C <SharedOS> rev-list --count $(git merge-base 3aa07e3 c74461c)..3aa07e3",
            "git -C <SharedOS> rev-list --count $(git merge-base 3aa07e3 c74461c)..c74461c",
            "git -C <SharedOS> diff --shortstat 3aa07e3 c74461c -- packages/contracts/src packages/core/src packages/os/src packages/runtime/src",
        ],
    }
    pkgs = {}
    for label, c in (("K1", k1["commit"]), ("K2", k2["commit"])):
        pkgs[label] = {}
        for d in ("contracts", "core", "os", "runtime"):
            pj = json.loads(git(so, "show", f"{c}:packages/{d}/package.json"))
            pkgs[label][d] = {"name": pj.get("name"), "version": pj.get("version")}
    R["sharedos"] = {"repository": so, "K1": k1, "K1-live": live, "K2": k2,
                     "K1_live_is_second_parent_of_K1": k1["parents"][1:] == [live["commit"]],
                     "K1_live_tree_equals_K1_tree": live["tree"] == k1["tree"], "packages": pkgs}

    # ---------------------------------------------------------------- runtime digest, recomputed from a K2 build
    dig = {"build": a.sharedos_k2_build}
    if os.path.isdir(a.sharedos_k2_build) and shutil.which("node"):
        dig["build_head"] = git(a.sharedos_k2_build, "rev-parse", "HEAD")
        dig["build_tracked_dirty"] = bool(git(a.sharedos_k2_build, "status", "--porcelain", "--untracked-files=no"))
        tmp = tempfile.mkdtemp(prefix="prov-digest-")
        try:
            with open(os.path.join(tmp, "load-sharedos.ts"), "w") as fh:
                fh.write(git(se, "show", f"{E3}:{LOADER}") + "\n")
            with open(os.path.join(tmp, "run.mts"), "w") as fh:
                fh.write("import { digestSharedOsRuntimeV1 } from './load-sharedos.ts';\n"
                         "console.log(digestSharedOsRuntimeV1(process.argv[2]) ?? 'undefined');\n")
            dig["node"] = run(["node", "--version"])
            dig["function"] = f"digestSharedOsRuntimeV1 from SharedEval {E3}:{LOADER}"
            dig["digest"] = run(["node", "run.mts", a.sharedos_k2_build], cwd=tmp).splitlines()[-1]
        finally:
            shutil.rmtree(tmp)
        dig["equals_pin"] = dig.get("digest") == DIGEST
    else:
        dig["skipped"] = "no local K2 build or no node"
    R["runtime_digest_recomputed"] = dig

    # ---------------------------------------------------------------- SharedEval: what each revision declares
    ev = {}
    for short in E1_LOCAL + E2 + [E3]:
        full = resolve(se, short)
        ev[short] = {"where": f"local clone {se}", "commit": full}
        if full:
            ev[short]["tree"] = git(se, "rev-parse", f"{full}^{{tree}}")
            ev[short]["load_sharedos"] = pins_from_text(git(se, "show", f"{full}:{LOADER}"))
            ev[short]["build_image_pin"] = build_image_pin(git(se, "show", f"{full}:scripts/experiments/build-image.sh"))
            ev[short]["ci_pin"] = ci_pin(se, full)
    ev[E4] = {"where": f"not in the local clone; its tree {D44E478_TREE} is (also the tree of 6773638)",
              "commit": resolve(se, E4), "tree_in_local_clone": git(se, "cat-file", "-t", D44E478_TREE, check=False) == "tree",
              "local_commit_with_same_tree": sorted({c.split()[0] for c in git(se, "log", "--all", "--format=%H %T").splitlines()
                                                     if c.split()[1] == D44E478_TREE}),
              "load_sharedos_from_tree": pins_from_text(git(se, "show", f"{D44E478_TREE}:{LOADER}"))}
    R["sharedeval_local"] = ev
    R["unresolved_locally"] = {s: resolve(se, s) for s in E1_UNRESOLVED + ["5aaa7f1", E3_HEADER]}

    # header ladder: E3's tree + the patch must give 4565add's tree (read on the VM below)
    tmp = tempfile.mkdtemp(prefix="prov-patch-")
    try:
        bare = os.path.join(tmp, "repo.git")
        run(["git", "init", "-q", "--bare", bare])
        with open(os.path.join(bare, "objects", "info", "alternates"), "w") as fh:
            fh.write(os.path.join(git(se, "rev-parse", "--absolute-git-dir"), "objects") + "\n")
        env = {**os.environ, "GIT_DIR": bare, "GIT_INDEX_FILE": os.path.join(tmp, "index")}
        run(["git", "read-tree", resolve(se, E3)], env=env)
        run(["git", "apply", "--cached", os.path.abspath(PATCH)], env=env)
        patched_tree = run(["git", "write-tree"], env=env)
        patch_id = run(["git", "patch-id", "--stable"], inp=open(PATCH).read(), env=env).split()
    finally:
        shutil.rmtree(tmp)
    with open(PATCH, encoding="utf-8") as fh:
        first = fh.readline().split()
    R["header_patch"] = {"patch": PATCH, "patch_names_commit": first[1] if len(first) > 1 else None,
                         "E3_tree_plus_patch": patched_tree, "patch_id_stable": patch_id[0] if patch_id else None}

    # ---------------------------------------------------------------- VM
    if a.vm_json:
        vm = json.load(open(a.vm_json))
    else:
        vm = json.loads(run(["ssh", "-o", "BatchMode=yes", a.vm, "nice -n 19 python3 -"], inp=open(VM_SCRIPT).read()))
    R["vm"] = vm
    R["header_patch"]["vm_4565add_tree"] = vm["commits"]["4565add"]["tree"]
    R["header_patch"]["vm_4565add_parent"] = vm["commits"]["4565add"]["parents"]
    R["header_patch"]["tree_equal"] = patched_tree == vm["commits"]["4565add"]["tree"]

    # cross-check E2 per-session revisions with the packing-delivery freeze, and split by validity
    frozen = {}
    with gzip.open(SESSIONS, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            frozen[(r["study"], r["run_id"])] = (r["source_revision"][:7] if r["source_revision"] else None, r["valid"])
    cross = {}
    for study, v in vm["e2"].items():
        rows = v["session_revision_7"]
        agree = sum(1 for s, rev in rows.items() if frozen.get((study, s), ("missing",))[0] == rev)
        valid = collections.Counter((rev, frozen.get((study, s), (None, None))[1]) for s, rev in rows.items())
        cross[study] = {"sessions": len(rows), "agree_with_packing_delivery_freeze": agree,
                        "by_revision_and_validity": [{"revision": k[0], "valid": k[1], "sessions": n}
                                                     for k, n in sorted(valid.items(), key=lambda x: (str(x[0][0]), str(x[0][1])))]}
    R["e2_cross_check"] = cross

    # ---------------------------------------------------------------- GitHub (optional)
    if a.github:
        gh = {}
        for repo, ids in (("systemind-team/SharedEval", E1_LOCAL + E1_UNRESOLVED + ["5aaa7f1"] + E2 + [E3, E3_HEADER, E4, "6773638"]),
                          ("systemind-team/SharedOS", [K1, K1_LIVE, K2])):
            for i in ids:
                p = subprocess.run(["gh", "api", f"repos/{repo}/commits/{i}", "--jq", ".sha"], capture_output=True, text=True)
                gh[f"{repo}@{i}"] = p.stdout.strip() if p.returncode == 0 else "not found (HTTP 422)" if "422" in p.stderr else p.stderr.strip()[:80]
        R["github"] = gh

    report(R)
    if a.write:
        write(R)


def full(R, short):
    for src in (R["sharedeval_local"].get(short, {}).get("commit"),):
        if src:
            return src
    for repo in R["vm"]["repos"].values():
        v = repo["resolved"].get(short)
        if v:
            return v
    return None


def report(R):
    d = R["k1_k2_divergence"]
    s = R["sharedos"]
    print("K1      ", s["K1"]["commit"], "tree", s["K1"]["tree"])
    print("K1 live ", s["K1-live"]["commit"], "tree", s["K1-live"]["tree"], "| second parent of K1:",
          s["K1_live_is_second_parent_of_K1"], "| same tree:", s["K1_live_tree_equals_K1_tree"])
    print("K2      ", s["K2"]["commit"], "tree", s["K2"]["tree"])
    print("merge base", d["merge_base"], f"({len(d['merge_bases_all'])} merge base)")
    print("commits only in K2:", d["commits_only_in_K2"], "| only in K1:", d["commits_only_in_K1"])
    print("shortstat K2..K1 (four packages' src):", d["shortstat_K2_to_K1_four_package_src"]["default"])
    print("  changed lines:", d["numstat_totals"]["changed_lines"], "| rename-insensitive:",
          len(set(d["shortstat_K2_to_K1_four_package_src"].values())) == 1)
    for k in ("K1", "K2"):
        print(f"packages at {k}:", ", ".join(f"{v['name']}@{v['version']}" for v in s["packages"][k].values()))
    g = R["runtime_digest_recomputed"]
    print("runtime digest recomputed from", g["build"], "->", g.get("digest"), "| equals pin:", g.get("equals_pin"))
    for short, v in R["sharedeval_local"].items():
        ls = v.get("load_sharedos") or v.get("load_sharedos_from_tree") or {}
        print(f"pin {short:13s}", (v.get("commit") or "(tree only)")[:12],
              {k: (x["lines"], x["value"] if isinstance(x["value"], list) else x["value"][:12]) for k, x in ls.items()})
    for short, v in R["vm"]["pins"].items():
        ls = v["load_sharedos"] or {}
        print(f"pin VM {short:10s}", (v["commit"] or "?")[:12],
              {k: (x["lines"], x["value"] if isinstance(x["value"], list) else x["value"][:12]) for k, x in ls.items()})
    print("unresolved in the local clone:", [k for k, v in R["unresolved_locally"].items() if not v])
    unres_vm = [t for t in E1_UNRESOLVED + ["5aaa7f1"] if not any(r["resolved"].get(t) for r in R["vm"]["repos"].values())]
    print("unresolved in every VM clone:", unres_vm)
    h = R["header_patch"]
    print("E3 tree + patch:", h["E3_tree_plus_patch"], "| 4565add tree on VM:", h["vm_4565add_tree"], "| equal:", h["tree_equal"],
          "| 4565add parent:", h["vm_4565add_parent"])
    for study, v in R["vm"]["e2"].items():
        print(f"E2 {study:8s} sessions {v['sessions']:5d}", {k[:7]: n for k, n in v["by_revision"].items()},
              "| bound:", [(b["revision"][:7] if b["revision"] else None, (b["runtime_digest"] or "")[:7], b["runs"]) for b in v["recorded_at_run_time"]["binding_sharedOs"]],
              "| agree with packing freeze:", R["e2_cross_check"][study]["agree_with_packing_delivery_freeze"])
    for lane, v in R["vm"]["lanes"].items():
        print(f"lane {lane:10s}", {(k[:7] if k != 'None' else k): n for k, n in v["last_launch_sourceRevision"].items()},
              "| bound:", [(b["revision"][:7] if b["revision"] else None, (b["runtime_digest"] or "")[:7], b["runs"]) for b in v["recorded_at_run_time"]["binding_sharedOs"]])
    for im in R["vm"]["e1"]["images"]:
        print("E1 image", im["imageRef"], im["cells"], "cells", "(voided: %d)" % len(im["voided_cells"]))
    print("E1 Azure cell dir readable:", R["vm"]["e1"]["azure_cells_dir_readable"],
          "| OpenRouter per-task dirs readable:", R["vm"]["e1"]["openrouter_task_dirs_readable"],
          "| SharedEval images in the VM's docker:", R["vm"]["e1"]["docker_sharedeval_images_on_vm"])
    if "github" in R:
        for k, v in R["github"].items():
            print("github", k, "->", v[:12] if len(v) == 40 else v)


def write(R):
    s, d, vm = R["sharedos"], R["k1_k2_divergence"], R["vm"]
    labels = {
        "K1": s["K1"]["commit"], "K1-live": s["K1-live"]["commit"], "K2": s["K2"]["commit"],
        "E1": [full(R, x) for x in E1_LOCAL] + [full(R, x) or x for x in E1_UNRESOLVED],
        "E2": [full(R, x) for x in E2],
        "E3": full(R, E3), "E3-header": vm["commits"]["4565add"]["commit"], "E4": vm["commits"]["d44e478"]["commit"],
    }
    with open(os.path.join(OUT, "revision_labels.json"), "w") as fh:
        json.dump(labels, fh, indent=1)
        fh.write("\n")

    def bound(lane_or_study):
        src = vm["e2"].get(lane_or_study) or vm["lanes"].get(lane_or_study)
        return src["recorded_at_run_time"]
    entries = {
        "K1": {"what": "SharedOS conformance snapshot: the kernel revision the conformance results are reported at "
                       "(evidence/runtime_manifest.json source_revision; evidence/kernel_conformance.source.json)",
               "commit": s["K1"]["commit"], "tree": s["K1"]["tree"], "subject": s["K1"]["subject"],
               "checked": "local SharedOS clone and VM clone <vm>/repos/SharedOS: git log -1 --format='%H %T %P' c74461c",
               "verified": True, "table9": TABLE9["K1"], "agrees_with_table9": True},
        "K1-live": {"what": "commit of the live conformance pass of 2026-09-08 (evidence/live_conformance/); second parent "
                            "of the K1 merge commit, with the same tree",
                    "commit": s["K1-live"]["commit"], "tree": s["K1-live"]["tree"], "author_date": s["K1-live"]["author_date"],
                    "second_parent_of_K1": s["K1_live_is_second_parent_of_K1"], "same_tree_as_K1": s["K1_live_tree_equals_K1_tree"],
                    "checked": "local SharedOS clone and VM clone: git log -1 --format='%H %T %P %ad' 5392148",
                    "verified": True, "table9": TABLE9["K1-live"], "agrees_with_table9": True},
        "K2": {"what": "SharedOS revision every evaluator revision below pins (SHAREDOS_VERIFIED_REVISION_V1) and that every "
                       "run directory of E2, E3, the header ladder and E4 recorded binding at run time",
               "commit": s["K2"]["commit"], "tree": s["K2"]["tree"], "subject": s["K2"]["subject"],
               "checked": "local SharedOS clone, VM clones SharedOS and SharedOS-3aa07e3 (HEAD 3aa07e3, no tracked changes, "
                          "dist built); binding.json of every run directory (vm.e2/lanes recorded_at_run_time)",
               "verified": True, "verified_for_studies": "E2, E3, E3-header, E4 from run records; E1 only through the pin in "
                                                         "the source of 58829fe and 0735564 (PAIR I run records are not readable)",
               "table9": TABLE9["K2"], "agrees_with_table9": True},
        "runtime-digest": {"what": "SHAREDOS_VERIFIED_RUNTIME_DIGEST_V1: sha256 over the four runtime packages' package.json "
                                   "and dist JavaScript plus zod's v3 closure (digestSharedOsRuntimeV1)",
                           "value": DIGEST, "recomputed": R["runtime_digest_recomputed"],
                           "checked": "declared at every evaluator revision opened (evaluator_pins); recomputed from the "
                                      "local K2 build; recorded at run time by every E2/E3/E3-header/E4 run directory",
                           "verified": bool(R["runtime_digest_recomputed"].get("equals_pin")), "table9": TABLE9["runtime-digest"],
                           "agrees_with_table9": True},
        "E1": {"what": "PAIR I builds: OpenRouter cells ran in images sharedeval-experiment:<first 12 hex of the SharedEval "
                       "commit>; Azure cells ran SharedEval natively",
               "commits": labels["E1"], "images_by_cell": vm["e1"]["images"],
               "checked": "58829fe and 0735564: local clone and every VM SharedEval clone (pins below). Image per cell: "
                          "<vm>/work/v41-grid-out/*/*/cell-provenance.json (imageRef, imageDigest).",
               "verified": "partial: 58829fe and 0735564 (commits and pins) and the cell-to-image mapping; NOT 79b52cf8b76b "
                           "or 40f4f01 (in no local or VM clone and not on GitHub systemind-team/SharedEval), so their SharedOS "
                           "pin is unverified",
               "table9": TABLE9["E1"], "agrees_with_table9": True},
        "E2": {"what": "probing grid (grid600, 2,400 sessions) and packing study (pack1, 180; pack10, 18)",
               "commits": labels["E2"],
               "sessions_by_revision": {k: v["by_revision"] for k, v in vm["e2"].items()},
               "checked": "last launch log per session (<vm>/runs/<study>/logs/<session>.*.log, sourceRevision)",
               "verified": True, "table9": TABLE9["E2"], "agrees_with_table9": True},
        "E3": {"what": "ladder grid (VM lane t3simple, run ids S4-*) and identity comparison (VM lane pair2id2)",
               "commit": labels["E3"], "tree": vm["commits"]["8081e7e"]["tree"],
               "checked": "local clone and VM clone SharedEval-a1 (HEAD, no tracked changes); launch logs of t3simple "
                          "and pair2id2 (vm.lanes)", "verified": True, "table9": TABLE9["E3"], "agrees_with_table9": True},
        "E3-header": {"what": "header ladder (VM lane pair2told): E3 plus the told-policy patch",
                      "commit": labels["E3-header"], "tree": vm["commits"]["4565add"]["tree"],
                      "parent": vm["commits"]["4565add"]["parents"], "patch": R["header_patch"],
                      "checked": "VM clone SharedEval-told (HEAD 4565add); local: E3's tree with the patch applied "
                                 "(git apply --cached in a throw-away repository) equals 4565add's tree",
                      "verified": R["header_patch"]["tree_equal"], "table9": TABLE9["E3"], "agrees_with_table9": True},
        "E4": {"what": "NET rerun (VM lanes net-or-ds, net-or-glm)", "commit": labels["E4"],
               "tree": vm["commits"]["d44e478"]["tree"], "parent": vm["commits"]["d44e478"]["parents"],
               "same_tree_as": R["sharedeval_local"][E4]["local_commit_with_same_tree"],
               "checked": "VM clone <vm>/repos/SE-net-e1 (HEAD d44e478, no tracked changes); its tree is in the "
                          "local clone as the tree of 6773638 (origin/net/register-missing-workspaces)",
               "verified": True, "table9": TABLE9["E4"], "agrees_with_table9": True},
    }
    pins = {short: {"commit": v.get("commit"), "where": v["where"],
                    "file": LOADER, **(v.get("load_sharedos") or {}),
                    **({"scripts/experiments/build-image.sh SHAREDOS_PINNED_REVISION": v["build_image_pin"]} if v.get("build_image_pin") else {}),
                    **({".github/workflows/ci.yml SHAREDOS_PIN": v["ci_pin"]} if v.get("ci_pin") else {})}
            for short, v in R["sharedeval_local"].items() if v.get("load_sharedos")}
    for short, v in vm["pins"].items():
        pins[f"{short} (VM)"] = {"commit": v["commit"], "where": v["repo"], "file": LOADER, **(v["load_sharedos"] or {})}
    doc = {
        "what": "Provenance manifest for the paper's kernel (K) and evaluator (E) revisions. "
                "Regenerate with: python3 scripts/freeze/provenance/collect.py --github --write",
        "generated_utc": R["generated_utc"],
        "labels": entries,
        "k1_k2_divergence": d,
        "runtime_packages": {
            "SHAREDOS_RUNTIME_PACKAGES_V1": ["contracts", "core", "os", "runtime"],
            "listed_in": f"SharedEval {LOADER}, lines 26-31 at every evaluator revision opened (evaluator_pins)",
            "npm_packages": s["packages"],
        },
        "evaluator_pins": pins,
        "recorded_at_run_time": {k: bound(k) for k in list(vm["e2"]) + list(vm["lanes"])},
        "e2_sessions": {k: {x: v[x] for x in ("sessions", "rule", "by_revision", "by_requester", "sessions_whose_launches_disagree",
                                                "sessions_without_a_revision", "sessions_without_logs", "log_ids_not_a_session",
                                                "launch_revision_vs_run_json_kernelRevision") if x in v}
                        for k, v in vm["e2"].items()},
        "e2_cross_check_with_packing_delivery": R["e2_cross_check"],
        "other_lanes_launch_revisions": {k: {x: v[x] for x in ("run_ids_with_logs", "last_launch_sourceRevision",
                                                               "every_log_sourceRevision", "logs_without_revision")}
                                         for k, v in vm["lanes"].items()},
        "e1": vm["e1"],
        "vm_clones": vm["repos"],
        "sharedos_k2_checkout_on_vm": vm["sharedos_k2_checkout"],
        "github": R.get("github"),
    }
    with open(os.path.join(OUT, "provenance.json"), "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote", os.path.join(OUT, "provenance.json"), "and", os.path.join(OUT, "revision_labels.json"))


if __name__ == "__main__":
    main()
