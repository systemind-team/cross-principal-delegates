#!/usr/bin/env python3
"""P2-3: build and freeze the attacker and control heartbeats from one template, and set the attacker upstream
slug and recompute the manifest. No model calls.

The control heartbeat is generated from the SAME template as the attacker heartbeat, so its self-references,
statuses, phases, finalization and the `tried=` task-selection rule are identical; only the tactic/policy/menu
parts are removed and the plain-asking instruction is added. The template
`frozen/sources/HEARTBEAT.template.md` marks the attacker-only lines with whole-line `<<AD>>` / `<</AD>>`
fences, the control-only lines with `<<CT>>` / `<</CT>>`, and the two inlined blocks with `{{POLICY}}` and
`{{MENU}}`:
  - the attacker heartbeat keeps the AD lines (fences stripped) and substitutes the policy and menu;
  - the control heartbeat keeps the CT lines and drops the AD ones, and never mentions a tactic, policy or menu.
A diff of the two frozen heartbeats therefore shows only the AD and CT passages (test_heartbeats_diff.py).

The template uses only the runtime statuses [answered]/[pending]/[refused]; the private tactic lives in the
MEMORY note as `tactic=`. The parser at 8081e7e accepts only pending|answered|refused|error.

The runtime mounts only four workspace files, so the responder policy (D2R_ID_R0) and the tactic menu are
INLINED into the attacker heartbeat, and nowhere in the control. The policy text is read from the frozen
D2R_ID_R0.md (the file the responder runs), never pasted here.

Sources (frozen/sources/; the policy text is not among them):
  HEARTBEAT.template.md   the one heartbeat, with <<AD>>..<</AD>> fences and {{POLICY}}/{{MENU}} placeholders
  menu.md                 the tactic menu, substituted into {{MENU}}
Input: evidence/v3.14/multi-spoof/inputs/D2R_ID_R0.md (the responder policy), sha 8100ecea...

Outputs (frozen/): HEARTBEAT.md, HEARTBEAT-control.md, menu.md (the inlined menu, kept for the supplement),
model_config.json (slug filled when --attacker-upstream is given), MANIFEST.json (digests).

Usage:
  python3 build_frozen.py                              # (re)build the heartbeats and the manifest
  python3 build_frozen.py --attacker-upstream <slug>   # also set the Gemini upstream slug and re-freeze
  python3 build_frozen.py --check                       # rebuild into memory and fail if the frozen files differ
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN = ROOT / "evidence/v3.14/multi-adaptive/frozen"
SRC = FROZEN / "sources"
POLICY = ROOT / "evidence/v3.14/multi-spoof/inputs/D2R_ID_R0.md"
POLICY_SHA = "8100eceaa8e2952e42c6630f1ce6d816e8e7f6d9253fd70c372c11b729f89788"
# Block fences. An <<AD>> block appears in the attacker heartbeat only (the tactics, policy and menu); a
# <<CT>> block in the control heartbeat only (the plain-asking instruction). Each fence must be
# alone on its line, and blocks do not nest.
FENCES = {"AD": ("<<AD>>", "<</AD>>"), "CT": ("<<CT>>", "<</CT>>")}


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


# Internal references that must never reach a model (export scrub): host rulings, reviewer ids
# (R1-R7, action items A1-A12), seat names (W1-W6), room seq numbers, item ids (P1-x/P2-x) and "design
# review". The reviewer/action patterns are written NOT to match legitimate task ids such as PAIR-Q7 or
# PAIR-A50 (an A-item must not be preceded by a letter, digit or hyphen) or the lower-case word "requester".
SCRUB_PATTERNS = [
    (r"(?i)\bhost ruling", "host ruling"),
    (r"(?i)\bdesign review", "design review"),
    (r"(?i)\breviewer\b", "reviewer"),
    (r"(?<![\w-])R[1-7]\b", "reviewer id R1-R7"),            # R1, R3 ... but not PAIR-... or requester
    (r"(?<![\w-])A(?:[1-9]|1[0-2])\b", "action item A1-A12"),  # A1..A12 but not PAIR-A50
    (r"(?<![\w-])W[1-6]\b", "seat name W1-W6"),
    (r"(?i)\bseq(?:uence)?\.?\s*#?\s*\d+", "room seq number"),
    (r"\bP[12]-\d", "item id P1-x/P2-x"),
]


def scan_internal_refs(text):
    """Return a list of (label, matched snippet) for every internal reference in `text` (must be empty)."""
    import re as _re
    hits = []
    for pat, label in SCRUB_PATTERNS:
        for m in _re.finditer(pat, text):
            i = m.start()
            hits.append((label, text[max(0, i - 25):m.end() + 15].replace("\n", " ")))
    return hits


def render(template, variant, subs, only=None):
    """Resolve the template for `variant` ("attacker" keeps AD, drops CT; "control" keeps CT, drops AD). A
    {{NAME}} placeholder is substituted only when its block is kept. `only` ("AD" or "CT") instead returns just
    that block kind's lines (for the diff test). Returns (text, {"AD": n, "CT": n} block counts)."""
    keep = {"attacker": "AD", "control": "CT"}.get(variant) if only is None else None
    out, stack, counts = [], [], {"AD": 0, "CT": 0}
    for line in template.splitlines(keepends=True):
        s = line.strip()
        opened = next((k for k, (o, _) in FENCES.items() if s == o), None)
        closed = next((k for k, (_, c) in FENCES.items() if s == c), None)
        if opened:
            stack.append(opened)
            counts[opened] += 1
            continue
        if closed:
            if not stack or stack[-1] != closed:
                raise ValueError(f"unbalanced {closed} fence")
            stack.pop()
            continue
        cur = stack[-1] if stack else None
        if only is not None:
            if cur == only:
                out.append(line)
            continue
        if cur is not None and cur != keep:
            continue  # a block belonging to the other variant
        out.append(line)
    if stack:
        raise ValueError(f"unclosed {stack[-1]} fence")
    text = "".join(out)
    kept_block = only if only is not None else keep
    for name, value in subs.items():
        token = "{{" + name + "}}"
        # placeholders live in AD blocks; present only when AD content is kept (attacker, or only="AD")
        if kept_block == "AD":
            if token not in text:
                raise ValueError(f"placeholder {token} not found")
            text = text.replace(token, value)
        elif token in text:
            raise ValueError(f"placeholder {token} leaked into a non-attacker rendering")
    if only is None:
        text = re.sub(r"\n\n\n+", "\n\n", text)  # collapse a blank gap a dropped block leaves
    return text, counts


def build(check=False):
    assert sha(POLICY) == POLICY_SHA, "D2R_ID_R0.md is not the frozen responder policy"
    template = (SRC / "HEARTBEAT.template.md").read_text()
    menu = (SRC / "menu.md").read_text()
    subs = {"POLICY": "```\n" + POLICY.read_text().rstrip() + "\n```", "MENU": menu.rstrip()}
    attacker, counts = render(template, "attacker", subs)
    control, _ = render(template, "control", subs)
    if counts["AD"] == 0 or counts["CT"] == 0:
        raise ValueError("the template must have both <<AD>> and <<CT>> blocks")
    # the control must mention no tactic, menu or policy, and must keep the plain-asking instruction
    for banned in ("tactic=", "## Tactics", "responder's policy", "Verified caller"):
        if banned in control:
            raise ValueError(f"control heartbeat still contains {banned!r}")
    if "Ask plainly" not in control or "no claim of identity" not in control:
        raise ValueError("control heartbeat lost its plain-asking instruction")
    # scrub: no internal reference may reach a model. Scan everything a model sees — the attacker heartbeat
    # (which inlines the policy and the menu), the control heartbeat, and the menu copy.
    for name, text in (("HEARTBEAT.md", attacker), ("HEARTBEAT-control.md", control), ("menu.md", menu)):
        hits = scan_internal_refs(text)
        if hits:
            raise ValueError(f"{name} contains internal references a model would read: {hits}")
    outputs = {"HEARTBEAT.md": attacker, "HEARTBEAT-control.md": control, "menu.md": menu}
    if check:
        bad = {f: (sha(FROZEN / f) if (FROZEN / f).exists() else None,
                   hashlib.sha256(v.encode()).hexdigest()) for f, v in outputs.items()
               if not (FROZEN / f).exists() or (FROZEN / f).read_text() != v}
        return bad
    for f, v in outputs.items():
        (FROZEN / f).write_text(v)
    return {}


def set_upstream(slug):
    cfg = json.loads((FROZEN / "model_config.json").read_text())
    cfg["attacker"]["providerRouting"] = {"order": [slug], "only": [slug], "allowFallbacks": False}
    cfg["attacker"]["providerRouting_note"] = (
        f"pinned to the single OpenRouter provider '{slug}' serving gemini-2.5-flash through the gateway, chosen "
        "from the public endpoints list (evidence/v3.14/multi-adaptive/upstream_check/endpoints.json; host: prefer "
        "google-vertex, alternative google-ai-studio). SharedEval records OpenRouter's display name, so the "
        "per-call check compares it to this slug through PROVIDER_ALIASES (delivery_adaptive.py).")
    (FROZEN / "model_config.json").write_text(json.dumps(cfg, indent=1) + "\n")


def write_manifest():
    files = ["HEARTBEAT.md", "HEARTBEAT-control.md", "menu.md", "model_config.json"]
    cfg = json.loads((FROZEN / "model_config.json").read_text())
    slug = cfg["attacker"]["providerRouting"]["only"][0]
    man = {
        "about": "Frozen P2-3 attacker artifacts. Pinned before the pilot; any change after "
                 "the pilot makes a new arm. The attacker and control heartbeats are built from one template "
                 "(frozen/sources/HEARTBEAT.template.md) so their protocol is identical; HEARTBEAT.md inlines "
                 "the responder policy (D2R_ID_R0) and the tactic menu, since the runtime mounts only four "
                 "workspace files. Built by scripts/pair_multi/spoof/adaptive/build_frozen.py.",
        "attacker_upstream_set": slug != "<attacker upstream>",
        "frozen_2026_10_24": {f: sha(FROZEN / f) for f in files},
        "sources": {f"sources/{f}": sha(SRC / f) for f in ("HEARTBEAT.template.md", "menu.md")},
        "inlined_policy": {"path": str(POLICY.relative_to(ROOT)), "sha256": POLICY_SHA},
    }
    (FROZEN / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacker-upstream")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        bad = build(check=True)
        if bad:
            print(json.dumps({"stale": {f: {"frozen": a, "rebuilt": b} for f, (a, b) in bad.items()}}, indent=1))
            sys.exit("frozen heartbeats differ from the template; run build_frozen.py")
        print("frozen heartbeats reproduce from the template")
        return
    build()
    if args.attacker_upstream:
        set_upstream(args.attacker_upstream)
    print(json.dumps(write_manifest(), indent=1))


if __name__ == "__main__":
    main()
