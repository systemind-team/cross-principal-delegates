#!/usr/bin/env python3
"""P1-6: the cause of every attempt that exited with an error (read only, on the VM): run id, exit code and the
harness's runner-error cause from the attempt's log.

Usage (VM): python3 failures_vm.py <lane dir> > failures.tsv
"""
import re
import sys

L = sys.argv[1]
print("run_id\texit_code\tcause")
for line in open(f"{L}/times.tsv"):
    rid, _, _, rc = line.rstrip("\n").split("\t")
    if rc == "0":
        continue
    cause = "not found"
    for row in open(f"{L}/logs/{rid}.log", errors="replace"):
        m = re.search(r"Sharedeval runner error: .*?\(cause: ([a-z_]+)\)", row)
        if m:
            cause = m.group(1)
            break
    print(f"{rid}\t{rc}\t{cause}")
