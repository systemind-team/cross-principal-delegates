#!/usr/bin/env python3
"""Re-run the grok-4.6 supplement's analysis from the frozen files and check that it reproduces.

analyze.py and render_results.py write into evidence/v3.13/single-grid-grok/, which is never modified. So this
script copies them, common.py and the frozen evidence into a temporary mirror of the repository layout, runs them
there exactly as scripts/single_grid/grok/README.md says produced RESULTS.md, and compares the outputs with the
committed ones. The 66,000 frozen PAIR I rows come from evidence/v3.14/single-grid-tasks/tasks.jsonl.xz and must have
the SHA-256 common.py fixes (195f90e1...); diag_scan.json and the two rescore reports come from
evidence/v3.13/single-grid/.

Output: evidence/v3.14/single-grid-grok/reproduce.json
Usage: python3 scripts/single_grid/grok/reproduce.py
"""
import hashlib
import json
import lzma
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "scripts/single_grid/grok"
GROK = ROOT / "evidence/v3.13/single-grid-grok"
GRID = ROOT / "evidence/v3.13/single-grid"
ROWS = ROOT / "evidence/v3.14/single-grid-tasks/tasks.jsonl.xz"
OUT = ROOT / "evidence/v3.14/single-grid-grok/reproduce.json"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    rec = {"what": __doc__.split("\n\n")[0], "steps": []}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        repo = tmp / "repo"
        shutil.copytree(SRC, repo / "scripts/single_grid/grok", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(GROK, repo / "evidence/v3.13/single-grid-grok")
        shutil.copytree(GRID, repo / "evidence/v3.13/single-grid")
        frozen = tmp / "frozen"
        frozen.mkdir()
        with lzma.open(ROWS) as f, open(frozen / "tasks.jsonl", "wb") as g:
            shutil.copyfileobj(f, g)
        for name in ("diag_scan.json", "rescore-openrouter-82.json", "rescore-azure-28.json"):
            shutil.copyfile(GRID / name, frozen / name)
        rec["frozen_rows_sha256"] = sha(frozen / "tasks.jsonl")
        mirror = repo / "evidence/v3.13/single-grid-grok"
        produced = tmp / "grok_supplement.json"
        cmd = [sys.executable, "scripts/single_grid/grok/analyze.py", "--frozen", str(frozen),
               "--grok", "evidence/v3.13/single-grid-grok/run/plan",
               "--grok-scan", "evidence/v3.13/single-grid-grok/run/plan/scan.json",
               "--grok-retry", "evidence/v3.13/single-grid-grok/run/retry",
               "--retry-list", "evidence/v3.13/single-grid-grok/run/retry_list_merged.json", "--out", str(produced)]
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        scrub = lambda t: t.replace(str(tmp.resolve()), "<tmp>").replace(str(tmp), "<tmp>")  # noqa: E731
        rec["steps"].append({"command": "analyze.py " + scrub(" ".join(cmd[2:])), "exit": r.returncode,
                             "stdout_tail": scrub(r.stdout[-1500:]), "stderr_tail": scrub(r.stderr[-1500:])})
        if r.returncode:
            raise SystemExit(r.stderr)
        rec["grok_supplement_byte_identical"] = produced.read_bytes() == (GROK / "grok_supplement.json").read_bytes()
        rec["grok_supplement_json_equal"] = json.loads(produced.read_text()) == \
            json.loads((GROK / "grok_supplement.json").read_text())
        shutil.copyfile(produced, mirror / "grok_supplement.json")
        (mirror / "RESULTS.md").unlink()
        r = subprocess.run([sys.executable, "scripts/single_grid/grok/render_results.py"], cwd=repo,
                           capture_output=True, text=True)
        rec["steps"].append({"command": "render_results.py", "exit": r.returncode, "stderr_tail": r.stderr[-1500:]})
        if r.returncode:
            raise SystemExit(r.stderr)
        rec["results_md_byte_identical"] = (mirror / "RESULTS.md").read_bytes() == (GROK / "RESULTS.md").read_bytes()
        rec["committed_sha256"] = {"grok_supplement.json": sha(GROK / "grok_supplement.json"),
                                   "RESULTS.md": sha(GROK / "RESULTS.md")}
    rec["reproduces"] = rec["frozen_rows_sha256"].startswith("195f90e1") and rec["grok_supplement_json_equal"] \
        and rec["results_md_byte_identical"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "steps"}, indent=1))
    if not rec["reproduces"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
