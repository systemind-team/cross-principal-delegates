import json, sys
d=json.load(open("q11cases.json"))
for cid in map(int, sys.argv[1].split(",")):
    x=d[cid-1]; print(f"######## CASE {cid} {x['taskId']} GOLD {x['gold']}")
    for c in x["disclosing"][1:]:
        print("--", c["attempt"], c["strategy"], c["matchedGoldIdx"], "| REQ:", (c["request"] or "")[:120])
        print("  ", (c["response"] or "")[:int(sys.argv[2]) if len(sys.argv)>2 else 1000].replace("\n"," "))
