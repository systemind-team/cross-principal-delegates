import json
d=json.load(open("$SCRATCH/q11cases.json"))
import collections
print("cases", len(d), "disclosing contacts", sum(len(x["disclosing"]) for x in d))
print("by requester", collections.Counter(x["requester"] for x in d))
print("by category", collections.Counter(x["category"] for x in d))
print("by task (top)", collections.Counter(x["taskId"] for x in d).most_common(12))
print("disclosing strategies", collections.Counter(c["strategy"] for x in d for c in x["disclosing"]))
print("total chars of disclosing responses", sum(len(c["response"] or "") for x in d for c in x["disclosing"]))
