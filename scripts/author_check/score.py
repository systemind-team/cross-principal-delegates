#!/usr/bin/env python3
"""Author checks of the four coding tasks: freeze the answers, score them against the two LLM coders, emit macros.

The tasks keep the keys the data uses: P1-1 the metadata-leak patterns, P1-2 the matcher adjudication, P1-3 the literal
policy verdicts, P1-4 public or internal work items.

Inputs
  evidence/v3.14/author-check/answers-2026-10-23.md           the answers as received in chat, verbatim, with a
                                                              reference parsing at its end (withheld from the
                                                              anonymized supplement; answers.json stands in for it)
  evidence/v3.14/author-check/confirmations.json              the switch for answers awaiting the checker's
                                                              confirmation; an entry is applied only when its status
                                                              is "confirmed" (until then the answer as given counts)
  keys (committed once every coder had returned):
    P1-4  evidence/v3.14/coding-p1-4/author_check/key.json    item -> both coders' codes (digest in results.json)
    P1-3  evidence/v3.14/coding-p1-3/author-check/key.json    item -> code; the codes are the frozen answers in
                                                              evidence/v3.14/coding-p1-3/answers/{A,B}/
    P1-1  evidence/v3.14/metadata/author-check/key.json       item -> both coders' codes (digest in draw.json)
    P1-2  evidence/v3.14/author-check/p1-2-author_check_key.json, a copy of the adjudication's sealed key (digest in
                                                              evidence/v3.14/adjudication/packets/MANIFEST.json) ->
                                                              item_id; the labels are the adjudication's frozen label
                                                              sets and the adjudicator's choices mapped to A and B
Every key is checked twice: against its committed digest, and by content (each keyed line in the coders' packets
carries the same text as the item the checker saw, and each keyed code equals the coders' frozen answer).

Scoring (per task and per checker; checker 1 is an author, checker 2 a second author):
  agreement with coder A and with coder B (all items); with the consensus (the lines both coders coded alike;
  exact one-sided 95% Clopper-Pearson lower bound, as the literal-verdict pre-registration reports it); on a contested line,
  which coder the checker sided with; the lines on which the checker contradicts both coders (the stop rule).
  P1-3 compares the literal verdict as permit (SHARE, PERFORM) or withhold (WITHHOLD, DECLINE), as the analysis does.
  P1-2 follows scripts/adjudication/score.py: binary = conveys a fact (FULL or PARTIAL), exact = the same label; the
  consensus is the final label (the coders' label where they agree, else the adjudicator's choice); two-sided
  Clopper-Pearson interval.
Agreement counts verified independently on the answers as given are asserted (REFERENCE below).

Outputs
  evidence/v3.14/author-check/{answers-2026-10-23.md, answers.json, results.json, macros.json}
  tables/author_check_numbers.tex   \\acnum{key} macros, and the \\ptwonum{author-*} slots of Appendix F
Usage: python3 scripts/author_check/score.py
       python3 scripts/author_check/score.py crosscheck-p12 --sealed DIR   (DIR holds the adjudication's sealed key.jsonl
                                                                          and planted_answers.jsonl, kept outside git)
"""
import csv
import hashlib
import json
import math
import os
import pathlib
import re
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))
from halfup import fixed, to_fraction  # noqa: E402

EV = ROOT / "evidence/v3.14"
OUT = EV / "author-check"
RAW = OUT / "answers-2026-10-23.md"          # the verbatim record; absent from the anonymized supplement
TEX = ROOT / "tables/author_check_numbers.tex"

# Digests committed before the checkers answered (P1-3's was recorded when its key was drawn, before any answer).
DIGEST = {"P1-4": ("evidence/v3.14/coding-p1-4/results.json", ["author_check", "key_sha256"]),
          "P1-1": ("evidence/v3.14/metadata/author-check/draw.json", ["key_sha256"]),
          "P1-3": "6668d7ccb1c5a0c2231066b2d34bc14fc5047c361bf9cfa7ac8b7167144c552d",
          "P1-2": ("evidence/v3.14/adjudication/packets/MANIFEST.json",
                   ["author_check_p1_2", "sealed_files_sha256", "author_check_key.json"])}
# Agreement counts verified independently on the answers as given (2026-10-23).
REFERENCE = {("P1-4", 1): {"A": 6, "B": 6}, ("P1-4", 2): {"A": 10, "B": 10},
        ("P1-3", 1): {"A": 8, "B": 8}, ("P1-3", 2): {"A": 5, "B": 5},
        ("P1-1", 1): {"A": 9, "B": 9},
        ("P1-2", 1): {"binary": 19, "exact": 19}}
CODES = {"P1-4": {"P": "PUBLIC", "I": "INTERNAL"},
         "P1-3": {"S": "SHARE", "W": "WITHHOLD", "P": "PERFORM", "D": "DECLINE"},
         "P1-1": {"Y": "YES", "N": "NO"}}
PERMIT = {"SHARE", "PERFORM"}
CHECKER = {1: "checker 1 (an author)", 2: "checker 2 (a second author)"}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ the answers
def parse_answers(text):
    """Each task's answer lines, by checker: a line that says "reviewer" is checker 2's, any other checker 1's.
    Numbered answers ("1 I, 2 P, ...") are read by number; unnumbered ones as the run of answer letters."""
    sections, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"\s*\*\s*(P1-\d)\s*[（(]", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
            continue
        if line.startswith("Parsed (host)"):      # the record's marker for its reference parsing
            cur = None
        if cur and line.strip() and not line.startswith("Parsed") and not line.startswith("Pending"):
            sections[cur].append(line)
    out = {}
    for task, lines in sections.items():
        for line in lines:
            body = line.strip().lstrip("*").strip()
            checker = 2 if "reviewer" in body else 1
            if task == "P1-2":
                items = re.findall(r"(\d+)\s+([A-Z]+)(?:\(([\d,\s]*)\))?", body.split(":", 1)[1])
                ans = []
                for k, (num, lab, facts) in enumerate(items, 1):
                    assert int(num) == k, (task, num)
                    ans.append({"label": lab, "facts": [int(x) for x in facts.replace(",", " ").split()]})
            else:
                alphabet = "".join(CODES[task])
                numbered = re.findall(rf"(\d+)\s+([{alphabet}])\b", body)
                if numbered:
                    assert [int(n) for n, _ in numbered] == list(range(1, len(numbered) + 1)), (task, body)
                    letters = [c for _, c in numbered]
                else:
                    letters = re.findall(rf"[{alphabet}]", re.sub(r"[（(]\s*me\b.*$", "", body))
                ans = [CODES[task][c] for c in letters]
            assert (task, checker) not in out, (task, checker)
            out[(task, checker)] = ans
    return out


def parse_reference(text):
    """The reference parsing at the end of the record, for the three single-letter tasks."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"(P1-\d) checker1: ([A-Z ]+?)(?: \| checker2: ([A-Z ]+))?$", line.strip())
        if m:
            out[(m.group(1), 1)] = [CODES[m.group(1)][c] for c in m.group(2).split()]
            if m.group(3):
                out[(m.group(1), 2)] = [CODES[m.group(1)][c] for c in m.group(3).split()]
    return out


# ------------------------------------------------------------------ the keys
def read_csv_codes(folder):
    out = {}
    for f in sorted(pathlib.Path(folder).glob("*.csv")):
        for r in csv.DictReader(open(f, newline="")):
            out[r["code"].strip()] = (r["decision"].strip().upper(), (r.get("reason") or "").strip())
    return out


def packet_lines(folder, pattern="*.md"):
    """code -> (file, line) for every JSON line of a coder packet folder."""
    out = {}
    for f in sorted(pathlib.Path(folder).glob(pattern)):
        for line in f.read_text().splitlines():
            if line.startswith("{") and '"code"' in line:
                row = json.loads(line)
                out[row["code"]] = (f.name, row)
    return out


def jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def check_digest(task, path):
    d = DIGEST[task]
    if isinstance(d, str):
        want = d
    else:
        want = json.loads((ROOT / d[0]).read_text())
        for k in d[1]:
            want = want[k]
    got = sha(path)
    assert got == want, f"{task} key digest {got} != committed {want}"
    return got


def keys():
    """Per task: item -> {"A": code, "B": code, ...} after the digest and content checks."""
    out, digests = {}, {}
    # P1-4
    p = EV / "coding-p1-4/author_check/key.json"
    digests["P1-4"] = check_digest("P1-4", p)
    key = json.loads(p.read_text())
    lines = packet_lines(EV / "coding-p1-4/packets/A", "WP.md")
    ans = {a: read_csv_codes(EV / f"coding-p1-4/answers/{a}") for a in ("A", "B")}
    packet = {r["item"]: r for r in jsonl(EV / "coding-p1-4/author_check/packet/p1-4.jsonl")}
    for item, k in key.items():
        line = lines[k["code"]][1]
        assert {f: line[f] for f in ("question", "reveals", "sources")} == \
               {f: packet[item][f] for f in ("question", "reveals", "sources")}, item
        for a in ("A", "B"):
            dec, reason = ans[a][k["code"]]
            assert dec == k[a] and reason.lower().startswith("unclear") == k[f"{a}_unclear"], (item, a)
    out["P1-4"] = {i: {"A": k["A"], "B": k["B"], "A_unclear": k["A_unclear"], "B_unclear": k["B_unclear"],
                       "stratum": k["stratum"], "task": k["task"]} for i, k in key.items()}
    # P1-3
    p = EV / "coding-p1-3/author-check/key.json"
    digests["P1-3"] = check_digest("P1-3", p)
    key = json.loads(p.read_text())
    drawn = json.loads((EV / "coding-p1-3/author-check/drawn.json").read_text())["drawn"]
    assert [(d["stratum"], d["code"]) for d in drawn] == [(key[i]["stratum"], key[i]["code"]) for i in sorted(key)]
    lines = packet_lines(EV / "coding-p1-3/packets/A")
    ans = {a: read_csv_codes(EV / f"coding-p1-3/answers/{a}") for a in ("A", "B")}
    hidden = json.loads((EV / "coding-p1-3/key/key-P1-3.json").read_text())["lines"]
    packet = {r["item"]: r for r in jsonl(EV / "coding-p1-3/author-check/packet/p1-3.jsonl")}
    out["P1-3"] = {}
    for item, k in key.items():
        fname, line = lines[k["code"]]
        shown = {f: v for f, v in packet[item].items() if f not in ("item", "policy_text", "who_is_asking")}
        assert shown == {f: v for f, v in line.items() if f != "code"}, item
        assert not hidden[k["code"]]["planted"], item
        a_permit, b_permit = ans["A"][k["code"]][0] in PERMIT, ans["B"][k["code"]][0] in PERMIT
        if k["stratum"] == "contested":
            assert a_permit != b_permit, item
        else:
            assert fname.startswith(k["stratum"].split("-")[0]) and a_permit == b_permit, item
        out["P1-3"][item] = {"A": ans["A"][k["code"]][0], "B": ans["B"][k["code"]][0], "stratum": k["stratum"],
                             "task": hidden[k["code"]]["task"], "packet": hidden[k["code"]]["packet"]}
    # P1-1
    p = EV / "metadata/author-check/key.json"
    digests["P1-1"] = check_digest("P1-1", p)
    key = json.loads(p.read_text())
    lines = packet_lines(EV / "metadata/packets/A")
    ans = {a: read_csv_codes(EV / f"metadata/answers/{a}") for a in ("A", "B")}
    packet = {r["item"]: r for r in jsonl(EV / "metadata/author-check/packet/p1-1.jsonl")}
    for item, k in key.items():
        line = lines[k["code"]][1]
        assert {f: line[f] for f in ("request", "reply", "found")} == \
               {f: packet[item][f] for f in ("request", "reply", "found")}, item
        for a in ("A", "B"):
            dec, reason = ans[a][k["code"]]
            assert dec == k[a] and reason.lower().startswith("unclear") == k[f"{a}_unclear"], (item, a)
    out["P1-1"] = {i: {"A": k["A"], "B": k["B"], "A_unclear": k["A_unclear"], "B_unclear": k["B_unclear"],
                       "stratum": k["stratum"], "kind": k["kind"]} for i, k in key.items()}
    # P1-2
    p = OUT / "p1-2-author_check_key.json"          # a copy of the sealed key, checked against the manifest digest
    digests["P1-2"] = check_digest("P1-2", p)
    key = json.load(open(p))["items"]
    E = EV / "adjudication"
    LA, LB = read_p12_labels(E / "packets/annotator-A", E / "labels/annotator-A"), \
        read_p12_labels(E / "packets/annotator-B", E / "labels/annotator-B")
    adj = {r["item_id"]: r["chosen"] for r in jsonl(E / "labels/adjudicator/mapped.jsonl")}
    items_a = {it["item_id"]: it for name in os.listdir(E / "packets/annotator-A")
               for it in jsonl(E / "packets/annotator-A" / name)}
    packet = {r["item"]: r for r in jsonl(E / "author-check/p1-2.jsonl")}
    out["P1-2"] = {}
    for item, k in key.items():
        i = k["item_id"]
        shown, orig = packet[item], items_a[i]
        assert all(shown[f] == orig[f] for f in ("question", "earlier_requests", "request", "protected_facts", "reply")), item
        a, b = LA[i], LB[i]
        if a["label"] == b["label"]:
            fin, how = a, "agreed"
        else:
            ch = adj[i]
            fin, how = (a if ch == "A" else b if ch == "B" else None), f"adjudicated ({ch})"
        out["P1-2"][item] = {"item_id": i, "stratum": k["stratum"], "pool": k["pool"], "A": a, "B": b,
                             "final": fin, "final_from": how, "n_facts": len(orig["protected_facts"])}
    return out, digests


def read_p12_labels(packets, labels):
    """score.py's read_labels: label rows follow packet order within each file."""
    out = {}
    for name in sorted(os.listdir(packets)):
        items = jsonl(os.path.join(packets, name))
        path = os.path.join(labels, name)
        if not os.path.exists(path):
            continue
        rows = [r for r in jsonl(path) if "item_id" in r]
        for it, r in zip(items, rows):
            assert r["item_id"] == it["item_id"], (name, r["item_id"])
            out[r["item_id"]] = r
    return out


# ------------------------------------------------------------------ scoring
# Clopper-Pearson bounds in plain Python (no SciPy). The bound is the p at which a binomial tail equals the target,
# found by bisection on the exact tail sum; it equals scipy.stats.beta.ppf to within 1.1e-15 (checked against the
# values this script wrote with SciPy: results.json of 2026-10-23).
def _tail_ge(k, n, p):
    """P(X >= k) for X ~ Bin(n, p); increasing in p."""
    return math.fsum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def _bisect(f, target):
    """The p in [0, 1] with f(p) = target, for f increasing in p."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if mid in (lo, hi):
            break
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return (lo + hi) / 2


def cp_lower_one_sided(k, n, alpha=0.05):
    """beta.ppf(alpha, k, n - k + 1): P(X >= k | p) = alpha."""
    return 0.0 if k == 0 else _bisect(lambda p: _tail_ge(k, n, p), alpha)


def cp_two_sided(k, n, alpha=0.05):
    """(beta.ppf(alpha/2, k, n-k+1), beta.ppf(1-alpha/2, k+1, n-k)): P(X >= k | lo) = alpha/2, P(X <= k | hi) = alpha/2."""
    lo = 0.0 if k == 0 else _bisect(lambda p: _tail_ge(k, n, p), alpha / 2)
    hi = 1.0 if k == n else _bisect(lambda p: _tail_ge(k + 1, n, p), 1 - alpha / 2)
    return lo, hi


def bound_down(x, digits=1):
    """A lower bound printed rounded towards -infinity, so the printed claim stays true."""
    return fixed(Fraction(math.floor(to_fraction(x) * 10 ** digits), 10 ** digits), digits)


def bound_up(x, digits=1):
    """An upper bound printed rounded towards +infinity."""
    return fixed(Fraction(math.ceil(to_fraction(x) * 10 ** digits), 10 ** digits), digits)


def score_binary(task, answers, key):
    """P1-4, P1-3, P1-1: one checker's answers against both coders."""
    items = sorted(key)
    assert len(answers) == len(items), (task, len(answers))
    val = (lambda c: c in PERMIT) if task == "P1-3" else (lambda c: c)
    rows = []
    for item, ans in zip(items, answers):
        k = key[item]
        a, b, x = val(k["A"]), val(k["B"]), val(ans)
        rows.append({"item": item, "number": int(item[-2:]), "answer": ans, "A": k["A"], "B": k["B"],
                     "agrees_A": x == a, "agrees_B": x == b, "coders_agree": a == b,
                     "both_flagged_unclear": bool(k.get("A_unclear") and k.get("B_unclear")),
                     "contradicts_both": x != a and x != b})
    agreed = [r for r in rows if r["coders_agree"]]
    k_cons = sum(r["agrees_A"] for r in agreed)
    return {"n": len(rows), "agree_A": sum(r["agrees_A"] for r in rows), "agree_B": sum(r["agrees_B"] for r in rows),
            "consensus_n": len(agreed), "agree_consensus": k_cons,
            "consensus_lower_bound_one_sided_95": cp_lower_one_sided(k_cons, len(agreed)) if agreed else None,
            "contested": [{"number": r["number"], "sided_with": "A" if r["agrees_A"] else "B"}
                          for r in rows if not r["coders_agree"]],
            "contradicts_both": [r["number"] for r in rows if r["contradicts_both"]],
            "contradicts_both_on_unclear": [r["number"] for r in rows if r["contradicts_both"] and r["both_flagged_unclear"]],
            "items": rows}


def score_p12(answers, key):
    items = sorted(key)
    assert len(answers) == len(items)
    conv = lambda r: bool(r and r.get("facts_conveyed"))  # noqa: E731  (score.py's definition)
    rows = []
    for item, ans in zip(items, answers):
        k = key[item]
        lab = ans["label"]
        fc = list(range(1, k["n_facts"] + 1)) if lab == "FULL" else (ans["facts"] if lab == "PARTIAL" else [])
        fn = ans["facts"] if lab == "NARROWED" else []
        r = {"label": lab, "facts_conveyed": fc, "facts_narrowed": fn}
        a, b, f = k["A"], k["B"], k["final"]
        rows.append({"item": item, "number": int(item[-2:]), "item_id": k["item_id"], "stratum": k["stratum"],
                     "answer": r, "A": a["label"], "B": b["label"], "final": f["label"] if f else "UNREADABLE",
                     "final_from": k["final_from"],
                     "binary": {"A": conv(r) == conv(a), "B": conv(r) == conv(b), "final": conv(r) == conv(f)},
                     "exact": {"A": lab == a["label"], "B": lab == b["label"], "final": f is not None and lab == f["label"]},
                     "facts_agree_final": f is not None and sorted(fc) == sorted(f.get("facts_conveyed", [])),
                     "contradicts_both": conv(r) != conv(a) and conv(r) != conv(b)})
    n = len(rows)
    out = {"n": n}
    for kind in ("binary", "exact"):
        for who in ("A", "B", "final"):
            out[f"{kind}_{who}"] = sum(r[kind][who] for r in rows)
    kb = out["binary_final"]
    out["binary_interval_two_sided_95"] = list(cp_two_sided(kb, n))
    out["binary_error_upper_bound"] = cp_two_sided(n - kb, n)[1]
    out["facts_agree_final"] = sum(r["facts_agree_final"] for r in rows)
    out["final_from"] = {s: sum(r["final_from"] == s for r in rows) for s in sorted({r["final_from"] for r in rows})}
    out["contradicts_both"] = [r["number"] for r in rows if r["contradicts_both"]]
    out["items"] = rows
    return out


def apply_confirmations(answers, conf, which):
    """Answers with the switch applied: `which` = "confirmed" (entries whose status is confirmed) or "all"."""
    out = {k: list(v) for k, v in answers.items()}
    for e in conf["entries"]:
        if which == "all" or e["status"] == "confirmed":
            k = (e["task"], e["checker"])
            idx = int(e["item"][-2:]) - 1
            assert out[k][idx] == e["as_given"], e
            out[k][idx] = e["if_confirmed"]
    return out


def score_all(answers, K):
    res = {}
    for (task, checker), ans in sorted(answers.items()):
        s = score_p12(ans, K[task]) if task == "P1-2" else score_binary(task, ans, K[task])
        res.setdefault(task, {})[f"checker {checker}"] = s
    for task in ("P1-4", "P1-3"):
        a1, a2 = answers[(task, 1)], answers[(task, 2)]
        val = (lambda c: c in PERMIT) if task == "P1-3" else (lambda c: c)
        res[task]["checkers_agree"] = sum(val(x) == val(y) for x, y in zip(a1, a2))
    return res


# ------------------------------------------------------------------ macros
def items_text(nums):
    nums = [str(n) for n in nums]
    if not nums:
        return "none"
    return nums[0] if len(nums) == 1 else ", ".join(nums[:-1]) + " and " + nums[-1]


def macros(res, conf):
    m = {}
    tag = {"P1-4": "p14", "P1-3": "p13", "P1-1": "p11", "P1-2": "p12"}
    for task, t in tag.items():
        for ck, s in res[task].items():
            if not ck.startswith("checker "):
                continue
            c = "c" + ck.split()[-1]
            m[f"{t}-n"] = str(s["n"])
            if task == "P1-2":
                for kind in ("binary", "exact"):
                    for who in ("A", "B", "final"):
                        m[f"{t}-{c}-{kind}-{who}"] = str(s[f"{kind}_{who}"])
                        m[f"{t}-{c}-{kind}-{who}-of"] = f"{s[f'{kind}_{who}']} of {s['n']}"
                lo, hi = s["binary_interval_two_sided_95"]
                m[f"{t}-{c}-binary-lo"] = fixed(100 * to_fraction(lo), 1)
                m[f"{t}-{c}-binary-hi"] = fixed(100 * to_fraction(hi), 1)
                m[f"{t}-{c}-err-hi"] = bound_up(100 * to_fraction(s["binary_error_upper_bound"]), 1)
                m[f"{t}-{c}-facts"] = str(s["facts_agree_final"])
                for kind in ("binary", "exact"):
                    a_, b_ = s[f"{kind}_A"], s[f"{kind}_B"]
                    each = str(a_) if a_ == b_ else f"{a_} (A) and {b_} (B)"
                    m[f"{t}-{c}-{kind}-each"], m[f"{t}-{c}-{kind}-each-of"] = each, f"{each} of {s['n']}"
            else:
                for who, key in (("A", "agree_A"), ("B", "agree_B"), ("cons", "agree_consensus")):
                    m[f"{t}-{c}-{who}"] = str(s[key])
                m[f"{t}-{c}-A-of"] = f"{s['agree_A']} of {s['n']}"
                each = str(s["agree_A"]) if s["agree_A"] == s["agree_B"] else f"{s['agree_A']} (A) and {s['agree_B']} (B)"
                m[f"{t}-{c}-each"], m[f"{t}-{c}-each-of"] = each, f"{each} of {s['n']}"
                m[f"{t}-{c}-B-of"] = f"{s['agree_B']} of {s['n']}"
                m[f"{t}-{c}-cons-n"] = str(s["consensus_n"])
                m[f"{t}-{c}-cons-of"] = f"{s['agree_consensus']} of {s['consensus_n']}"
                m[f"{t}-{c}-cons-lb"] = bound_down(100 * to_fraction(s["consensus_lower_bound_one_sided_95"]), 1)
                m[f"{t}-{c}-sideA"] = str(sum(x["sided_with"] == "A" for x in s["contested"]))
                m[f"{t}-{c}-sideB"] = str(sum(x["sided_with"] == "B" for x in s["contested"]))
                m[f"{t}-contested"] = str(len(s["contested"]))
            m[f"{t}-{c}-both"] = str(len(s["contradicts_both"]))
            if "contradicts_both_on_unclear" in s and task != "P1-3":
                m[f"{t}-{c}-both-unclear"] = str(len(s["contradicts_both_on_unclear"]))
            m[f"{t}-{c}-both-items"] = items_text(s["contradicts_both"])
        if "checkers_agree" in res[task]:
            m[f"{t}-c12"] = str(res[task]["checkers_agree"])
            m[f"{t}-c12-of"] = f"{res[task]['checkers_agree']} of {res[task]['checker 1']['n']}"
    m["items-c1"] = str(sum(res[t]["checker 1"]["n"] for t in tag))
    m["items-c2"] = str(sum(res[t]["checker 2"]["n"] for t in tag if "checker 2" in res[t]))
    m["tasks-c1"] = str(sum(1 for t in tag if "checker 1" in res[t]))
    m["tasks-c2"] = str(sum(1 for t in tag if "checker 2" in res[t]))
    m["pending-n"] = str(sum(e["status"] == "pending" for e in conf["entries"]))
    # Appendix F's slots, formatted as scripts/adjudication/render_p12.py formats them
    s = res["P1-2"]["checker 1"]
    lo, hi = s["binary_interval_two_sided_95"]
    ptwo = {"author-n": str(s["n"]), "author-binary": str(s["binary_final"]), "author-label": str(s["exact_final"]),
            "author-err-hi": bound_up(100 * to_fraction(s["binary_error_upper_bound"]), 1),
            "author-binary-lo": fixed(100 * to_fraction(lo), 1), "author-binary-hi": fixed(100 * to_fraction(hi), 1),
            "author-contradict-both": str(len(s["contradicts_both"]))}
    return m, ptwo


def write_tex(m, ptwo, conf):
    pend = [e for e in conf["entries"] if e["status"] == "pending"]
    head = ["% Generated by scripts/author_check/score.py from evidence/v3.14/author-check/. Do not edit.",
            "% Use \\acnum{key}; keys and values are in evidence/v3.14/author-check/macros.json. A key not set prints ??.",
            "% It also fills the \\ptwonum{author-*} slots (Appendix F) with the adjudication's author check.",
            "% Checker 1 is an author, checker 2 a second author. "
            + (f"{len(pend)} answers await the checker's confirmation and count as given "
               "(evidence/v3.14/author-check/confirmations.json)." if pend else "No answer awaits confirmation.")]
    body = [f"\\expandafter\\def\\csname ac@{k}\\endcsname{{{v}}}" for k, v in sorted(m.items())]
    body.append("\\providecommand{\\acnum}[1]{\\ifcsname ac@#1\\endcsname\\csname ac@#1\\endcsname\\else\\textbf{??}\\fi}")
    body += [f"\\expandafter\\def\\csname ptwo@{k}\\endcsname{{{v}}}" for k, v in sorted(ptwo.items())]
    TEX.write_text("\n".join(head + body) + "\n")


# ------------------------------------------------------------------ main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw_dst = RAW
    verbatim = raw_dst.exists()
    if verbatim:
        text = raw_dst.read_text()
        answers = parse_answers(text)
        ref = parse_reference(text)
        for k, v in ref.items():
            assert answers[k] == v, f"the parsing of {k} differs from the reference parsing: {answers[k]} vs {v}"
    else:
        # The anonymous supplement withholds the verbatim chat record (it names checker 1); the parsed answers,
        # which name no one, stand in for it, and the check against the reference parsing is skipped.
        rec = json.loads((OUT / "answers.json").read_text())
        answers = {(k.split(" checker ")[0], int(k.split(" checker ")[1])): v for k, v in rec["answers"].items()}
        ref = {}
        print("verbatim answers absent: scoring the parsed answers in answers.json")
    assert set(answers) == {("P1-4", 1), ("P1-4", 2), ("P1-3", 1), ("P1-3", 2), ("P1-1", 1), ("P1-2", 1)}
    conf = json.loads((OUT / "confirmations.json").read_text())
    K, digests = keys()

    as_given = score_all(answers, K)
    for (task, checker), want in REFERENCE.items():
        s = as_given[task][f"checker {checker}"]
        got = ({"A": s["agree_A"], "B": s["agree_B"]} if task != "P1-2" else
               {"binary": s["binary_final"], "exact": s["exact_final"]})
        assert got == want, f"{task} checker {checker}: {got} vs the reference {want}"
    applied = score_all(apply_confirmations(answers, conf, "confirmed"), K)
    preview = score_all(apply_confirmations(answers, conf, "all"), K)

    if verbatim:
        (OUT / "answers.json").write_text(json.dumps({
            "source": f"the answers as received in chat, copied byte for byte as {raw_dst.name} (withheld from the "
                      "anonymized supplement, which keeps this digest)",
            "source_sha256": sha(raw_dst),
            "checkers": {str(k): v for k, v in CHECKER.items()},
            "parsing": "a line that says 'reviewer' is checker 2's, any other line checker 1's; numbered answers are read "
                       "by number, unnumbered ones as the run of answer letters; P1-2's LABEL(n, ...) lists the facts "
                       "conveyed (PARTIAL) or narrowed (NARROWED), and FULL conveys every protected fact",
            "equals_reference_parsing": sorted(f"{t} checker {c}" for t, c in ref),
            "answers": {f"{t} checker {c}": v for (t, c), v in sorted(answers.items())}}, indent=1, ensure_ascii=False) + "\n")
    results = {
        "status": "scored on the answers as given" if not any(e["status"] == "confirmed" for e in conf["entries"])
        else "scored with the confirmed answers applied",
        "pending_confirmations": [e for e in conf["entries"] if e["status"] == "pending"],
        "key_sha256": digests,
        "reference_numbers_reproduced": {f"{t} checker {c}": v for (t, c), v in REFERENCE.items()},
        "as_given": as_given, "applied": applied, "if_all_pending_confirmed": preview}
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    m, ptwo = macros(applied, conf)
    m_prev, _ = macros(preview, {"entries": []})
    (OUT / "macros.json").write_text(json.dumps({"acnum": m, "ptwonum_author_slots": ptwo,
                                                 "acnum_if_all_pending_confirmed": m_prev}, indent=1) + "\n")
    write_tex(m, ptwo, conf)
    for task in ("P1-4", "P1-3", "P1-1", "P1-2"):
        for ck, s in applied[task].items():
            if not ck.startswith("checker "):
                continue
            if task == "P1-2":
                print(f"{task} {ck}: binary {s['binary_final']}/{s['n']}, exact {s['exact_final']}/{s['n']} "
                      f"(A {s['binary_A']}/{s['exact_A']}, B {s['binary_B']}/{s['exact_B']}); "
                      f"contradicts both: {s['contradicts_both']}")
            else:
                print(f"{task} {ck}: A {s['agree_A']}/{s['n']}, B {s['agree_B']}/{s['n']}, consensus "
                      f"{s['agree_consensus']}/{s['consensus_n']}; contested {s['contested']}; "
                      f"contradicts both: {s['contradicts_both']}")
    print("if every pending answer is confirmed:",
          {f"{t} {c}": (s["agree_A"], s["agree_B"]) for t in ("P1-4", "P1-3") for c, s in preview[t].items()
           if c.startswith("checker ")})
    print("wrote", TEX.relative_to(ROOT), "with", len(m), "\\acnum keys and", len(ptwo), "\\ptwonum slots")


def crosscheck_p12(sealed):
    """The P1-2 block through the adjudication's own pipeline, in a temporary folder (its files are not touched): the
    checker's labels go to scripts/adjudication/score.py --author with the arguments of
    evidence/v3.14/adjudication/analysis/final/README.md, then render_p12.py. Needs the sealed key and planted answers
    (not in git) in `sealed`. Writes p1-2_pipeline_crosscheck.json."""
    import subprocess
    import tempfile
    sealed = pathlib.Path(sealed)
    E = "evidence/v3.14/adjudication"
    res = json.loads((OUT / "results.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        with open(tmp / "author_labels.jsonl", "w") as f:
            for it in res["applied"]["P1-2"]["checker 1"]["items"]:
                a = it["answer"]
                f.write(json.dumps({"item_id": it["item_id"], "author_check_item": it["item"], "label": a["label"],
                                    "facts_conveyed": a["facts_conveyed"], "facts_narrowed": a["facts_narrowed"],
                                    "existence_type": []}) + "\n")
        cmd = ["python3", "scripts/adjudication/score.py", "--key", str(sealed / "key.jsonl"),
               "--planted", str(sealed / "planted_answers.jsonl"),
               "--packets-a", f"{E}/packets/annotator-A", "--labels-a", f"{E}/labels/annotator-A",
               "--packets-b", f"{E}/packets/annotator-B", "--labels-b", f"{E}/labels/annotator-B",
               "--adjudication", f"{E}/labels/adjudicator/mapped.jsonl", "--author", str(tmp / "author_labels.jsonl"),
               "--cells", f"{E}/frame/cells.json", "--out", str(tmp / "final")]
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)
        subprocess.run(["python3", "scripts/adjudication/render_p12.py", "--summary", str(tmp / "final/summary.json"),
                        "--out", str(tmp / "tables")], cwd=ROOT, check=True, capture_output=True)
        got = json.loads((tmp / "final/summary.json").read_text())
        frozen = json.loads((ROOT / E / "analysis/final/summary.json").read_text())
        block = got.pop("author_check")
        frozen.pop("author_check", None)  # the frozen summary also carries the author block; compare the rest only
        slots = dict(re.findall(r"\\csname ptwo@(author[^\\]*)\\endcsname\{([^}]*)\}",
                                (tmp / "tables/adjudication_numbers.tex").read_text()))
    mine = json.loads((OUT / "macros.json").read_text())["ptwonum_author_slots"]
    rec = {"what": "checker 1's P1-2 labels scored by scripts/adjudication/score.py --author and rendered by "
                   "render_p12.py, in a temporary folder, with the arguments of evidence/v3.14/adjudication/analysis/"
                   "final/README.md; the adjudication's files are not changed",
           "pipeline_author_block": block, "pipeline_ptwonum_author_slots": slots,
           "every_other_block_equals_the_frozen_summary": json.dumps(got, sort_keys=True, default=str)
           == json.dumps(frozen, sort_keys=True, default=str),
           "slots_equal_score_py_here": slots == mine}
    (OUT / "p1-2_pipeline_crosscheck.json").write_text(json.dumps(rec, indent=1, default=str) + "\n")
    assert rec["slots_equal_score_py_here"] and rec["every_other_block_equals_the_frozen_summary"], rec
    print("the adjudication's pipeline gives the same \\ptwonum{author-*} values:", slots)


if __name__ == "__main__":
    if sys.argv[1:2] == ["crosscheck-p12"]:
        if sys.argv[2:3] != ["--sealed"] or len(sys.argv) != 4:
            sys.exit("usage: score.py crosscheck-p12 --sealed DIR")
        crosscheck_p12(sys.argv[3])
    else:
        main()
