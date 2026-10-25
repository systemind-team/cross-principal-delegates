#!/usr/bin/env python3
"""NET: what the 14 holders' D2 topic policies say about their edges' requesters.

Inputs (frozen): evidence/v3.14/net-world/policies/<holder>.md (scripts/freeze/net_run_files/freeze.py: the D2 POLICY.md
each holder read, equal to the holder's file at SharedEval d44e478) and evidence/v3.13/net-rerun/contacts.jsonl
(each edge's holder, its two requesters and its stratum; the five borderline edges are left out of the analysis).

For each of the 26 requesters the script searches every holder policy for the requester's agent id, full name, first
name and surname (a "dr_" prefix dropped), word-bounded and case-sensitive. Each occurrence is classed by its
sentence:
  recipient  the sentence names who may receive something: "may receive", "can receive", "share ... with",
             "shared with", "disclose ... to", "send ... to", "recipient";
  subject    any other sentence, where the name is part of a protected topic (an example, an item, a section title).
The section each occurrence sits in (the MAY or MUST NOT list of sharing or of actions) is recorded too.
Roles are checked the same way. Each requester's title is the "Asked by" line of the frozen judge inputs
(evidence/v3.14/net-judge-inputs/net_judge_inputs.jsonl, e.g. "Co-founder & CTO at TechFlow AI"); its components (split
on "&", "," and "and", parentheticals dropped, the organisation after " at " kept as its own component) are searched
like the names, acronyms case-sensitively and the rest case-insensitively. The script also lists every
audience-scoping phrase in each policy (sentences with "outside", "external", "third part", "immediate family",
"anyone"), so a reader can see each scope a policy names.

Checks the paper's three statements and writes evidence/v3.14/net-world/policies/policy_check.json:
  1. on the non-borderline edges no holder policy names either of its edge's requesters as a recipient;
  2. the only policy that names any of the 26 requesters as a recipient is the holder's of N-08 (borderline);
  3. the two quoted audience scopes ("outside parties", "anyone outside the SOC") occur verbatim.
Usage: python3 scripts/net_world/policy_check.py
"""
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
POL = ROOT / "evidence/v3.14/net-world/policies"
CONTACTS = ROOT / "evidence/v3.13/net-rerun/contacts.jsonl"
JUDGE = ROOT / "evidence/v3.14/net-judge-inputs/net_judge_inputs.jsonl"
RECIPIENT = re.compile(r"\b(may receive|can receive|share[sd]?\b[^.;]{0,60}?\bwith|shared with|disclosed? [^.;]{0,40}?\bto|"
                       r"send [^.;]{0,40}?\bto|recipients?)\b", re.I)
SCOPE = re.compile(r"\b(outside|external|third[ -]part|immediate family|anyone)\w*", re.I)
QUOTED = ["outside parties", "anyone outside the SOC"]


def forms(agent):
    parts = agent.split("_")
    if parts[0] == "dr":
        parts = parts[1:]
    first, last = parts[0].capitalize(), parts[-1].capitalize()
    return [agent, f"{first} {last}", first, last]


def roles(asked_by):
    """'Asked by: Alex Chen, Co-founder & CTO at TechFlow AI' -> ['Co-founder', 'CTO', 'TechFlow AI']."""
    title = asked_by.split(",", 1)[1].strip() if "," in asked_by else ""
    org = ""
    if " at " in title:
        title, org = title.rsplit(" at ", 1)
    title = re.sub(r"\([^)]*\)", "", title)
    parts = [x.strip() for x in re.split(r"\s*(?:&|,|\band\b)\s*", title) if x.strip()]
    return parts + ([org.strip()] if org.strip() else [])


def role_hit(component, sentence):
    if component.isupper():
        return re.search(r"\b" + re.escape(component) + r"\b", sentence)
    return re.search(r"\b" + re.escape(component) + r"\b", sentence, re.I)


def sentences(text):
    """(section, sentence) pairs: a line under a '## ...' or '... MAY/MUST NOT ...:' header carries that header."""
    section, out = "", []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#") or re.search(r"\b(MAY|MUST NOT)\b.*:$", s):
            section = s.lstrip("# ").rstrip(":")
        for sent in re.split(r"(?<=[.;])\s+", s):
            out.append((section, sent))
    return out


def main():
    contacts = [json.loads(l) for l in open(CONTACTS)]
    edges = collections.defaultdict(lambda: {"requesters": {}, "holder": None, "stratum": None})
    for c in contacts:
        e = edges[c["edge"]]
        e["holder"], e["stratum"] = c["holder"], c["stratum"]
        e["requesters"][c["arm"]] = c["asker"]
    requesters = sorted({a for e in edges.values() for a in e["requesters"].values()})
    holders = sorted({e["holder"] for e in edges.values()})
    titles = {}
    for l in open(JUDGE):
        j = json.loads(l)
        titles.setdefault(j["asker"], j["asked_by_line"])
    assert set(titles) == set(requesters)
    occ, role_occ, scopes = [], [], {}
    for h in holders:
        sents = sentences((POL / f"{h}.md").read_text())
        scopes[h] = sorted({s for _, s in sents if SCOPE.search(s)})
        for r in requesters:
            for section, s in sents:
                hit = next((f for f in forms(r) if re.search(r"\b" + re.escape(f) + r"\b", s)), None)
                if hit:
                    occ.append({"holder": h, "requester": r, "matched": hit, "section": section,
                                "class": "recipient" if RECIPIENT.search(s) else "subject", "sentence": s})
                rhit = next((c for c in roles(titles[r]) if role_hit(c, s)), None)
                if rhit:
                    role_occ.append({"holder": h, "requester": r, "matched": rhit, "section": section,
                                     "class": "recipient" if RECIPIENT.search(s) else "subject", "sentence": s})
    own = []
    for code, e in sorted(edges.items()):
        mine = [o for o in occ if o["holder"] == e["holder"] and o["requester"] in e["requesters"].values()]
        mine_roles = [o for o in role_occ if o["holder"] == e["holder"] and o["requester"] in e["requesters"].values()]
        own.append({"edge": code, "stratum": e["stratum"], "borderline": e["stratum"] == "borderline",
                    "holder": e["holder"], "requesters": e["requesters"],
                    "own_requester_named_as_recipient": sorted({o["requester"] for o in mine if o["class"] == "recipient"}),
                    "own_requester_named_as_subject": sorted({o["requester"] for o in mine if o["class"] == "subject"}),
                    "own_requester_role_as_recipient": sorted({f"{o['requester']}: {o['matched']}" for o in mine_roles
                                                               if o["class"] == "recipient"}),
                    "own_requester_role_mentioned": sorted({f"{o['requester']}: {o['matched']}" for o in mine_roles})})
    recipient_holders = sorted({o["holder"] for o in occ if o["class"] == "recipient"})
    n08_holder = edges["N-08"]["holder"]
    all_text = {h: (POL / f"{h}.md").read_text() for h in holders}
    quoted = {q: sorted(h for h, t in all_text.items() if q in t) for q in QUOTED}
    checks = {
        "1_no_nonborderline_edge_names_its_requester_as_recipient":
            all(not e["own_requester_named_as_recipient"] for e in own if not e["borderline"]),
        "2_only_N-08s_holder_names_any_requester_as_recipient": recipient_holders == [n08_holder],
        "3_quoted_scopes_occur_verbatim": all(quoted[q] for q in QUOTED),
        "4_no_nonborderline_edge_names_its_requesters_role_as_recipient":
            all(not e["own_requester_role_as_recipient"] for e in own if not e["borderline"])}
    out = {"holders": len(holders), "requesters": len(requesters), "edges": len(edges),
           "non_borderline_edges": sum(not e["borderline"] for e in own),
           "edges_whose_own_requester_is_named_as_subject": [e["edge"] for e in own if e["own_requester_named_as_subject"]],
           "holders_naming_a_requester_as_recipient": recipient_holders, "N-08_holder": n08_holder,
           "quoted_scopes": quoted, "checks": checks, "edges_detail": own, "occurrences": occ,
           "role_occurrences": role_occ, "titles": titles, "audience_scope_sentences": scopes}
    (POL / "policy_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("holders", "requesters", "edges", "non_borderline_edges",
                                          "edges_whose_own_requester_is_named_as_subject",
                                          "holders_naming_a_requester_as_recipient", "quoted_scopes", "checks")}, indent=1))
    assert all(checks.values()), checks


if __name__ == "__main__":
    main()
