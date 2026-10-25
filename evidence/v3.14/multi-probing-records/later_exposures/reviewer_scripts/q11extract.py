import json, glob, os, collections, sys
R="$RUNS"
DS=json.load(open("$SHAREDEVAL/dataset/pact-pair/tasks/questions.json"))
Q={f"PAIR-Q{q['id']}":q for q in DS["questions"]}
inst={}
for p in sorted(glob.glob(f"{R}/grid600/acc/G6-*/contacts.local.jsonl")):
    rid=p.split("/")[-2]
    for l in open(p):
        r=json.loads(l)
        if r["kind"]!="qa" or r["expectedBehavior"]!="refuse": continue
        inst.setdefault((rid,r["taskId"]),[]).append(r)
out=[]
for (rid,tid),cs in sorted(inst.items()):
    cs=sorted(cs,key=lambda r:(r["attempt"],r["tick"]))
    if cs[0].get("targetDisclosure"): continue
    if not any(c.get("targetDisclosure") for c in cs): continue
    q=Q[tid]
    out.append({"case":len(out)+1,"runId":rid,"requester":rid.split("-")[1],"taskId":tid,"category":q["category"],
                "question":q["question"],"gold":q["gold_key_facts"],
                "firstAsk":{"request":cs[0]["requestText"],"response":cs[0]["response"],"memoryStatus":cs[0]["memoryStatus"]},
                "terminalStatus":cs[-1]["memoryStatus"],
                "disclosing":[{"attempt":c["attempt"],"strategy":c.get("claimedStrategy"),"memoryStatus":c["memoryStatus"],
                               "matchedGoldIdx":c.get("ownFactMatchIndices"),"request":c["requestText"],"response":c["response"]}
                              for c in cs if c.get("targetDisclosure")]})
print(len(out), file=sys.stderr)
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
