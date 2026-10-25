#!/usr/bin/env python3
"""The NET world counts behind Appendix E's world table, from the world frozen at d44e478.

Inputs: evidence/v3.14/net-world/ (byte-identical copies of the d44e478 world; the script stops if any file differs
from SHA256SUMS) and the probe funnel that scripts/freeze/net_edges/audience_edges.py re-derives with the d44e478
loader's rules (evidence/v3.14/net-world/audience_edges.json).
Counts: agents; directed contact links and their mean per holder; access-matrix cells by label; tasks, seated agents
per task (requester plus participants); topologies; tasks tagged chain; forbidden edges naming an agent or an
audience; executable-core tasks; the probe funnel (probeable, paired, non-borderline).
Output: evidence/v3.14/net-world/counts.json
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "freeze", "net_edges"))
os.chdir(ROOT)
import audience_edges  # noqa: E402

BASE = "evidence/v3.14/net-world"
NET = os.path.join(BASE, "world/dataset/pact-net")


def load(rel):
    return json.load(open(os.path.join(NET, rel)))


def main():
    audience_edges.verify_inputs()
    cg = load("world_design/contact_graph.json")
    matrix = load("world_design/relational_access_matrix.json")["agents"]
    tasks_file = load("tasks/pact_net_tasks_v2.json")
    tasks = tasks_file["tasks"]
    agents = cg["agents"]
    links = sum(len(v) for v in cg["contacts"].values())
    assert links == cg["graph_stats"]["total_edges"]
    cells = collections.Counter(v for h in matrix.values() for req in h["requesters"].values()
                                for c, v in req.items() if c != "notes")
    seated = [1 + len(t["participants"]) for t in tasks]
    topo = collections.Counter(t["topology"] for t in tasks)
    chain = sum("chain" in (t.get("tags") or []) for t in tasks)
    forb = [f for t in tasks for f in (t.get("forbidden") or [])]
    agent_set = set(agents)
    named = sum(f["forbidden_to"] in agent_set for f in forb)
    audiences = collections.Counter(f["forbidden_to"] for f in forb if f["forbidden_to"] not in agent_set)
    ae = json.load(open(os.path.join(BASE, "audience_edges.json")))
    funnel = ae["named_edge_reproduction"]
    assert funnel["reproduces_rerun_exactly"]
    paired = json.load(open(os.path.join(BASE, "paired_edges_24.json")))["edges"]
    out = {
        "agents": len(agents),
        "directed_links": links, "links_per_holder_mean": links / len(agents),
        "access_cells": sum(cells.values()), "access_cells_by_label": dict(sorted(cells.items())),
        "tasks": len(tasks), "seated_per_task_mean": sum(seated) / len(seated), "seated_per_task_min": min(seated),
        "topologies": dict(topo), "all_fan_out": all(k.startswith("A→{") for k in topo),
        "tasks_tagged_chain": chain,
        "forbidden_edges": len(forb), "forbidden_to_agent": named, "forbidden_to_audience": sum(audiences.values()),
        "audiences": dict(sorted(audiences.items())),
        "executable_core_tasks": tasks_file["executable_core"]["task_count"],
        "probeable_edges": funnel.get("probeable_edges"),
        "paired_edges": len(paired),
        "paired_matrix_legitimate": sum(1 for e in paired if e.get("basis", "matrix_legitimate") == "matrix_legitimate"),
        "paired_non_borderline": sum(not e["borderline"] for e in paired),
    }
    with open(os.path.join(BASE, "counts.json"), "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("topologies", "audiences")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
