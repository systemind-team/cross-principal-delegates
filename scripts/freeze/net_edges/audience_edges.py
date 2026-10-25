#!/usr/bin/env python3
"""NET audience-class edges that could be seated. Offline, standard library only.

    python3 scripts/freeze/net_edges/audience_edges.py          # check inputs, print the counts
    python3 scripts/freeze/net_edges/audience_edges.py --write  # also write evidence/v3.14/net-world/audience_edges.json

Reads only files under evidence/v3.14/net-world/ and refuses to run if any of them differs from SHA256SUMS.

The authors' NET summary says that 47 of the 55 audience-class forbidden edges "already have both a seated
member of that class and a matrix-legitimate peer", which would take the paired set from 24 to 71. No script
in SharedEval, the dataset or the paper repository states how 47 was computed, so this script implements the
literal reading (README.md, "Rule"):

  An audience-class edge (forbidden_to is not one of the world's 60 agents) qualifies when
   (i)   its holder is seated in the edge's task and the protected fact sits in a note bundled in the holder's
         data.json, so the edge has a responder and a sensitivity category (the probe loader's own checks);
   (ii)  some seated agent other than the holder belongs to the forbidden audience, so it can act as the
         forbidden requester; and
   (iii) some other seated agent (not the holder, not that member) is labelled L for the fact's category in
         the holder's row of the relational access matrix, so it can act as the permitted requester.
  "Seated" means named as the task's requester or one of its participants. Membership in (ii) is taken only
  where the world records it: the organisation field of systems.json and the relationship field of
  contact_book.json, used as the repository's channel registry binds each label (mechanical modes).

Variants are reported beside the headline: open audiences (everyone, public) holding every agent; membership
not checked at all (an upper bound); requesters drawn from all 60 agents rather than the task's seats; and a
strict form of (iii) in which the permitted requester must not itself belong to the forbidden audience.

Before any of that, the script re-derives the 24 named pairs from the same files with the d44e478 probe
loader's rules (src/suites/pact-net/v2-probes.ts, loadPactNetV2ProbesV1 with arms 'both') and checks them,
edge by edge and requester by requester, against paired_edges_24.json (the rerun's record). That is what
makes "seated" and "matrix-legitimate" here the same predicates the rerun used.
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
import sys

BASE = "evidence/v3.14/net-world"
NET = "world/dataset/pact-net"
CATEGORIES = ("work_public", "sensitive_work", "personal_finance", "personal_health", "personal_relationships")
MECHANICAL = ("organisation", "kinship")


def path(rel):
    return os.path.join(BASE, rel)


def load(rel):
    with open(path(rel), "rb") as fh:
        return json.loads(fh.read())


def verify_inputs():
    sums = {}
    with open(path("SHA256SUMS")) as fh:
        for line in fh:
            digest, rel = line.rstrip("\n").split("  ", 1)
            with open(path(rel), "rb") as f:
                got = hashlib.sha256(f.read()).hexdigest()
            if got != digest:
                sys.exit(f"{rel}: sha256 {got} differs from SHA256SUMS {digest}")
            sums[rel] = digest
    return sums


# ---------------------------------------------------------------------------------------------- world
def holder_notes(agent):
    """The holder's notes, or None where the d44e478 loader would find no store (agentStoreSchema)."""
    p = path(f"{NET}/agent_configs/{agent}/data.json")
    if not os.path.exists(p):
        return None
    d = load(f"{NET}/agent_configs/{agent}/data.json")
    notes = d.get("notes") if isinstance(d, dict) else None
    if not isinstance(d.get("agent"), str) or not d["agent"] or not isinstance(notes, list) or not notes:
        return None
    for n in notes:
        if not all(isinstance(n.get(k), str) and n[k] for k in ("title", "folder", "content")):
            return None
        if n.get("sensitivity") not in CATEGORIES:
            return None
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(BASE):
        sys.exit(f"run from the worktree root ({BASE} not found)")
    sums = verify_inputs()

    tasks = load(f"{NET}/tasks/pact_net_tasks_v2.json")["tasks"]
    matrix = load(f"{NET}/world_design/relational_access_matrix.json")["agents"]
    agents = sorted(load(f"{NET}/world_design/contact_graph.json")["agents"])
    if sorted(matrix) != agents:
        sys.exit("access matrix and contact graph disagree on the agent set")
    org = {x: load(f"{NET}/agent_configs/{x}/systems.json")["organisation"] for x in agents}
    registry = load("registry/channel_registry.json")["channels"]
    paired = load("paired_edges_24.json")["edges"]
    agent_set = set(agents)

    def label(holder, requester, cat):
        return (matrix.get(holder, {}).get("requesters", {}).get(requester) or {}).get(cat)

    def kin(anchor, relationships):
        book = load(f"{NET}/agent_configs/{anchor}/contact_book.json")
        return {e["contactUserId"] for shelf in book.get("books", {}).values() for e in shelf.get("entries", [])
                if e.get("relationship") in relationships}

    def term_members(term, holder, reading):
        """(members, enumerable) of one registry term under a membership reading."""
        mode = term["mode"]
        if reading == "ignored":
            return set(agents), True
        if mode == "organisation":
            return {x for x in agents if org[x] in term["organisations"]}, True
        if mode == "kinship":
            anchor = holder if term.get("anchored_by") == "forbidden.holder" else term["anchor"]
            return kin(anchor, term["relationships"]), True
        return set(), False

    def members(lab, holder, reading):
        ch = registry[lab]
        if reading == "open_all" and ch["mode"] == "open" and lab in ("everyone", "public"):
            return set(agents), "label_semantics"
        terms = ch.get("terms", []) if ch["mode"] == "union" else [ch]
        out, how = set(), []
        for t in terms:
            m, enumerable = term_members(t, holder, reading)
            out |= m
            how.append(t["mode"] + ("" if enumerable else ":not_enumerable"))
        return out, "+".join(how)

    # Registry members must be what the world files produce (the registry's own invariant, re-run here).
    registry_check = {}
    for lab, ch in sorted(registry.items()):
        if ch["mode"] in MECHANICAL:
            holder = next(f["holder"] for t in tasks for f in (t.get("forbidden") or []) if f["forbidden_to"] == lab)
            got = sorted(members(lab, holder, "mechanical")[0])
            registry_check[lab] = {"members": len(got), "equals_registry": got == sorted(ch["members"])}
            if got != sorted(ch["members"]):
                sys.exit(f"registry members for {lab} differ from the world files")
    cited = collections.Counter(f["forbidden_to"] for t in tasks for f in (t.get("forbidden") or [])
                                if f["forbidden_to"] not in agent_set)
    if set(cited) != set(registry):
        sys.exit("registry labels differ from the task file's non-agent audiences")

    # ------------------------------------------- A. the named pairs, with the d44e478 probe loader's rules
    reasons = collections.Counter()
    loader = {}
    for t in tasks:
        actors = [t["requester"], *t["participants"]]
        actor_set = set(actors)
        restricted = {f["forbidden_to"] for f in (t.get("forbidden") or [])}
        for f in t.get("forbidden") or []:
            h, ft = f["holder"], f["forbidden_to"]
            if ft == "everyone":
                reasons["forbidden_to_is_everyone"] += 1; continue
            if ft == h:
                reasons["forbidden_to_equals_holder"] += 1; continue
            if ft not in actor_set:
                reasons["forbidden_to_not_an_actor"] += 1; continue
            if h not in actor_set:
                reasons["holder_not_an_actor"] += 1; continue
            if f.get("evidence_note_title") is None:
                reasons["evidence_outside_bundled_notes"] += 1; continue
            notes = holder_notes(h)
            if notes is None:
                reasons["holder_has_no_store"] += 1; continue
            note = next((n for n in notes if n["title"] == f["evidence_note_title"]), None)
            if note is None:
                reasons["evidence_note_absent_from_holder_store"] += 1; continue
            eligible = [x for x in actors if x != h and x not in restricted]
            if not eligible:
                reasons["no_eligible_contrast_asker"] += 1
                loader[t["id"]] = {"holder": h, "withheld": ft, "permitted": None, "basis": None}
                continue
            legit = [x for x in eligible if label(h, x, note["sensitivity"]) == "L"]
            loader[t["id"]] = {"holder": h, "withheld": ft, "category": note["sensitivity"],
                               "permitted": (legit or eligible)[0],
                               "basis": "matrix_legitimate" if legit else "not_named_forbidden"}
    legit_pairs = {e: v for e, v in loader.items() if v["basis"] == "matrix_legitimate"}
    mismatches = []
    for row in paired:
        v = legit_pairs.get(row["edge"])
        want = (row["holder"], row["withheld_requester"], row["permitted_requester"], row["fact_category"])
        got = v and (v["holder"], v["withheld"], v["permitted"], v["category"])
        if got != want:
            mismatches.append({"edge": row["edge"], "rerun": want, "rederived": got})
    extra = sorted(set(legit_pairs) - {r["edge"] for r in paired})
    named_repro = {
        "rule": "d44e478 src/suites/pact-net/v2-probes.ts loadPactNetV2ProbesV1({arms: 'both'}), re-implemented",
        "rejections": dict(sorted(reasons.items())),
        "probeable_edges": len(loader),
        "paired_with_matrix_legitimate_requester": len(legit_pairs),
        "paired_with_fallback_requester": sum(1 for v in loader.values() if v["basis"] == "not_named_forbidden"),
        "rerun_edges": len(paired),
        "mismatches_with_rerun": mismatches,
        "rederived_but_not_in_rerun": extra,
        "reproduces_rerun_exactly": not mismatches and not extra,
    }

    # ------------------------------------------- B. the 55 audience-class edges
    edges = []
    for t in tasks:
        for f in t.get("forbidden") or []:
            if f["forbidden_to"] in agent_set:
                continue
            h, lab = f["holder"], f["forbidden_to"]
            seats = list(dict.fromkeys([t["requester"], *t["participants"]]))
            notes = holder_notes(h)
            note = None
            if f.get("evidence_note_title") is not None and notes is not None:
                note = next((n for n in notes if n["title"] == f["evidence_note_title"]), None)
            cat = note["sensitivity"] if note else None
            rec = {"task_id": t["id"], "audience": lab, "registry_mode": registry[lab]["mode"],
                   "registry_seatable": registry[lab]["seatable"], "holder": h,
                   "holder_organisation": org.get(h), "holder_seated": h in seats,
                   "evidence_note_title": f.get("evidence_note_title"), "evidence_note_bundled": note is not None,
                   "fact_category": cat, "seated": []}
            mem = {r: members(lab, h, r) for r in ("mechanical", "open_all", "ignored")}
            rec["membership_basis"] = mem["mechanical"][1]
            for x in seats:
                if x == h:
                    continue
                rec["seated"].append({"agent": x, "organisation": org.get(x),
                                      "matrix_label": label(h, x, cat) if cat else None,
                                      "member_mechanical": x in mem["mechanical"][0],
                                      "member_if_open_audiences_hold_everyone": x in mem["open_all"][0]})
            rec["qualifies"] = {}
            for reading, scope, strict in itertools.product(("mechanical", "open_all", "ignored"),
                                                            ("task", "world"), (False, True)):
                ok = False
                if note is not None and (scope == "world" or h in seats):
                    pool = [x for x in seats if x != h] if scope == "task" else [x for x in agents if x != h]
                    ms = [x for x in pool if x in mem[reading][0]]
                    ps = [x for x in pool if label(h, x, cat) == "L" and not (strict and x in mem[reading][0])]
                    ok = any(p != m for m in ms for p in ps)
                rec["qualifies"][f"{reading}/{scope}/{'strict' if strict else 'literal'}"] = ok
            # Why the headline (mechanical/task/literal) says what it says, first failing condition first.
            ms = [s["agent"] for s in rec["seated"] if s["member_mechanical"]]
            ps = [s["agent"] for s in rec["seated"] if s["matrix_label"] == "L"]
            if not rec["holder_seated"]:
                why = "holder not seated in the task"
            elif not rec["evidence_note_bundled"]:
                why = "protected fact not in a bundled note of the holder"
            elif not mem["mechanical"][0]:
                why = f"no agent's membership in '{lab}' is recorded in the world (registry mode {rec['membership_basis']})"
            elif not ms:
                why = f"'{lab}' has {len(mem['mechanical'][0])} member(s) in the world but none is seated in the task"
            elif not ps:
                why = f"no seated agent is labelled L for {cat} by {h}'s matrix row"
            elif not any(p != m for m in ms for p in ps):
                why = "the only seated L agent is the only seated member"
            else:
                inside = [p for p in ps if p in mem["mechanical"][0]]
                why = (f"qualifies: seated member(s) {ms}; seated L for {cat}: {ps}"
                       + (f"; every seated L agent is itself in '{lab}', so the strict form fails" if inside == ps else ""))
            rec["headline_reason"] = why
            edges.append(rec)

    def count(key):
        return sorted(e["task_id"] for e in edges if e["qualifies"][key])

    keys = [f"{r}/{s}/{k}" for r in ("mechanical", "open_all", "ignored") for s in ("task", "world")
            for k in ("literal", "strict")]
    counts = {k: {"n": len(count(k)), "edges": count(k)} for k in keys}
    headline = counts["mechanical/task/literal"]

    # Diagnostics: how far condition (iii) alone gets, and what 47 would need.
    seated_l = sorted(e["task_id"] for e in edges if e["holder_seated"] and e["evidence_note_bundled"]
                      and any(s["matrix_label"] == "L" for s in e["seated"]))

    def any_cat(e, labels):
        return any(label(e["holder"], s["agent"], c) in labels for s in e["seated"] for c in CATEGORIES)

    def relaxed(labels):
        return sorted(e["task_id"] for e in edges
                      if e["audience"] != "everyone" and e["holder_seated"] and any_cat(e, labels))
    recon_l, recon_lb = relaxed(("L",)), relaxed(("L", "B"))
    diagnostics = {
        "audience_edges_with_a_seated_L_requester_for_the_fact_category": {
            "n": len(seated_l), "edges": seated_l,
            "meaning": "condition (iii) with (i), membership not checked: the ceiling for any reading that keeps "
                       "the summary's own 'legitimate for that material' test and the task's seats"},
        "post_hoc_combination_that_gives_47": {
            "n": len(recon_l), "edges": recon_l,
            "n_if_B_also_counts": len(recon_lb),
            "dropped": sorted({e["task_id"] for e in edges} - set(recon_l)),
            "rule": "holder seated; some seated agent labelled L (or, second count, L or B) by the holder's matrix "
                    "row for ANY category, not the fact's; no class-membership test; the four 'everyone' edges "
                    "dropped (the probe loader rejects that label first)",
            "caveat": "Found by searching combinations of relaxed conditions for one that lands on 47. It shows "
                      "what 47 would require, not what the authors did; no source states this rule."},
    }
    recon = recon_l
    out = {
        "what": "NET audience-class forbidden edges that already have a seated class member and a permitted "
                "requester, and the paired set they give",
        "inputs_sha256": sums,
        "rule_headline": "mechanical/task/literal: (i) holder seated and fact in a bundled holder note; (ii) a seated "
                         "non-holder agent belongs to the audience, membership as the world records it (systems.json "
                         "organisation, contact_book.json relationship; channel registry modes); (iii) another seated "
                         "agent is L for the fact's category in the holder's access-matrix row",
        "variant_keys": "<membership reading>/<who can act as a requester>/<form of (iii)>; membership reading: "
                        "mechanical (headline), open_all (everyone and public hold all 60 agents), ignored (every "
                        "agent is a member: upper bound); requester: task (seated in the task; holder seated), world "
                        "(any of the 60 agents other than the holder; holder need not be seated); form: literal, or "
                        "strict (the permitted requester must not belong to the audience)",
        "named_edge_reproduction": named_repro,
        "registry_member_check": registry_check,
        "audience_edges": len(edges),
        "audience_labels": len(cited),
        "headline": {"qualifying": headline["n"], "edges": headline["edges"],
                     "paired_set": len(paired) + headline["n"],
                     "strict_qualifying": counts["mechanical/task/strict"]["n"],
                     "strict_paired_set": len(paired) + counts["mechanical/task/strict"]["n"]},
        "authors_claim": {"qualifying": 47, "paired_set": 71, "source": "summary/pact_net_summary.tex, Future work"},
        "counts": counts,
        "diagnostics": diagnostics,
        "edges": edges,
    }
    print(f"inputs: {len(sums)} files match SHA256SUMS")
    print(f"named edges: {named_repro['probeable_edges']} probeable, {named_repro['paired_with_matrix_legitimate_requester']} "
          f"with a matrix-legitimate requester; rerun's 24 reproduced exactly: {named_repro['reproduces_rerun_exactly']}")
    print(f"audience-class edges: {len(edges)} over {len(cited)} labels")
    print(f"HEADLINE (literal reading, mechanical membership, seated): {headline['n']} {headline['edges']} "
          f"-> paired set {len(paired)} + {headline['n']} = {len(paired) + headline['n']}")
    for k in keys:
        print(f"  {k:28s} {counts[k]['n']:3d}")
    print(f"ceiling, (i)+(iii) only: {len(seated_l)}; post-hoc 47 combination: {len(recon)}")
    if a.write:
        with open(path("audience_edges.json"), "w") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("wrote", path("audience_edges.json"))


if __name__ == "__main__":
    main()
