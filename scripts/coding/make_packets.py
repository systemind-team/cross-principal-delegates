#!/usr/bin/env python3
"""Build the two coding tasks' packets (data keys P1-3: literal policy verdicts; P1-4: public or internal work items),
their hidden keys and the answer templates.

Inputs (frozen): evidence/v3.14/pair-dataset/ (questions.json, alex_data_store.json and the policy texts the
responders read), the relationship label file (evidence/v3.1/..., used here only to pick the work_public
questions for the public/internal task and recorded in the key, never written to a packet), the ladder grid's MANIFEST.json
(evidence/v3.13/multi-table3/), and scripts/coding/planted.py.

Outputs:
  evidence/v3.14/coding-p1-3/packets/{A,B}/...   packets for annotator A and B (same lines and codes,
  evidence/v3.14/coding-p1-4/packets/{A,B}/...   different order), answer templates, INSTRUCTIONS.md
  evidence/v3.14/coding-p1-3/packets/MANIFEST.json, coding-p1-4/packets/MANIFEST.json: sha256 of every
      packet file and of the hidden key
  evidence/v3.14/coding-p1-{3,4}/key/key-P1-{3,4}.json   the hidden key (code -> task, policy,
      requester, planted answer). Not staged until both annotators have returned their answers.
  Other sources on a public/internal line: notes and to-dos in a work folder (Work, Projects, Meetings, Shared) in
  which a gold fact of the question appears (fact_in), at most five, after the sources the question cites.
  --release DIR copies each annotator's folder to DIR/p1-{3,4}/annotator-{A,B}/ (the coders' release folder).
  --instructions DIR reads P1-3-INSTRUCTIONS.md and P1-4-INSTRUCTIONS.md from DIR; by default the frozen copies in
  the packets are reused, so a rebuild reproduces them.

Deterministic: fixed seeds; running it twice gives byte-identical files.
"""
import hashlib
import json
import pathlib
import random
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "coding"))
import planted  # noqa: E402

DS = ROOT / "evidence/v3.14/pair-dataset"
LABELS = ROOT / "evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/relationship_label_matrix_v2.json"
LADDER = ROOT / "evidence/v3.13/multi-table3/MANIFEST.json"
OUT3 = ROOT / "evidence/v3.14/coding-p1-3"
OUT4 = ROOT / "evidence/v3.14/coding-p1-4"

SEED_CODES, SEED_ORDER = 314159, {"A": 271828, "B": 161803}
PART = 300
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

questions = json.loads((DS / "questions.json").read_text())
Q = {f"PAIR-Q{q['id']}": q for q in questions["questions"]}
A = {f"PAIR-A{a['id']}": a for a in questions["actions"]}
labels = json.loads(LABELS.read_text())
QCAT = {f"PAIR-Q{q['id']}": q["category"] for q in labels["questions"]}
ACAT = {f"PAIR-A{a['id']}": a["category"] for a in labels["actions"]}
store = json.loads((DS / "alex_data_store.json").read_text())
NOTE_FOLDER = {f["id"]: f["name"] for f in store["note_folders"]}
TODO_FOLDER = {f["id"]: f["name"] for f in store["todo_folders"]}
LADDER_TASKS = [t for g in sorted(json.loads(LADDER.read_text())["groups"].items()) for t in g[1]]
assert len(LADDER_TASKS) == 150 and len(set(LADDER_TASKS)) == 150


def policy(name):
    return (DS / "policies" / name).read_text()


def identity_sentence(text):
    lines = [l for l in text.splitlines() if l.startswith("You are acting on behalf of your owner, Alex Chen")]
    assert len(lines) == 1, lines
    return lines[0]


def d1_body():
    bodies = {policy(f"PAIR-I_D1_R{k}.md").split("\n---\n", 1)[1].strip() for k in range(4)}
    assert len(bodies) == 1, "D1 body differs between requesters"
    return bodies.pop()


def task_line(tid):
    if tid in Q:
        return {"kind": "question", "request": Q[tid]["question"], "reveals": list(Q[tid]["gold_key_facts"])}
    return {"kind": "action", "request": A[tid]["instruction"]}


class Codes:
    def __init__(self, seed):
        self.rng, self.used = random.Random(seed), set()

    def new(self):
        while True:
            c = "".join(self.rng.choice(ALPHABET) for _ in range(8))
            if c not in self.used:
                self.used.add(c)
                return c


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write_packet(folder, name, title, policy_text, who, lines, part, nparts):
    body = [f"# {title}, part {part} of {nparts}", "",
            "Read INSTRUCTIONS.md first. Answer every line below in "
            f"`answers/{name}.csv` (one row per code, in any order).", ""]
    if policy_text is not None:
        body += ["## Policy text the assistant was given (the same for every line in this file)", "",
                 "~~~text", policy_text.rstrip("\n"), "~~~", ""]
    body += ["## Who is asking (the same for every line in this file)", "", who, "",
             f"## Lines ({len(lines)})", ""]
    body += [json.dumps(l, ensure_ascii=False) for l in lines]
    (folder / f"{name}.md").write_text("\n".join(body) + "\n")
    tmpl = ["code,decision,reason"] + [f"{l['code']},," for l in lines]
    (folder / "answers").mkdir(exist_ok=True)
    (folder / "answers" / f"{name}.csv").write_text("\n".join(tmpl) + "\n")


def build_p13():
    codes, key, groups = Codes(SEED_CODES), {}, []
    d1 = d1_body()
    # D1: questions only (D1 is silent on actions, so actions leave its tests)
    g = []
    for tid in sorted(Q, key=lambda t: int(t[6:])):
        c = codes.new()
        key[c] = {"packet": "D1", "policy": "PAIR-I D1", "requester": None, "task": tid, "planted": False}
        g.append({"code": c, **task_line(tid)})
    for i, (kind, req, rev, ans, clause) in enumerate(planted.D1):
        c = codes.new()
        key[c] = {"packet": "D1", "policy": "PAIR-I D1", "requester": None, "task": f"PLANT-D1-{i + 1:02d}",
                  "planted": True, "answer": ans, "clause": clause}
        g.append({"code": c, "kind": kind, "request": req, "reveals": rev})
    groups.append(("D1", "Coding packet P1-3 / D1 (generic caution)", d1,
                   "This text does not mention who is asking, so the requester cannot change the answer.", g))
    # D2: every task x R0-R3, with the header naming the requester
    for r in ("R0", "R1", "R2", "R3"):
        text = policy(f"PAIR-I_D2_{r}.md")
        g = []
        for tid in sorted(Q, key=lambda t: int(t[6:])) + sorted(A, key=lambda t: int(t[6:])):
            c = codes.new()
            key[c] = {"packet": f"D2-{r}", "policy": "PAIR-I D2", "requester": r, "task": tid, "planted": False}
            g.append({"code": c, **task_line(tid)})
        for i, (kind, req, rev, ans, clause) in enumerate(planted.D2[r]):
            c = codes.new()
            key[c] = {"packet": f"D2-{r}", "policy": "PAIR-I D2", "requester": r, "task": f"PLANT-D2-{r}-{i + 1:02d}",
                      "planted": True, "answer": ans, "clause": clause}
            g.append({"code": c, "kind": kind, "request": req, **({"reveals": rev} if rev else {})})
        groups.append((f"D2-{r}", f"Coding packet P1-3 / D2 (relationship policy), requester {r}", text,
                       identity_sentence(text), g))
    # CAT and PRN: the ladder grid's 150 tasks
    for pk, fname, pname, who, plant in (
            ("CAT", "PAIR-II_ladder_D2_category.md", "PAIR-II ladder D2 (category)",
             "Not given. This policy text does not depend on who is asking.", planted.CAT),
            ("PRN", "PAIR-II_identity_D2R_PRINCIPLES.md", "PAIR-II identity D2R principles, no header",
             "Not stated. The assistant is not told who is asking.", planted.PRN)):
        g = []
        for tid in LADDER_TASKS:
            c = codes.new()
            key[c] = {"packet": pk, "policy": pname, "requester": None, "task": tid, "planted": False}
            g.append({"code": c, **task_line(tid)})
        for i, (kind, req, rev, ans, clause) in enumerate(plant):
            c = codes.new()
            key[c] = {"packet": pk, "policy": pname, "requester": None, "task": f"PLANT-{pk}-{i + 1:02d}",
                      "planted": True, "answer": ans, "clause": clause}
            g.append({"code": c, "kind": kind, "request": req, **({"reveals": rev} if rev else {})})
        groups.append((pk, f"Coding packet P1-3 / {pk}", policy(fname), who, g))
    return key, groups


def norm(s):
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def materials():
    out = []
    for n in store["notes"]:
        if NOTE_FOLDER.get(n["folderId"]) == "Self":
            continue
        out.append({"type": "note", "title": n["title"], "folder": NOTE_FOLDER[n["folderId"]], "text": n["content"]})
    for t in store["todos"]:
        out.append({"type": "to-do", "title": t["title"], "folder": TODO_FOLDER[t["folderId"]],
                    "text": t.get("description") or ""})
    return out


STOP = {"a", "an", "the", "of", "and", "or", "to", "in", "on", "at", "for", "by", "with", "is", "are", "was"}
WORK_FOLDERS = {"Work", "Projects", "Meetings", "Shared"}


def words(s):
    return [w for w in re.split(r"[^a-z0-9#$%]+", norm(s)) if w]


def fact_in(fact, text):
    """A gold fact appears in a text when every meaningful word of the fact occurs within a window of
    (number of fact words + 3) consecutive words of the text. Facts with one meaningful word of under
    six characters (for example 'SF') are too short to locate and are never matched."""
    fw = [w for w in words(fact) if w not in STOP]
    if not fw or (len(fw) == 1 and len(fw[0]) < 6):
        return False
    tw = words(text)
    span = len(fw) + 3
    need = set(fw)
    for i in range(len(tw)):
        if tw[i] in need and need <= set(tw[i:i + span]):
            return True
    return False


def build_p14():
    codes, key = Codes(SEED_CODES + 4), {}
    mats = materials()
    by_title = {(m["type"], m["title"]): m for m in mats}
    g = []
    wp = sorted((t for t, c in QCAT.items() if c == "work_public"), key=lambda t: int(t[6:]))
    assert len(wp) == 200
    for tid in wp:
        q = Q[tid]
        cited = [by_title[("note", t)] for t in q.get("source_notes", [])] + \
                [by_title[("to-do", t)] for t in q.get("source_todos", [])]
        other = [m for m in mats if m not in cited and m["folder"] in WORK_FOLDERS
                 and any(fact_in(f, m["title"] + " " + m["text"]) for f in q["gold_key_facts"])]
        c = codes.new()
        key[c] = {"task": tid, "planted": False, "cited_sources": [m["title"] for m in cited],
                  "other_sources": [m["title"] for m in other[:5]]}
        g.append({"code": c, "question": q["question"], "reveals": list(q["gold_key_facts"]),
                  "sources": cited + other[:5]})
    for i, (question, rev, srcs, ans, marker) in enumerate(planted.P14):
        c = codes.new()
        key[c] = {"task": f"PLANT-P14-{i + 1:02d}", "planted": True, "answer": ans, "marker": marker}
        g.append({"code": c, "question": question, "reveals": rev,
                  "sources": [{"type": t, "title": ti, "folder": f, "text": tx} for t, ti, f, tx in srcs]})
    return key, [("WP", "Coding packet P1-4 / public or internal", None,
                  "Not relevant: public or internal is a property of the information, not of who asks.", g)]


def emit(out, key, groups, keyname, instructions):
    """instructions: the bytes of the task's INSTRUCTIONS.md, read before the packets folder is rebuilt."""
    pk = out / "packets"
    if pk.exists():
        shutil.rmtree(pk)
    manifest = {"files": {}}
    for ann in ("A", "B"):
        folder = pk / ann
        folder.mkdir(parents=True)
        (folder / "INSTRUCTIONS.md").write_bytes(instructions)
        rng = random.Random(SEED_ORDER[ann])
        for name, title, text, who, lines in groups:
            order = list(lines)
            rng.shuffle(order)
            nparts = -(-len(order) // PART)
            size = -(-len(order) // nparts)
            parts = [order[i:i + size] for i in range(0, len(order), size)]
            for k, part in enumerate(parts, 1):
                fname = f"{name}-part{k}" if len(parts) > 1 else name
                write_packet(folder, fname, title, text, who, part, k, len(parts))
    (out / "key").mkdir(exist_ok=True)
    keypath = out / "key" / keyname
    keypath.write_text(json.dumps({"seeds": {"codes": SEED_CODES, "order": SEED_ORDER}, "lines": key},
                                  indent=1, sort_keys=True) + "\n")
    for f in sorted(pk.rglob("*")):
        if f.is_file():
            manifest["files"][str(f.relative_to(out))] = sha(f)
    manifest["key"] = {"path": str(keypath.relative_to(out)), "sha256": sha(keypath),
                       "lines": len(key), "planted": sum(v["planted"] for v in key.values())}
    (pk / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def arg(name):
    return pathlib.Path(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else None


if __name__ == "__main__":
    src = arg("--instructions")
    instr = {t: ((src / f"{t}-INSTRUCTIONS.md") if src else out / "packets/A/INSTRUCTIONS.md").read_bytes()
             for t, out in (("P1-3", OUT3), ("P1-4", OUT4))}
    k3, g3 = build_p13()
    m3 = emit(OUT3, k3, g3, "key-P1-3.json", instr["P1-3"])
    k4, g4 = build_p14()
    m4 = emit(OUT4, k4, g4, "key-P1-4.json", instr["P1-4"])
    for name, m in (("P1-3", m3), ("P1-4", m4)):
        print(f"{name}: {len(m['files'])} packet files, {m['key']['lines']} lines ({m['key']['planted']} planted), "
              f"key sha256 {m['key']['sha256']}")
    room = arg("--release")
    if room:
        for task, out in (("p1-3", OUT3), ("p1-4", OUT4)):
            for ann in ("A", "B"):
                dst = room / task / f"annotator-{ann}"
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(out / "packets" / ann, dst)
        print("released to", room)
