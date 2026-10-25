# Provenance of the kernel and evaluator revisions

Appendix B.2 cites this folder. It checks, value by value, the revision table Appendix B printed before this check
(Table 9). Every value was recomputed
read-only on 2026-10-04/05 from the local clones, the experiment VM and, for one lookup, GitHub.

| File | What it is |
|---|---|
| `provenance.json` | The full manifest. For each label it gives the full commit, the tree, what the revision is, where and how it was checked, and whether the check passed. It also holds the K1–K2 divergence, the runtime packages, the pin each evaluator revision declares (file and line), what every run directory recorded loading, and the E2 revision of every session. |
| `revision_labels.json` | A flat map from each paper label to its full commit id, for the supplement export. A label that covers several commits maps to a list. Two E1 entries are short ids; see "Not verified". |
| `revision_dates.json` | Each label's commits with their author and committer dates, read from the local clones by `scripts/freeze/provenance/revision_dates.py` (no subject or author recorded; a commit absent from the clones is marked). E2's three revisions were committed on 2026-09-24 at 01:08:56, 02:54:14 and 11:12:05 (+08:00), a span of 10 h 3 min. |

To regenerate both files, run this from the worktree root:

```
python3 scripts/freeze/provenance/collect.py --github --write
```

Without `--write` the script only prints the values. It needs the local SharedOS clone
(`$SHAREDOS_CLONE`), a K2 checkout with its packages built (`$SHAREDOS_K2_BUILD`), a
SharedEval clone (`$SHAREDEVAL_CLONE`), node ≥ 23, `ssh <host>`, and `gh` for `--github`.
The VM half is `scripts/freeze/provenance/vm_checks.py`, fed over stdin. Its docstring lists everything it
opens; it reads no env file, key or gateway folder. `generated_utc` is the only field that changes between
runs.

## Result

| Label | Full commit | Tree | Verified | How |
|---|---|---|---|---|
| K1 | `c74461c1c4b715fd60c18401100cd72362d3afc1` | `b1f29050bf42ad2f97fb5fef2a3ed107d42bfabc` | yes | Local SharedOS clone and VM clone `repos/SharedOS`; on GitHub `systemind-team/SharedOS`. It is the merge commit of PR #64. |
| K1-live | `5392148fbcb229927643df5009ef2e0e2508af27` | `b1f29050…` (same as K1) | yes | The second parent of K1, with an identical tree. Author date 2026-09-08T13:14:57Z, the date of the live pass. |
| K2 | `3aa07e33999b656a10ace294fd4e41df8cbc318e` | `1745fa36f8157c8a52a3dd12266ea046ceccda4c` | yes | Local and VM clones. VM checkout `repos/SharedOS-3aa07e3` is at K2 with no tracked changes and all four `dist/` builds present. |
| runtime digest | `4afb23d79851a83a48e25e968f04e45cefc81847b4a9963c62277b5c05862d5d` | – | yes | Declared at every evaluator revision opened (below). Recomputed from the built K2 checkout with SharedEval 8081e7e's own `digestSharedOsRuntimeV1`, and equal. Recorded at run time by every run directory of E2, E3, E3-header and E4. |
| E1 | `58829feb17289e4e3092dae44089831a51336c4a`, `0735564b0c318b83fd2b611f73b25f2c74f4e5b5`, `79b52cf8b76b`, `40f4f01` | – | **partly** | The first two are in the local clone, in every VM SharedEval clone and on GitHub, and both pin K2. **`79b52cf8b76b` and `40f4f01` are not in any clone and not on GitHub**, so their pin is unverified. The cell-to-image map is verified (below). |
| E2 | `e20062ef31adb01113a64a0acc80d226ccf1f305`, `5db4182c8c3b1082e4585b6473d70fa8296cbe67`, `26dd392fc83df022f29bc0852f4bedfdf69ba0ae` | – | yes | Per-session counts are below. |
| E3 | `8081e7e78e0e5acfe79830c606619faae53c3b0a` | `0e2ac35d26c77c15000a4126a6b3a994392314bb` | yes | Local clone; VM clone `repos/SharedEval-a1` (HEAD, no tracked changes). Its parent is `26dd392`. |
| E3-header | `4565add03628d967938f8a6cebf2d33b27f80249` | `b898c190a40660b47acf210d01502f099cbe55eb` | yes | VM clone `repos/SharedEval-told` (HEAD, no tracked changes). Its only parent is E3. E3's tree plus the patch is exactly this tree (below). |
| E4 | `d44e4788562c438a97180443ee8cc5170094ad07` | `00eecd0bc16b37a170949afeb23f34bcedb8ad23` | yes | VM clone `repos/SE-net-e1` (HEAD, no tracked changes). The local clone does not have the commit but does have its tree, as the tree of `6773638d927a39ac76e294b7987860f74fdd2da3` (on GitHub, branch `net/register-missing-workspaces`). The two commits share subject and author date; d44e478 has a different parent (`511e225`). |

**Nothing in that table is contradicted.** The qualifications are listed under "Not verified" and "Notes".

## K1–K2 divergence (the numbers B.2 prints)

These were run in the local SharedOS clone with git 2.50.1:

```
git merge-base 3aa07e3 c74461c            # bd76d1161ec3f2a3aed74b079efe466f312c5c9a (the only merge base)
git rev-list --count bd76d116..3aa07e3    # 9    commits in K2 only
git rev-list --count bd76d116..c74461c    # 178  commits in K1 only
git diff --shortstat 3aa07e3 c74461c -- packages/contracts/src packages/core/src packages/os/src packages/runtime/src
#  47 files changed, 9382 insertions(+), 370 deletions(-)
```

- 9,382 + 370 = **9,752 changed source lines**, which is the number Appendix B.2 prints.
- The count is the same with `--no-renames` and with `-M`, and no file is binary.
- Per package: contracts 8 files, +317/−1; core 27 files, +7,206/−283; os 2 files, +405/−6; runtime 10 files, +1,454/−80.
- For scale, the whole-repository diff is 187 files, +29,143/−4,545.

## The four runtime packages

`SHAREDOS_RUNTIME_PACKAGES_V1 = ['contracts', 'core', 'os', 'runtime']` is in SharedEval
`src/execution/sharedos/v1/load-sharedos.ts`, **lines 26–31, at every evaluator revision opened**. The
same four directories are what `digestSharedOsRuntimeV1` hashes and what `build-image.sh` checks for a `dist/` build.

| Directory | npm name | Version at K2 | Version at K1 |
|---|---|---|---|
| `packages/contracts` | `@aicoo/sharedos-contracts` | 0.1.0-alpha.3 | 0.1.0-alpha.4 |
| `packages/core` | `@aicoo/sharedos-core` | 0.1.0-alpha.3 | 0.1.0-alpha.4 |
| `packages/os` | `@aicoo/sharedos-os` | 0.1.0-alpha.3 | 0.1.0-alpha.4 |
| `packages/runtime` | `@aicoo/sharedos-runtime` | 0.1.0-alpha.3 | 0.1.0-alpha.4 |

## The pin each evaluator revision declares

Each value was read with `git show <rev>:<file>`. The first six revisions were read in the local clone
**and** in VM clone `SharedEval-a1`. 4565add was read in `SharedEval-told` and d44e478 in `SE-net-e1`, both on
the VM; d44e478 was also read locally through its tree.

| Revision | `load-sharedos.ts` 34–35 `SHAREDOS_VERIFIED_REVISION_V1` | 36–37 `SHAREDOS_VERIFIED_RUNTIME_DIGEST_V1` | `build-image.sh` 20 `SHAREDOS_PINNED_REVISION` | `.github/workflows/ci.yml` `SHAREDOS_PIN` |
|---|---|---|---|---|
| 58829fe | K2 | 4afb23d7… | K2 | line 60: **`ac0f1bb210baa3ba4b7e0d0baaf2291bbe9ffd05`** |
| 0735564 | K2 | 4afb23d7… | K2 | line 60: **`ac0f1bb2…`** |
| e20062e | K2 | 4afb23d7… | K2 | line 61: K2 |
| 5db4182 | K2 | 4afb23d7… | K2 | line 61: K2 |
| 26dd392 | K2 | 4afb23d7… | K2 | line 61: K2 |
| 8081e7e | K2 | 4afb23d7… | K2 | line 61: K2 |
| 4565add | K2 | 4afb23d7… | K2 | line 61: K2 |
| d44e478 | K2 | 4afb23d7… | K2 | line 61: K2 |

The runtime pin, the digest and the image-build pin are K2 everywhere. The CI pin at the two E1 revisions is
not K2: it is SharedOS `ac0f1bb` (merge of PR #20, 2026-08-28), an ancestor 12 commits behind K2. That pin only
chooses which SharedOS SharedEval's CI `sharedos-loader` job checks out. What a run loads is decided by the
loader's revision and digest check, which fails closed, and by `build-image.sh` for images. Read "pinned by
every evaluator revision" as the runtime pin.

Other commands used:

```
git -C <SharedEval> show <rev>:src/execution/sharedos/v1/load-sharedos.ts | sed -n '26,37p'
git -C <SharedEval> show <rev>:scripts/experiments/build-image.sh | sed -n 20p
git -C <SharedEval> show <rev>:.github/workflows/ci.yml | grep -n SHAREDOS_PIN
```

## The runtime digest, recomputed

```
git -C <SharedEval> show 8081e7e:src/execution/sharedos/v1/load-sharedos.ts > $tmp/load-sharedos.ts
printf "import { digestSharedOsRuntimeV1 } from './load-sharedos.ts';\nconsole.log(digestSharedOsRuntimeV1(process.argv[2]));\n" > $tmp/run.mts
cd $tmp && node run.mts $SHAREDOS_K2_BUILD
# node v25.8.1 -> 4afb23d79851a83a48e25e968f04e45cefc81847b4a9963c62277b5c05862d5d
```

The local checkout is at K2 with no tracked changes. Its `dist/` builds and its zod install are untracked, as
they are on the VM. The result is equal to the pinned digest.

## What the runs recorded loading (K2 "loaded by every study")

Every run directory keeps `multi/.sharedeval-file-workflow/binding.json`. The harness writes into it the
SharedOS revision and runtime digest it verified at load (`binding.sharedOs.sharedOsRevision`,
`.sharedOsRuntimeDigest`). Every directory found was read:

| VM lane | Study | Run directories | Bound K2 with digest 4afb23d7… |
|---|---|---:|---:|
| `grid600` | E2 probing grid | 2,400 | 2,400 |
| `pack1` | E2 packing, 1 per session | 180 | 180 |
| `pack10` | E2 packing, 10 per session | 18 | 18 |
| `t3simple` | E3 ladder grid (run ids `S4-*`) | 1,389 | 1,389 |
| `pair2id2` | E3 identity comparison | 413 | 413 |
| `pair2told` | E3-header header ladder | 619 | 619 |
| `net-or-ds` | E4 NET rerun, DeepSeek | 432 | 432 |
| `net-or-glm` | E4 NET rerun, GLM | 288 | 288 |

Counts include retried runs, which have their own directories. PAIR I (E1) could not be checked this way;
see below.

The last launch log of each run id (`<lane>/logs/*.log`) prints the SharedEval `sourceRevision`:

| Lane | sourceRevision | No sourceRevision printed |
|---|---|---|
| `t3simple` | 8081e7e × 1,346 | 43 |
| `pair2id2` | 8081e7e × 398 | 15 |
| `pair2told` | 4565add × 596 | 23 |
| `net-or-ds` | d44e478 × 393 | 40 |
| `net-or-glm` | d44e478 × 272 | 17 |

This holds across every log in these lanes, not only the last one per run: the only revision any log prints
is the one its label names. Every log that prints none is short (under 4 KiB) and carries an error message,
so it records a launch that failed. See `other_lanes_launch_revisions` in `provenance.json`.

## E2: revision per session

The rule, the same as `evidence/v3.14/packing-delivery`: the `sourceRevision` printed by the session's **last**
launch log, by mtime. Sessions are the lane's `cfg/*.json`.

| Study | Sessions | 5db4182 | 26dd392 | e20062e | none printed |
|---|---:|---:|---:|---:|---:|
| `grid600` (probing grid) | 2,400 | 2,353 | 30 | 16 | 1 |
| — R0 | 600 | 581 | 7 | 12 | 0 |
| — R1 | 600 | 589 | 8 | 3 | 0 |
| — R2 | 600 | 590 | 10 | 0 | 0 |
| — R3 | 600 | 593 | 5 | 1 | 1 |
| `pack1` | 180 | 0 | 180 | 0 | 0 |
| `pack10` | 18 | 0 | 18 | 0 | 0 |

- No session's launches disagree with each other.
- All 2,598 per-session values equal `source_revision` in `evidence/v3.14/packing-delivery/sessions.jsonl.gz`.
- By that freeze's validity flag, all 2,399 grid sessions with a revision are valid.
- The one session with no revision is **G6-R3-r3-g094**, and it is invalid. None of its eight launch logs prints
  a revision. Its run.json carries `backend.kernelRevision`, which only code from 26dd392 on writes (PR #92;
  `git grep kernelRevision` finds it in src at 26dd392 and not at 5db4182 or e20062e). That fits 26dd392, but
  no log shows it.
- run.json carries `backend.kernelRevision` in exactly 31 grid sessions: the 30 launched from 26dd392, plus
  G6-R3-r3-g094.
- Every pack1 and pack10 session carries it, set to K2 with digest 4afb23d7….

## E1: which image each PAIR I cell ran

Source: `<vm>/work/v41-grid-out/*/*/cell-provenance.json`, read for `imageRef` and
`imageDigest` only.

| Image | Image digest | Cells |
|---|---|---:|
| `sharedeval-experiment:58829feb1728` | `sha256:bc17ce54a4dfaece3ce0600058fbbdb65077ccb9d72dbb3b902ee61f48596dd6` | 58, of which 2 are voided `*.bad-504-20260914` |
| `sharedeval-experiment:0735564b0c31` | `sha256:5eab4c1d13c453ca29ce6779c49390a8c0d024a891e98ce9acfebfa20e2e6367` | 24 (`xC-*`, `xD-*`) |
| `sharedeval-experiment:79b52cf8b76b-codex` | `sha256:2abe0ab279e03e3b9af7b65ad726936ff85758c536b0061fbf067533cd8435ca` | 2 (`codex-d2-r1`, `codex-d2-r3`) |

That is 56 + 24 + 2 = 82 valid OpenRouter cells, the count in `evidence/v3.13/single-grid/rescore-openrouter-82.json`.
`build-image.sh` tags an image `sharedeval-experiment:<first 12 hex of HEAD>` by default, so `79b52cf8b76b`
is that commit's prefix and `-codex` a hand-set suffix.

## Not verified

1. **`79b52cf8b76b`** (the `-codex` image) and **`40f4f01`** (the Azure cells, run natively):
   - They are not in the local SharedEval clone or any of the six SharedEval clones on the VM.
   - `gh api repos/systemind-team/SharedEval/commits/<id>` returns 422 "No commit found" for both.
   - The image is not in the VM's docker, so its `org.sharedeval.*` labels cannot be read.
   - Their SharedOS pin is therefore **unverified**. The same holds for `5aaa7f1`, the rescore tool's commit
     (parent 40f4f01) named in `evidence/v3.13/single-grid/manifest.json`.
   - `revision_labels.json` gives them as short ids, because no readable clone resolves them: `79b52cf8b76b`
     (12 hex, from the image tag) and `40f4f01` (from `appendix/current_single.tex` and Table 9).
2. **No PAIR I run record shows which SharedOS was loaded.**
   - The OpenRouter per-task directories (`…/runs/*/single/*`) are mode 700 and owned by <user>.
   - `<vm>/luna`, the Azure cells, cannot be read by user <user>.
   - For E1, "K2 loaded" rests on the source pins of 58829fe and 0735564 and on the v3.13 single-grid
     manifest's statement "3aa07e33999b (pinned for every cell)". It does not rest on run records.
3. **d44e478 (E4) and 4565add (E3-header) are not on GitHub.** They exist only in VM clones. Their content can
   still be reproduced from public commits:
   - d44e478's tree is the tree of `6773638` (on GitHub);
   - 4565add's tree is E3's tree with `scripts/pair_multi/told_ladder/sharedeval-told-4565add.patch` applied.
     Checked as follows: a throw-away bare repository borrows the SharedEval clone's objects through
     `objects/info/alternates`, then
     `git read-tree 8081e7e…; git apply --cached <patch>; git write-tree` gives `b898c190…`. That equals
     `git rev-parse 4565add^{tree}` on the VM. The patch's stable patch-id is `25c8f4a08b7c8ab41b1cba79c6ce53057012d84f`.
4. **Runs whose last launch log prints no revision** (counts in the table above). Their SharedEval revision
   cannot be read from the log. Each one still recorded binding K2 with the pinned digest.

## Notes

- **K1 is not the kernel the studies loaded.** K1 (and its live pass) is the conformance snapshot. Every
  evaluation run bound K2, and K1 is 178 commits ahead of their merge base.
- **The ladder grid ran in lane `t3simple`, not `t3full`.**
  - `evidence/v3.13/multi-table3/MANIFEST.json` is byte-identical to the VM's `t3simple/MANIFEST.json`
    (sha256 `36119d69…`). Its 1,350 configs are the `S4-*` ids of t3simple.
  - Its `source` field, `<vm>/runs/t3full/cfg`, names the strict-profile grid the 50 groups were
    taken from.
  - `t3full` is a different run (`T3-*`, strict profile). Its last launch logs print 26dd392 × 995, and 400 print
    no revision. It is not under any label in Table 9. If the paper reports a t3full number anywhere, its
    evaluator revision is not fully determined.
- **The NET runs' run.json has no `backend.kernelRevision`.** d44e478 is not on the PR #92 line. Their
  binding.json records K2 and the digest, as above.

## Routes, dates and tools per study

`runs.json`, written by `scripts/freeze/provenance/runs.py` from frozen files only (each entry names its source):
the evaluator label and commits, the model route (provider, model or deployment, upstream pin, temperature) and the
run dates of PAIR I, the probing grid, the packing study, the ladder grid, the header comparison, the header ladder
and the NET run, and PAIR I's offline rescore tool (`scripts/experiments/rescore-relationship-grid.ts
--include-text --recover-quarantined-qa` at SharedEval `5aaa7f1`, a child of `40f4f01`). PAIR I's run dates are not
recorded in any frozen file; the file says so instead of guessing.

## D.6's ablation lane

`ablation_binding.json`, from `scripts/freeze/provenance/vm_ablation_binding.py` (read-only on the VM, the same reads
as `vm_checks.py`'s `recorded()`): every one of the lane's 960 runs bound K2 with the pinned runtime digest in its
`binding.json`, including all 480 sessions behind Table 33's D0 and D1 (arms AB-D0T and AB-D1T, 240 each).
`run.json`'s `kernelRevision` field is empty in the 313 runs launched at E2's `5db4182` (82 AB-D0T, 230 AB-D0S, 1
AB-D2S), as in the other E2 lanes; the binding record is the one the harness checks.
