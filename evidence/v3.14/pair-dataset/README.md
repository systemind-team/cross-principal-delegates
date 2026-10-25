# PAIR task set, workspace and policy texts (frozen inputs)

Copies of SharedEval files that the paper's scripts read. Nothing here was edited.

| File | Source (SharedEval) | sha256 |
|---|---|---|
| `questions.json` | `dataset/pact-pair/tasks/questions.json` at 913bf49 (identical at 8081e7e, the ladder grid's revision, and at 65f7070) | 9032f46a… |
| `alex_data_store.json` | `dataset/pact-pair/data_spec/alex_data_store.json` at 913bf49 (identical at 8081e7e) | f67467c1… |
| `relationship_label_matrix_v1.1.json` | `dataset/pact-pair/relationship_labels/relationship_label_matrix.json` (v1.1, last changed in 913bf49): rows Q101–Q200 with the 39 B cells | 56680eb4… |
| `policies/PAIR-I_D{0,1,2}_R{0..3}.md` | `dataset/pact-pair/policies/D{k}_R{j}.md` at 9c29358 (the PAIR I policy assets; D0_R1, D1_R1 and D2_R1 match `evidence/v3.13/single-grid/policies/` byte for byte) | see `sha256sum` |
| `policies/PAIR-II_ladder_D1.md`, `PAIR-II_ladder_D2_category.md` | `dataset/shared-eval/workspaces/v1/policies/pact-pair-defense/d{1,2}/1.0.0/POLICY.md`, identical at 8081e7e | 94c9bd88…, a213e556… |
| `policies/PAIR-II_identity_D2R_PRINCIPLES.md` | `dataset/pact-pair/policies/D2R_PRINCIPLES.md`, identical to `evidence/v3.1/.../D2R_PRINCIPLES.md` and to the `pact-pair-principles/d2r` asset at 8081e7e | f400db89… |

The relationship label file itself is frozen in `evidence/v3.1/sharedeval/dataset/pact-pair/relationship_labels/`.

Regenerate: `git -C <SharedEval> show 913bf49:dataset/pact-pair/tasks/questions.json > questions.json` and likewise for the
other files at the revisions above.
