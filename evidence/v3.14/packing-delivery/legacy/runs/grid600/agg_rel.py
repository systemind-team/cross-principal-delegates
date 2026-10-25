#!/usr/bin/env python3
"""grid600 按请求方聚合：分子分母求和后再算比率，绝不平均比率。"""
import json, os, glob, collections, sys
BASE="<vm>/runs/grid600/cfg/runs"
M=["informationUtility","informationSecurity","falseRefusalRate","actionUtility","actionSafety","leakRate"]
def load(run):
    m=f"{BASE}/{run}/multi"
    try:
        N=len(json.load(open(m+"/run.json"))["selectedTaskIds"])
        s=json.load(open(m+"/summary.json"))
    except Exception: return None
    nf=len(os.listdir(m+"/.sharedeval-file-failures")) if os.path.isdir(m+"/.sharedeval-file-failures") else 0
    if s.get("evaluationRows",0)<N or N==0 or nf: return None
    return {r["metric"]:(r["numerator"],r["denominator"]) for r in s["metrics"]}
pool=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0]))
perrep=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0]))
sess=collections.Counter(); dropped=collections.Counter()
for d in sorted(glob.glob(f"{BASE}/G6-*")):
    rid=os.path.basename(d); parts=rid.split("-"); q=parts[1]; rep=parts[2]
    r=load(rid)
    if r is None: dropped[q]+=1; continue
    sess[q]+=1
    for k,(n,de) in r.items():
        pool[q][k][0]+=n; pool[q][k][1]+=de
        perrep[(q,rep)][k][0]+=n; perrep[(q,rep)][k][1]+=de
qs=["R0","R1","R2","R3"]
print(f"{'metric':<24}" + "".join(f"{q:>10}" for q in qs))
for k in M:
    row=f"{k:<24}"
    for q in qs:
        n,de=pool[q][k]; row+=f"{100*n/de:>9.1f} " if de else f"{'--':>10}"
    print(row)
print(f"{'Sessions':<24}" + "".join(f"{sess[q]:>10}" for q in qs))
print(f"{'掉的(不计入分母)':<20}" + "".join(f"{dropped[q]:>10}" for q in qs))
print("\n分母（判据：四列必须逐指标相等，否则不是 matched）")
for k in M:
    print(f"  {k:<24}" + "".join(f"{pool[q][k][1]:>8}" for q in qs))
