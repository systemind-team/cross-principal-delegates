#!/usr/bin/env python3
"""Routes, dates and tools per study, from frozen files only, no VM or network.

Writes evidence/v3.14/provenance/runs.json. Every value is read from a frozen file named in its "source" field
(JSON keys directly, README lines by a pattern the script asserts); a value no frozen file records is written as
null with the reason. Revision labels follow evidence/v3.14/provenance/revision_labels.json.
Usage: python3 scripts/freeze/provenance/runs.py
"""
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]


def jload(rel):
    return json.loads((ROOT / rel).read_text())


def readme_line(rel, pattern):
    text = (ROOT / rel).read_text()
    m = re.search(pattern, text)
    assert m, (rel, pattern)
    return m.group(1).strip()


def main():
    sg = jload("evidence/v3.13/single-grid/manifest.json")["derived_from"]
    cells = jload("evidence/v3.13/single-grid/cells.json")["cells"]
    routes1 = sorted({(c["family"], c["transport"], c["configModel"], c["temperature"]) for c in cells})
    net = jload("evidence/v3.13/net-rerun/manifest.json")
    ident = jload("evidence/v3.13/multi-identity/manifest.json")
    told = jload("evidence/v3.13/multi-told/manifest.json")
    labels = jload("evidence/v3.14/provenance/revision_labels.json")
    out = {
        "PAIR I (single-request grid)": {
            "evaluator": {"label": "E1", "commits": labels["E1"]},
            "routes": [{"cells": fam, "transport": tr, "model": model, "temperature": temp} for fam, tr, model, temp in routes1],
            "dates": {"openrouter_cells": "restored from a backup taken 2026-09-19; run dates not recorded in frozen files",
                      "azure_cells": "the voided first attempts are marked 2026-09-22; run dates not recorded in frozen files",
                      "manifest_generated": sg["generated"]},
            "offline_rescore": {"tool": sg["rescore_tool"], "relationship_labels": sg["relationship_labels"],
                                "policy_assets_commit": sg["policy_assets_commit"]},
            "source": "evidence/v3.13/single-grid/manifest.json (derived_from), cells.json",
        },
        "PAIR II probing grid": {
            "evaluator": {"label": "E2", "commits": labels["E2"]},
            "route": readme_line("evidence/v3.14/packing-delivery/README.md", r"used the same model, `([^`]*)`, for both requester and responder")
                     + ", requester and responder; " + readme_line("evidence/v3.14/packing-delivery/README.md", r"- \*\*Route:\*\* ([^\n]*)"),
            "dates": {"R1_sessions_finished_utc": readme_line("evidence/v3.14/packing-delivery/README.md", r"\| 3 per session \|[^\n]*\| ([0-9-]+ [0-9:]+ – [0-9-]+ [0-9:]+) \|"),
                      "whole_grid": "2026-09-23/24 (evidence/v3.14/multi-probing-records/README.md)"},
            "source": "evidence/v3.14/packing-delivery/README.md; evidence/v3.14/multi-probing-records/README.md",
        },
        "PAIR II packing study": {
            "evaluator": {"label": "E2", "commits": labels["E2"]},
            "route": readme_line("evidence/v3.14/packing-delivery/README.md", r"used the same model, `([^`]*)`, for both requester and responder")
                     + ", requester and responder; " + readme_line("evidence/v3.14/packing-delivery/README.md", r"- \*\*Route:\*\* ([^\n]*)"),
            "dates": {"one_per_session": readme_line("evidence/v3.14/packing-delivery/README.md", r"\| 1 per session \|[^\n]*\| ([0-9-]+ [0-9:]+ – [0-9:]+) \|"),
                      "ten_per_session": readme_line("evidence/v3.14/packing-delivery/README.md", r"\| 10 per session \|[^\n]*\| ([0-9-]+ [0-9:]+ – [0-9:]+) \|")},
            "source": "evidence/v3.14/packing-delivery/README.md",
        },
        "PAIR II ladder grid": {
            "evaluator": {"label": "E3", "commits": labels["E3"]},
            "routes": [readme_line("evidence/v3.13/multi-table3/README.md", r"- DeepSeek: ([^\n]*)"),
                       readme_line("evidence/v3.13/multi-table3/README.md", r"- GLM: ([^\n]*)"),
                       readme_line("evidence/v3.13/multi-table3/README.md", r"- Grok: ([^\n]*)")],
            "dates": readme_line("evidence/v3.14/ladder-per-task/README.md", r"\((\d{4}-\d\d-\d\d) run;"),
            "lane": "t3simple (the v3.13 manifest's source field names t3full, a different strict-profile grid)",
            "source": "evidence/v3.13/multi-table3/README.md; evidence/v3.14/ladder-per-task/README.md",
        },
        "PAIR II header comparison": {
            "evaluator": {"label": "E3", "commit": ident["sharedeval_revision"]},
            "route": readme_line("evidence/v3.13/multi-identity/README.md", r"(gateway to OpenRouter, pinned to the `Relace` upstream[^;]*)"),
            "model": ident["model"]["model"], "temperature": ident["model"]["temperature"],
            "dates": readme_line("evidence/v3.13/multi-identity/README.md", r"- \*\*Run:\*\* VM lane `[^`]*`, ([0-9-]+ [0-9:–]+ UTC)"),
            "source": "evidence/v3.13/multi-identity/{manifest.json, README.md}",
        },
        "PAIR II header ladder": {
            "evaluator": {"label": "E3-header", "commit": told["sharedeval_revision"]},
            "route": readme_line("evidence/v3.13/multi-told/README.md", r"- \*\*Model:\*\* ([^\n]*\n[^\n]*)").replace("\n", " "),
            "model": told["model"]["model"], "temperature": told["model"]["temperature"],
            "dates": readme_line("evidence/v3.13/multi-told/README.md", r"- \*\*Run:\*\* VM lane `[^`]*`, ([0-9-]+ [0-9:–]+ UTC)"),
            "untold_reference": readme_line("evidence/v3.13/multi-told/README.md", r"- \*\*Untold reference:\*\* ([^\n]*)"),
            "source": "evidence/v3.13/multi-told/{manifest.json, README.md}",
        },
        "NET run": {
            "evaluator": {"label": "E4", "commit": net["runner"]["sharedeval_source_revision"]},
            "routes": {k: v["route"] for k, v in net["responders"].items()},
            "upstream_provider_pinned": net["upstream_provider_pinned"],
            "dates": {k: v["results_utc"] for k, v in net["responders"].items()},
            "judge": net.get("judge", {}).get("model"),
            "source": "evidence/v3.13/net-rerun/manifest.json",
        },
    }
    dst = ROOT / "evidence/v3.14/provenance/runs.json"
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
