import json, sys
d=json.load(open("q11cases.json"))
lo,hi=int(sys.argv[1]),int(sys.argv[2]); maxc=int(sys.argv[3]) if len(sys.argv)>3 else 1800
for x in d[lo-1:hi]:
    print(f"\n######## CASE {x['case']} {x['runId']} {x['taskId']} [{x['category']}] terminal={x['terminalStatus']}")
    print("Q:", x["question"]); print("GOLD:", " | ".join(f"[{i}] {g}" for i,g in enumerate(x["gold"])))
    print("FIRST-ASK reply (no match):", (x["firstAsk"]["response"] or "")[:300].replace("\n"," "))
    for c in x["disclosing"]:
        print(f"  -- attempt {c['attempt']} {c['strategy']} mem={c['memoryStatus']} matched={c['matchedGoldIdx']}")
        print("     REQ:", (c["request"] or "")[:200].replace("\n"," "))
        print("     REPLY:", (c["response"] or "")[:maxc].replace("\n"," "))
