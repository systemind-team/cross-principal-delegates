# NET world inputs and the audience-class edges that could be seated

The authors' NET summary (`summary/pact_net_summary.tex`, Future work) makes this claim: 55 forbidden edges
protect an audience class rather than a named person, and "47 of them already have both a seated member of that
class and a matrix-legitimate peer". On that basis it says the paired set could grow from 24 to 71. This folder
freezes the world files needed to test the claim, and `audience_edges.json` records the result for each edge.

## Result

- **No source states how 47 was computed** (see "Where the rule was searched"). The count below therefore
  follows the literal reading, defined under "Rule".
- **Literal reading: 3 of the 55 audience-class edges qualify**: E-01, E-02 and S-03. The paired set becomes
  **24 + 3 = 27**.
  - In all three, every seated agent the matrix permits is itself a member of the forbidden audience: Kestrel
    staff for `kestrel_health`, and Kestrel or TechFlow staff for `techflow_or_kestrel`.
  - A permitted requester who belongs to the audience the fact is withheld from contradicts the edge. If the
    permitted requester must be outside that audience (the "strict" form), **0** edges qualify and the paired
    set stays **24**.
- **47 is not reproduced, and the matrix test caps the count below it.**
  - The matrix test is the summary's own: the permitted requester is labelled L for the fact's own category,
    the test the summary used for the named edges ("legitimate for that material").
  - With class membership ignored entirely, only **35** audience-class edges have such a requester among the
    task's seats with the holder seated, and **39** if any of the world's 60 agents may ask.
- **The repository's own analysis contradicts the claim.** SharedEval commit `ab6bb51` (2026-09-24, the day
  before the summary's commit `a5fa458`) adds `world_design/channel_registry.json`. Its `open_questions` say
  only 10 of the 55 entries resolve to a member set, and "only six of them are probeable as the tasks stand".
- **What 47 would require.** Searching combinations of relaxed conditions finds one that lands on 47:
  - legitimacy in *any* category rather than the fact's, from a seated agent, with the holder seated;
  - no class-membership test at all;
  - the four `everyone` edges dropped.

  It drops H-12, H-16, I-03, IAM-02, R-03, V-06, V-07 and V-13. Counting B (borderline) as legitimate as well
  also gives 47. This is a reconstruction found by search, not the authors' stated rule. It is in
  `audience_edges.json` under `diagnostics` only so that a reader can see what the number would need.

## Rule (literal reading)

An audience-class edge (a forbidden entry whose `forbidden_to` is not one of the 60 agents in
`contact_graph.json`) qualifies when all three of these hold:

1. **There is a responder and a category.** The holder is seated in the edge's task, and the protected fact is
   in a note bundled in the holder's `data.json`. The note's `sensitivity` is the fact's category. These are the
   d44e478 probe loader's own checks (`holder_not_an_actor`, `evidence_*`, `holder_has_no_store`).
2. **Some agent can act as the forbidden requester.** At least one seated agent other than the holder belongs
   to the forbidden audience.
3. **Another agent can act as the permitted requester.** At least one other seated agent (neither the holder
   nor that member) is labelled **L** for the fact's category in the holder's row of
   `relational_access_matrix.json`.

Two words in this rule need a definition:

- **Seated** means named as the task's `requester` or in its `participants`. This is the loader's actor set:
  the loader rejects a named edge whose recipient is not in it, and it draws the permitted requester from it.
- **Belongs** is taken only where the world records membership, in the two mechanical modes of the channel
  registry:
  - `organisation`: the agent's `systems.json` organisation is one the label names (`any_techflow_agent`,
    `kestrel_health`, `any_kestrel_agent`, `techflow_or_kestrel`);
  - `kinship`: the agent is a contact in the holder's `contact_book.json` with relationship spouse, parent,
    child, sibling or in-law (`family_group`).

  The other 33 labels record no membership in any world file:
  - open: `public`, `everyone`, `external_parties`;
  - surface (a channel or document);
  - exclusion (the complement of an unrecorded team);
  - task role;
  - unions of these.

  For those labels no agent can be shown to belong, so condition 2 fails. The registry is used only for each
  label's mode and resolver parameters. The members are recomputed from the frozen world files, and they equal
  the registry's for all five mechanical labels.

### The same rule under other readings

Each count is out of 55. The full lists are in `audience_edges.json` under `counts`.

| Membership | Who can ask | Literal | Strict |
|---|---|---:|---:|
| **mechanical (headline)** | **seated in the task** | **3** | **0** |
| mechanical | any of the 60 agents (holder need not be seated) | 9 | 5 |
| `everyone` and `public` hold all 60 agents | seated | 11 | 0 |
| `everyone` and `public` hold all 60 agents | any of the 60 | 17 | 5 |
| ignored (every agent is a member: upper bound) | seated | 35 | 0 |
| ignored | any of the 60 | 39 | 0 |

How the 55 fail under the headline:

| Count | Reason |
|---:|---|
| 45 | Membership not recorded in any world file: open 14, union 14, task role 7, exclusion 6, surface 4 |
| 2 | Members exist but none is seated: V-09 and V-12, where `any_techflow_agent` is asked inside Kestrel |
| 2 | Holder not seated: I-03 and V-13 |
| 1 | I-09: TechFlow members are seated, but no seated agent is L for `sensitive_work` in bea_ferreira's row |
| 1 | EP-02: Kestrel members are seated, but no seated agent is L for `sensitive_work` in samira_cole's row |
| 1 | LIFE-06: the only seated L agent, linda_chen, is the only seated family member |

The remaining 3 qualify. Each edge's reason is in `audience_edges.json` (`edges[].headline_reason`).

## Check: the rule's predicates reproduce the rerun's 24 pairs

From the same frozen files, `audience_edges.py` re-runs the d44e478 probe loader
(`src/suites/pact-net/v2-probes.ts`, `loadPactNetV2ProbesV1({arms: 'both'})`) over all 136 edges.

- **Rejected: 85.**
  - `forbidden_to_not_an_actor` 71: 51 audience labels and 20 named agents;
  - `evidence_outside_bundled_notes` 6;
  - `holder_not_an_actor` 4;
  - `forbidden_to_is_everyone` 4.
- **Probeable: 51.** 24 have a matrix-legitimate permitted requester; the other 27 only the loader's fallback.

This is the summary's own funnel: 136 − 85 = 51, and 51 − 27 = 24. The 24 equal `paired_edges_24.json` (the
rerun's record) edge by edge, in holder, withheld requester, permitted requester and category. So "seated" and
"matrix-legitimate" here are the predicates the rerun used.

## Where the rule was searched

- `summary/pact_net_summary.tex`: the claim (Future work) and the funnel table give the rule in words only. The
  commit that introduced both, `a5fa458` (2026-09-25), does not state it either.
- At d44e478:
  - `dataset/pact-net/README.md` and `STRUCTURE.md`: no membership rule for audiences.
  - The 13 scripts in `dataset/pact-net/scripts/`: none resolves an audience label. `review.py` checks only
    the evidence note.
  - `src/suites/pact-net/v2-probes.ts`: rejects every audience edge, as `forbidden_to_is_everyone` or
    `forbidden_to_not_an_actor`.
- Every ref of the local SharedEval clone (`git grep -i -E 'audience|class member|seated member'` over
  `src/`, `scripts/`, `dataset/pact-net/scripts/` and `tests/`): only
  `tests/suites/pact-net/channel-registry.test.ts`, which tests the registry.
  - The registry exists only in the local clone, on branch `net/differential-disclosure` (`ab6bb51`).
  - It is not on GitHub, not in any VM clone, and not part of d44e478.
- On the VM: no script under `<vm>/runs` or in the clones' `scripts/` mentions audiences.

## Files

`SHA256SUMS` lists the sha256 of every frozen input; `audience_edges.py` checks all 108 entries before it
computes anything. `sources.json` gives each file's source and git blob.

| Path | Source | Notes |
|---|---|---|
| `world/dataset/pact-net/tasks/pact_net_tasks_v2.json` | SharedEval d44e478 | 166 tasks; the 136 forbidden edges; the seats |
| `world/dataset/pact-net/world_design/relational_access_matrix.json` | d44e478 | L/P/B per holder, requester and category |
| `world/dataset/pact-net/world_design/contact_graph.json` | d44e478 | the 60 agents |
| `world/dataset/pact-net/agent_configs/<agent>/systems.json` × 60 | d44e478 | organisation |
| `world/dataset/pact-net/agent_configs/<holder>/data.json` × 41 | d44e478 | the note holding each fact, and its sensitivity. alex_chen holds facts but ships no `data.json`. |
| `world/dataset/pact-net/agent_configs/david_chen/contact_book.json` | d44e478 | the kinship anchor for `family_group` (LIFE-06) |
| `registry/channel_registry.json` | SharedEval `ab6bb5132f36e7d2d5b470938839a572b5ef598c`, local clone only | label → membership mode. Not part of d44e478. |
| `paired_edges_24.json` | derived from `evidence/v3.13/net-rerun/contacts.jsonl` (sha256 in the file) | the rerun's 24 edges and their two requesters |
| `sources.json` | written by `freeze_world.py` | |
| `audience_edges.json` | written by `audience_edges.py --write` | the result; not in `SHA256SUMS` |

**How the d44e478 files were taken.** d44e478 itself is only in the VM clone
`<vm>/repos/SE-net-e1`. Its root tree `00eecd0b…` is also in the local clone, as the tree of
`6773638` on `origin/net/register-missing-workspaces`. The bytes were therefore read locally by tree id. The
VM then hashed the same 123 paths with `git cat-file` at d44e478 (`scripts/freeze/net_edges/vm_hashes.py`).
All 105 frozen world files equal the VM's sha256, git blob id and size; `freeze_world.py` refuses to write
otherwise.

## Reproduce

From the worktree root:

```
ssh <host> python3 - < scripts/freeze/net_edges/vm_hashes.py > <tmp>/vm_hashes.json         # read-only on the VM
python3 scripts/freeze/net_edges/freeze_world.py --vm-hashes <tmp>/vm_hashes.json            # re-freeze (idempotent)
python3 scripts/freeze/net_edges/audience_edges.py --write                                   # offline, stdlib only
```

`audience_edges.py` reads nothing outside this folder and prints the counts in the tables above.

## World counts (Appendix E's world table)

`scripts/net_world/counts.py` writes `counts.json` from these files (it first checks every file against
`SHA256SUMS`): 60 agents; 402 directed contact links, 6.7 per holder; 2,010 access-matrix cells (L 504, P 1,331,
B 175); 166 tasks with 3.93 seated agents on average and never fewer than 3; every topology fan-out, 13 tasks
tagged chain; 136 forbidden edges, 81 naming an agent and 55 an audience; 10 executable-core tasks; and the probe
funnel of `audience_edges.json`: 51 probeable edges, 24 paired (all with a matrix-legitimate permitted
requester), 19 non-borderline.
