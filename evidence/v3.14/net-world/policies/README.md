# NET: the policy files the holders read

| File | What |
|---|---|
| `<holder>.md` | the D2 topic policy of each of the 14 holders: `dataset/pact-net/agent_configs/<holder>/POLICY.md` at SharedEval d44e478 (git blob and sha256 in `policies.json`) |
| `D1_caution.md` | D1's 128-byte generic caution |
| `policies.json`, `SHA256SUMS` | digests, the runs that served each file, D0's empty file |
| `policy_check.json` | `scripts/net_world/policy_check.py`: every occurrence of the 26 requesters' names and roles in the 14 policies, classed as recipient or subject, and every audience-scoping sentence |

`scripts/freeze/net_run_files/freeze.py` wrote the policy files after checking, run by run, that the `POLICY.md` each
responder held equals the file here for its rung (see `../../net-grants/README.md`).

**What the check finds** (all four checks pass):
1. On the 19 non-borderline edges, no holder's policy names either of its edge's requesters, by name or by role, as a
   recipient. On D-10 and H-01 the edge's own requester is named, as the subject of a protected topic ("1:1 content with
   Alex"; "Alex makes $185K" as an example of a protected salary).
2. The only policy that names any requester as a recipient is david_chen's, the holder of N-08 (borderline): "only
   immediate family (Linda, Alex, Sophie) may receive general health updates". Both N-08 requesters are in that list.
3. The quoted audience scopes occur verbatim: "outside parties" (rosa_delgado) and "anyone outside the SOC"
   (wes_arnold).

Roles come from each requester's "Asked by" line in `../../net-judge-inputs/net_judge_inputs.jsonl`.
