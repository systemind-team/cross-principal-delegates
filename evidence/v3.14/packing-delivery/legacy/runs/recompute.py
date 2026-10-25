#!/usr/bin/env python3
"""跑完后重算：装载三点（1/3/10，全 scoped）+ 模型大样本。"""
import json, glob, os, collections, statistics
R="<vm>/runs"
DS=json.load(open("<vm>/repos/SharedEval-a1/dataset/pact-pair/tasks/questions.json"))
CAT={c["id"]:c for c in DS["categories"]}
Q={f"PAIR-Q{q['id']}":q for q in DS["questions"]}
A={f"PAIR-A{a['id']}":a for a in DS["actions"]}
def kindof(t):
    if t in Q: return "qa_"+CAT[Q[t]["category"]]["expected_m2"]
    if t in A: return "act_"+("auth" if A[t]["category"].startswith("authorized") else "unauth")
    return "?"
def collect(paths, taskfilter=None, reqfilter=None):
    tasks=collections.defaultdict(list); un=0; tot=0
    for d in paths:
        try:
            s=json.load(open(d+"/summary.json")); u=s.get("usage") or {}
            if not (s.get("evaluationRows")==s.get("selectedTasks") and (u.get("contactCalls") or 0)>0): continue
            rj=json.load(open(d+"/run.json"))
        except Exception: continue
        rid=os.path.basename(os.path.dirname(d))
        if reqfilter and f"-{reqfilter}-" not in rid: continue
        for l in open(d+"/results.jsonl"):
            r=json.loads(l); tot+=1; pe=r.get("publicEvaluation")
            if pe is None: un+=1; continue
            if taskfilter and pe["taskId"] not in taskfilter: continue
            tasks[pe["taskId"]].append(pe)
    return tasks, un, tot
def mt(tasks, keep=None):
    acc=collections.defaultdict(lambda:[0,0])
    for tid,pes in tasks.items():
        if keep is not None and tid not in keep: continue
        k=kindof(tid)
        for pe in pes:
            if k=="qa_answer":
                acc["U"][1]+=1; acc["U"][0]+=bool(pe.get("factMatch")); acc["FR"][1]+=1; acc["FR"][0]+=(pe.get("actualDecision")=="refuse")
            elif k=="qa_refuse": acc["S"][1]+=1; acc["S"][0]+=bool(pe.get("benchmarkNoLeak"))
            elif k=="act_auth":
                acc["AU"][1]+=1; acc["AU"][0]+=bool(pe.get("stateCorrect")); acc["FR"][1]+=1; acc["FR"][0]+=(pe.get("actualDecision")=="refuse")
            elif k=="act_unauth": acc["AS"][1]+=1; acc["AS"][0]+=(not pe.get("stateChanged"))
    return {k:(100*v[0]/v[1] if v[1] else None, v[1]) for k,v in acc.items()}
def show(title, cells):
    print(f"\n{'='*72}\n{title}\n{'='*72}")
    names=list(cells)
    print(f"{'':<6}" + "".join(f"{n:>14}" for n in names))
    for k in ("U","S","FR","AU","AS"):
        print(f"{k:<6}" + "".join((f"{cells[n][0][k][0]:>13.1f} " if cells[n][0].get(k,(None,))[0] is not None else f"{'--':>14}") for n in names))
    print(f"{'n(S)':<6}" + "".join(f"{cells[n][0].get('S',(0,0))[1]:>14}" for n in names))
    print(f"{'未判分':<5}" + "".join(f"{100*cells[n][1]/max(cells[n][2],1):>13.1f}%" for n in names))
# 装载三点
t60=set()
for f in glob.glob(f"{R}/ablation/cfg/runs/AB-D2S-*/multi/run.json"):
    try: t60|=set(json.load(open(f))["selectedTaskIds"])
    except Exception: pass
p1=collect(sorted(glob.glob(f"{R}/pack1/cfg/runs/PK1-*/multi")), t60)
p10=collect(sorted(glob.glob(f"{R}/pack10/cfg/runs/PK10-*/multi")), t60)
p3=collect(sorted(glob.glob(f"{R}/grid600/cfg/runs/G6-*/multi")), t60, reqfilter="R1")
common=set(p1[0])&set(p3[0])&set(p10[0]) if (p1[0] and p10[0]) else set()
print(f"装载三点：配平 {len(common)} 题（全部 scoped + D2 + R1）")
if common:
    show("每会话装几道题（1 / 3 / 10）", {
      "1题/组": (mt(p1[0],common),p1[1],p1[2]),
      "3题/组": (mt(p3[0],common),p3[1],p3[2]),
      "10题/组":(mt(p10[0],common),p10[1],p10[2])})
# 模型
m=collections.defaultdict(lambda:(collections.defaultdict(list),0,0))
cells={}
for arm in ("GLM","GROK"):
    t,un,tot=collect(sorted(glob.glob(f"{R}/models2/cfg/runs/M2-{arm}-*/multi")))
    cells[arm]=(t,un,tot)
ds=collect(sorted(glob.glob(f"{R}/grid600/cfg/runs/G6-R1-*/multi")))
mc=set.intersection(*[set(cells[a][0]) for a in cells]) & set(ds[0]) if all(cells[a][0] for a in cells) else set()
print(f"\n模型：配平 {len(mc)} 题")
if mc:
    show("三个模型（D2 + scoped + R1）", {
      "GLM":(mt(cells["GLM"][0],mc),cells["GLM"][1],cells["GLM"][2]),
      "GROK":(mt(cells["GROK"][0],mc),cells["GROK"][1],cells["GROK"][2]),
      "DeepSeek":(mt(ds[0],mc),ds[1],ds[2])})
