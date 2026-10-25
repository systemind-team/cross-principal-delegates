import json, sys
d=json.load(open("q11cases.json"))
lo,hi=int(sys.argv[1]),int(sys.argv[2]); maxc=int(sys.argv[3]) if len(sys.argv)>3 else 1400; k=int(sys.argv[4]) if len(sys.argv)>4 else 2
for x in d[lo-1:hi]:
    print(f"\n######## CASE {x['case']} {x['runId']} {x['taskId']} [{x['category']}] terminal={x['terminalStatus']} ndisc={len(x['disclosing'])}")
    print("Q:", x["question"]); print("GOLD:", " | ".join(f"[{i}] {g}" for i,g in enumerate(x["gold"])))
    for c in x["disclosing"][:k]:
        print(f"  -- att{c['attempt']} {c['strategy']} mem={c['memoryStatus']} matched={c['matchedGoldIdx']} | REQ: {(c['request'] or '')[:140]}")
        print("     REPLY:", (c["response"] or "")[:maxc].replace("\n"," "))
