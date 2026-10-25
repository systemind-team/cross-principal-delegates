#!/usr/bin/env python3
"""Write the SharedEval run configs for the grok-4.6 supplement from design/run_plan.json.

Every field except the model block and the task ids is the GPT-5.6 Azure cells' config (files-single,
24 ticks, 32 tool calls, 600 s per task, 8 tasks in flight, category grading at run time). The model block
differs from GPT-5.6 in the deployment and in temperature 0, which the DeepSeek and GLM cells used and the
grok-4.6 deployment accepts (GPT-5.6's deployment rejects any value but its default).

  python3 scripts/single_grid/grok/make_configs.py --endpoint https://<resource>.cognitiveservices.azure.com/openai/v1 --out DIR [--trial]

The endpoint is an argument so the resource name stays out of the repository; the key is read at run time
from SHAREDEVAL_MODEL_API_KEY. --trial writes the trial cells (grok-trial-*) instead of the twelve plan cells;
--retry FILE writes <cell>-retry configs holding only the task ids retry_list.py listed for that cell.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DESIGN_DIR

TEMPLATE = """apiVersion: sharedeval-run/v1
kind: RunConfig
model:
  provider: azure-openai
  endpoint: {endpoint}
  deployment: grok-4.6
  apiKeyEnv: SHAREDEVAL_MODEL_API_KEY
  temperature: 0
  maxOutputTokens: 16000
  outputTokenLimitParameter: max_completion_tokens
benchmark:
  dataset: pact-pair
  policy: {policy}
  requester: {requester}
  gradingMode: category
  tasks:
    kind: all
    ids: [{ids}]
workflow:
  mode: single
  protocol: files
  maxTicks: 24
  stopWhen: all-terminal
  taskConcurrency: 8
budget:
  maxToolCalls: 32
  maxRuntimeMs: 600000
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--trial", action="store_true")
    ap.add_argument("--retry")
    args = ap.parse_args()
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+/openai/v1", args.endpoint):
        raise SystemExit("endpoint must be https://<host>/openai/v1")
    plan = json.load(open(os.path.join(DESIGN_DIR, "run_plan.json")))
    if args.retry:
        listed = json.load(open(args.retry))["cells"]
        cells = {}
        for c, tasks in listed.items():
            ids = [t["taskId"] for t in tasks]
            if not set(ids) <= set(plan["cells"][c]["ids"]):
                raise SystemExit(f"{c}: retry ids outside the plan")
            cells[f"{c}-retry"] = {**plan["cells"][c], "ids": [t for t in plan["cells"][c]["ids"] if t in set(ids)]}
    elif args.trial:
        cells = {c.replace("grok-", "grok-trial-", 1): {**plan["cells"][c], "ids": ids}
                 for c, ids in plan["trial"]["cells"].items()}
    else:
        cells = plan["cells"]
    os.makedirs(args.out, exist_ok=True)
    for cid, c in cells.items():
        with open(os.path.join(args.out, f"{cid}.yaml"), "w") as f:
            f.write(TEMPLATE.format(endpoint=args.endpoint, policy=c["policy"], requester=c["requester"],
                                    ids=", ".join(c["ids"])))
    print(f"wrote {len(cells)} configs ({sum(len(c['ids']) for c in cells.values())} task-runs) to {args.out}")


if __name__ == "__main__":
    main()
