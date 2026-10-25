#!/usr/bin/env python3
"""Acceptance: the frozen attacker and control heartbeats are generated from one template, so a
line-level diff shows only the attacker-only passages (the policy, the menu and the tactic instructions marked
by the template's <<AD>> blocks), and every line the control keeps is byte-identical to the attacker's. The
shared protocol — statuses, phases, finalization, the `tried=` selection rule — is therefore the same for both
arms, so the arms share one budget per task. No model calls.

The check is structural, not keyword-based: it recomputes the exact set of AD-block lines from the template and
asserts the attacker-only inserted lines are exactly those. It also runs build_frozen.py --check (the frozen
files reproduce from the template) and asserts the control names no tactic, menu or policy.

Usage: python3 scripts/pair_multi/spoof/adaptive/test_heartbeats_diff.py
"""
import collections
import difflib
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_frozen as bf # noqa: E402

FROZEN = HERE.parents[3] / "evidence/v3.14/multi-adaptive/frozen"


def nonblank(lines):
    return collections.Counter(x for x in lines if x.strip())


def main():
    r = subprocess.run([sys.executable, str(HERE / "build_frozen.py"), "--check"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("build_frozen --check failed:\n" + r.stdout + r.stderr)
    print("ok:", r.stdout.strip())

    attacker = (FROZEN / "HEARTBEAT.md").read_text().splitlines()
    control = (FROZEN / "HEARTBEAT-control.md").read_text().splitlines()
    template = (bf.SRC / "HEARTBEAT.template.md").read_text()
    menu = (bf.SRC / "menu.md").read_text()
    subs = {"POLICY": "```\n" + bf.POLICY.read_text().rstrip() + "\n```", "MENU": menu.rstrip()}
    ad_only, _ = bf.render(template, None, subs, only="AD")
    ct_only, _ = bf.render(template, None, subs, only="CT")
    ad_lines, ct_lines = nonblank(ad_only.splitlines()), nonblank(ct_only.splitlines())

    # (b) every line the two heartbeats differ on is explained by exactly one <<AD>> or <<CT>> block: an
    # attacker-only line is an AD-block line, a control-only line is a CT-block line.
    sm = difflib.SequenceMatcher(a=control, b=attacker, autojunk=False)
    attacker_only, control_only = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            attacker_only += attacker[j1:j2]
        if tag in ("delete", "replace"):
            control_only += control[i1:i2]
    got_ad, got_ct = nonblank(attacker_only), nonblank(control_only)
    if got_ad != ad_lines:
        sys.exit("attacker-only lines are not exactly the AD blocks.\n"
                 f" unexpected: {list((got_ad - ad_lines).elements())!r}\n"
                 f" AD lines missing: {list((ad_lines - got_ad).elements())!r}")
    if got_ct != ct_lines:
        sys.exit("control-only lines are not exactly the CT blocks.\n"
                 f" unexpected: {list((got_ct - ct_lines).elements())!r}\n"
                 f" CT lines missing: {list((ct_lines - got_ct).elements())!r}")
    shared = sum(1 for tag, i1, i2, _, _ in sm.get_opcodes() if tag == "equal" for _ in control[i1:i2])
    print(f"ok: {shared} shared lines; the only differences are the AD blocks (attacker) and the CT block (control)")
    print(f"ok: attacker-only = {sum(got_ad.values())} AD-block lines; control-only = {sum(got_ct.values())} CT-block lines")

    control_text = "\n".join(control).lower()
    for banned in ("tactic=", "## tactics", "verified caller", "responder's policy"):
        if banned in control_text:
            sys.exit(f"control heartbeat still names {banned!r}")
    if "ask plainly" not in control_text or "no claim of identity" not in control_text:
        sys.exit("control heartbeat lost its plain-asking instruction")
    print("ok: the control names no tactic/menu/policy and keeps the plain-asking instruction")
    print("all heartbeat-diff checks passed")


if __name__ == "__main__":
    main()
