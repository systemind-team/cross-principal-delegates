import json,re,sys
d=json.load(open("q11cases.json"))
lo,hi=int(sys.argv[1]),int(sys.argv[2])
for x in d[lo-1:hi]:
    print(f"\n######## CASE {x['case']} {x['runId']} {x['taskId']} [{x['category']}] ndisc={len(x['disclosing'])}")
    print("Q:", x["question"]); print("GOLD:", " | ".join(f"[{i}] {g}" for i,g in enumerate(x["gold"])))
    keys=[w for g in x["gold"] for w in re.findall(r"[A-Za-z0-9$%.,/&-]{3,}", g.lower()) if w not in ("and","the","for","with","her","his","per")]
    for c in x["disclosing"]:
        t=(c["response"] or "")
        sents=[s for s in re.split(r"(?<=[.!?])\s+|\n+", t) if any(k in s.lower() for k in keys)]
        print(f"  -- att{c['attempt']} {c['strategy']} matched={c['matchedGoldIdx']} | REQ: {(c['request'] or '')[:130]}")
        for s in sents[:5]: print("       >", s[:300].replace("\n"," "))
