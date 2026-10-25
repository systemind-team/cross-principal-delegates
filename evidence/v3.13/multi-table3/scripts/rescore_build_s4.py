import json, glob, os, collections
base = "<vm>/runs/t3simple"; os.chdir(base)
src = open("analyze_s4.py").read(); cut = src.index("# per (cell, group, task) evaluation"); g = {}; exec(src[:cut], g)
choice = g["choice"]; kindof = g["kindof"]; TASKS = g["TASKS"]
DS = json.load(open("<vm>/repos/SharedEval-a1/dataset/pact-pair/tasks/questions.json"))
Q = {"PAIR-Q%s" % q["id"]: q for q in DS["questions"]}
items = []
policy_cache = {}
for (b, p, r, gr), m in choice.items():
    if m is None: continue
    run_root = m[:-len("/multi")]
    pol = policy_cache.get(run_root)
    if pol is None:
        ps = glob.glob(run_root + "/workspaces/runs/*/workspaces/responder/versions/*/POLICY.md")
        pol = open(ps[0]).read() if ps else ""
        policy_cache[run_root] = pol
    evs = {}
    for l in open(m + "/results.jsonl"):
        row = json.loads(l); evs[row["taskId"]] = row
    msgs = collections.defaultdict(list)
    for f in glob.glob(m + "/.sharedeval-sharedos-session/messages/record-*.json"):
        rec = json.load(open(f)); e = rec["envelope"]; pl = e["payload"]
        msgs[pl.get("taskId")].append((rec["sequence"], e["sender"]["agentId"], pl.get("message") if e["sender"]["agentId"] == "requester" else (pl.get("response") or "")))
    for t in TASKS[gr]:
        if kindof(t) != "qa_refuse": continue
        row = evs.get(t); pe = (row or {}).get("publicEvaluation")
        if pe is None: continue
        steps = [{"who": w, "text": x or ""} for s, w, x in sorted(msgs.get(t, []))]
        items.append({"key": [b, p, r, gr, t], "gold": Q[t]["gold_key_facts"], "policy": pol,
                      "steps": steps, "decision": pe.get("actualDecision"), "leaked": bool(pe.get("benchmarkLeaked"))})
json.dump(items, open("/tmp/s4_rescore_in.json", "w"), ensure_ascii=False)
print("items", len(items), "leaked", sum(i["leaked"] for i in items))
