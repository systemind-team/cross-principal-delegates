#!/usr/bin/env python3
"""Kernel check: the refusal and failure texts a kernel can hand back in a tool or message result, K2 vs K1.

Reads each built kernel's packages/core/dist/kernel.js and collects the string literals (code and message) of every call to
deniedToolResult, failedToolResult, deniedResourceResult, failedResourceResult and protocolError (the result
builders whose text reaches the turn driver), plus each builder's own source. Prints whether the message sets
and the builder bodies are equal, and anything that is in one kernel only.
Usage: compare_denial_messages.py <K2 build> <K1 build>
"""
import json
import re
import sys

BUILDERS = ("deniedToolResult", "failedToolResult", "deniedResourceResult", "failedResourceResult", "protocolError")
# a builder call with its arguments (string literals and one level of nested parentheses allowed)
CALL = re.compile(r"\b(" + "|".join(BUILDERS) + r")\(((?:\"[^\"]*\"|[^()\"]|\([^()]*\))*)\)")
LIT = re.compile(r"\"([^\"]*)\"")


def scan(path):
    src = open(path).read()
    msgs = sorted({(m.group(1), " | ".join(LIT.findall(m.group(2)))) for m in CALL.finditer(src)
                   if LIT.findall(m.group(2))})
    bodies = {}
    for b in BUILDERS[:4]:
        m = re.search(r"function " + b + r"\([^)]*\)\s*\{.*?\n\}", src, re.S)
        bodies[b] = m.group(0) if m else None
    return msgs, bodies


def main(k2, k1):
    m2, b2 = scan(f"{k2}/packages/core/dist/kernel.js")
    m1, b1 = scan(f"{k1}/packages/core/dist/kernel.js")
    out = {
        "messages_k2": len(m2), "messages_k1": len(m1), "message_sets_equal": m2 == m1,
        "only_k2": [list(x) for x in sorted(set(m2) - set(m1))], "only_k1": [list(x) for x in sorted(set(m1) - set(m2))],
        "builder_bodies_equal": {b: (b1[b] is not None and b1[b] == b2[b]) for b in BUILDERS[:4]},
    }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
